try:
    import spacy
except ImportError as e:
    print(f"Warning: Failed to import spacy ({e}). Advanced NLP features may be degraded.")
    spacy = None

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
import fitz  # PyMuPDF
import io
import os
import json
from docx import Document
from dotenv import load_dotenv
import warnings
# Suppress Google Generative AI deprecation/future warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google.*")
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure Generative AI
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
else:
    model = None

# NLP model (spaCy) will be lazy loaded
_nlp = None

def get_nlp():
    global _nlp
    if _nlp is None and spacy:
        try:
            print("Loading spaCy model (en_core_web_sm)...")
            _nlp = spacy.load("en_core_web_sm")
            print("spaCy model loaded.")
        except Exception as e:
            print(f"Error loading spaCy: {e}")
            _nlp = None
    return _nlp

class RecruitmentAI:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words='english')

    def extract_text_from_pdf(self, file_bytes):
        """Extract text from PDF using PyMuPDF."""
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            return text
        except Exception as e:
            print(f"PDF Extraction Error: {e}")
            return ""

    def extract_text_from_docx(self, file_bytes):
        """Extract text from DOCX using python-docx."""
        try:
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            print(f"DOCX Extraction Error: {e}")
            return ""


    def calculate_match_score(self, resume_text, jd_text):
        """Fallback Score: TF-IDF aur Cosine Similarity."""
        try:
            documents = [resume_text, jd_text]
            tfidf_matrix = self.vectorizer.fit_transform(documents)
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
            return round(float(similarity[0][0]) * 100, 2)
        except Exception as e:
            print(f"Scoring Error: {e}")
            return 0.0


    def extract_entities(self, text):
        """
        spaCy use karke Organizations (ORG) aur potential locations/names nikalna.
        """
        nlp = get_nlp()
        if not nlp:
            return {"organizations": [], "skills": []}
            
        doc = nlp(text)
        entities = {
            "organizations": [ent.text for ent in doc.ents if ent.label_ == "ORG"],
            "people": [ent.text for ent in doc.ents if ent.label_ == "PERSON"],
        }
        return entities

    def calculate_match_score(self, resume_text, jd_text):
        """
        TF-IDF aur Cosine Similarity ke zariye scoring (0 to 100).
        """
        try:
            # Combine both texts to vectorize together
            documents = [resume_text, jd_text]
            tfidf_matrix = self.vectorizer.fit_transform(documents)
            
            # Calculate cosine similarity
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
            
            # Convert to percentage
            score = round(float(similarity[0][0]) * 100, 2)
            return score
        except Exception as e:
            print(f"Scoring Error: {e}")
            return 0.0

    def _calculate_heuristic_score(self, base_score, matching_skills):
        """
        Deterministic scoring based on evidence quality (Metrics, Specificity).
        Inspired by Stage 2 of the AI Distiller.
        """
        adjustment = 0
        breakdown = []

        # 1. Metric Bonus: Check for numbers, percentages, or currency in evidence
        metric_pattern = re.compile(r'\d+%|\$\d+|increased|decreased|grew|reduced|saved', re.IGNORECASE)
        points_for_metrics = 0
        
        for skill in matching_skills:
            evidence = skill.get("evidence", "")
            if metric_pattern.search(evidence):
                points_for_metrics += 3
        
        if points_for_metrics > 0:
            bonus = min(points_for_metrics, 15) # Cap metric bonus at 15
            adjustment += bonus
            breakdown.append(f"Evidence Bonus (+{bonus}%): Quantitative achievements detected.")

        # 2. Specificity Check: Penalty for very short/generic context
        generic_count = 0
        for skill in matching_skills:
            context = skill.get("context", "")
            if len(context.split()) < 3:
                generic_count += 1
        
        if generic_count > 2:
            adjustment -= 5
            breakdown.append("Genericism Penalty (-5%): Some claims lack professional context.")

        final_score = min(max(base_score + adjustment, 0), 100)
        return round(final_score, 2), breakdown

    async def analyze_cv_comprehensively(self, resume_text, jd_text):
        """
        FYP-Level Deep Analysis using Generative AI with Heuristic Validation.
        """
        if not model:
            score = self.calculate_match_score(resume_text, jd_text)
            return {
                "match_score": score,
                "summary": "AI Analysis unavailable (Missing API Key).",
                "matching_skills": [],
                "missing_skills": [],
                "interview_questions": [],
                "score_breakdown": ["Basic TF-IDF similarity."]
            }

        prompt = f"""
        You are an expert HR Recruitment AI. Conduct a multi-stage analysis of this Resume against the Job Description.
        
        STAGES:
        1. Extraction: Find all professional capabilities (SUPPLY) in the resume.
        2. Mapping: Compare Supply against Job Requirements.
        3. Evidence Validation: For ogni matching skill, extract the exact context and a verbatim quote from the resume as proof.

        Job Description:
        {jd_text}
        
        Resume:
        {resume_text}
        
        Return STRICT JSON format:
        {{
          "match_score": (0-100 integer - initial semantic match),
          "summary": (Professional recommendation),
          "matching_skills": [
            {{
              "skill": "Skill name",
              "context": "Short description of how/where it was used",
              "evidence": "Verbatim quote from resume showing proof (max 100 chars)"
            }}
          ],
          "missing_skills": ["List of key JD requirements missing in resume"],
          "interview_questions": ["3-5 personalized questions"]
        }}
        """

        try:
            response = model.generate_content(prompt)
            text_response = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(text_response)
            
            # Apply Heuristic Scoring
            base_score = data.get("match_score", 0)
            matching_skills = data.get("matching_skills", [])
            
            final_score, breakdown = self._calculate_heuristic_score(base_score, matching_skills)
            
            data["match_score"] = final_score
            data["score_breakdown"] = breakdown
            
            return data

        except Exception as e:
            print(f"Deep Analysis Error: {e}")
            score = self.calculate_match_score(resume_text, jd_text)
            return {
                "match_score": score,
                "summary": "Error during deep AI analysis. Fallback to basic scoring.",
                "matching_skills": [],
                "missing_skills": [],
                "interview_questions": [],
                "score_breakdown": ["Fallback active due to system error."]
            }



    async def distill_onboarding_profile(self, bio: str, cv_text: str, goals: str):
        """
        Takes multiple inputs (LinkedIn Bio, CV Text, and Goals) and distills them 
        into a unified professional profile (Profile + Supply).
        """
        if not model:
            return {
                "profile": {
                    "name": "", "job_title": "", "company": "", "location": "",
                    "headline": "", "bio": "", "contact_info": "", "hyperlinks": "-"
                },
                "supplies": []
            }

        prompt = f"""
        You are a Professional Profile Distiller AI. Analyze the candidate's info and create a structured profile.

        SOURCES:
        1. LinkedIn Bio: {bio}
        2. Experience Documents (CV): {cv_text}
        3. Stated Goals: {goals}

        GOALS:
        - Extract "PROFILE" details: Name, current Job Title, current Company, Location, a catchy Headline, a professional Bio summary, Contact Info (phone), and any Hyperlinks.
        - Extract "SUPPLIES": A list of specific professional capabilities (e.g., "I can provide...", "I can help with...").

        Return STRICT JSON format:
        {{
          "profile": {{
            "name": "Full Name",
            "job_title": "Current or targeted job title",
            "company": "Current or last company",
            "location": "City, Country",
            "headline": "Short professional headline",
            "bio": "Detailed professional bio",
            "contact_info": "Phone number or email found",
            "hyperlinks": "LinkedIn or Portfolio links"
          }},
          "supplies": [
            "Specific capability statement 1",
            "Specific capability statement 2"
          ]
        }}
        """

        try:
            response = model.generate_content(prompt)
            text_response = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(text_response)
        except Exception as e:
            print(f"Distiller Error: {e}")
            return {
                "profile": {
                    "name": "Error", "job_title": "", "company": "", "location": "",
                    "headline": "", "bio": "Error distilling profile.", "contact_info": "", "hyperlinks": "-"
                },
                "supplies": []
            }

    def extract_skills_manually(self, text, skill_list):
        """
        Di gayi skill list (JD se ayi hui) ke mutabiq check karna ke Resume mein kya hai.
        """
        found_skills = []
        for skill in skill_list:
            # Simple Case Insensitive Word Match
            if re.search(rf"\b{re.escape(skill)}\b", text, re.IGNORECASE):
                found_skills.append(skill)
        return found_skills

    async def match_applicant_to_jobs(self, applicant_supplies: list, jobs: list):
        """
        Generative AI logic to rank jobs for a specific applicant based on their supplies.
        """
        if not model or not applicant_supplies or not jobs:
            return []

        # Prepare a compact list of jobs for the prompt
        job_summaries = []
        for j in jobs:
            job_summaries.append({
                "id": str(j.get("_id", j.get("id"))),
                "title": j.get("title"),
                "description": j.get("description")[:500] # Limit context
            })

        prompt = f"""
        You are a Talent Matching AI. Match the applicant's capabilities (SUPPLIES) to the available JOBS.
        
        APPLICANT SUPPLIES:
        {json.dumps(applicant_supplies)}

        AVAILABLE JOBS:
        {json.dumps(job_summaries)}

        TASK:
        1. For each job, calculate a "match_score" (0-100).
        2. Provide a short "reasoning" (max 15 words) why this job matches or doesn't.
        
        Return STRICT JSON array:
        [
          {{
            "job_id": "id from input",
            "match_score": 85,
            "reasoning": "Your expertise in React and UI design perfectly fits this role."
          }},
          ...
        ]
        """

        try:
            response = model.generate_content(prompt)
            text_response = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(text_response)
        except Exception as e:
            print(f"Job Matching Error: {e}")
            return []


# Global Instance
ai_engine = RecruitmentAI()
