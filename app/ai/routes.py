from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List
from pydantic import BaseModel
from .engine import ai_engine

router = APIRouter()

# --- BULK ANALYZE CVS ---
@router.post("/analyze-cvs")
async def analyze_cvs(
    job_description: str = Form(...),
    files: List[UploadFile] = File(...),
):
    results = []
    
    for file in files:
        try:
            content = await file.read()
            text = ""
            
            if file.content_type == "application/pdf":
                text = ai_engine.extract_text_from_pdf(content)
            elif file.content_type in [
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/msword"
            ]:
                text = ai_engine.extract_text_from_docx(content)
            else:
                # Fallback for filenames
                if file.filename.endswith(".pdf"):
                    text = ai_engine.extract_text_from_pdf(content)
                elif file.filename.endswith(".docx"):
                    text = ai_engine.extract_text_from_docx(content)
                else:
                    results.append({"filename": file.filename, "score": 0, "error": "Unsupported file type"})
                    continue

            if not text.strip():
                results.append({"filename": file.filename, "score": 0, "error": "Could not extract text"})
                continue


           

            # Detailed AI Analysis
            analysis = await ai_engine.analyze_cv_comprehensively(text, job_description)
            results.append({
                "filename": file.filename,
                "score": analysis.get("match_score", 0),
                "summary": analysis.get("summary", ""),
                "matching_skills": analysis.get("matching_skills", []),
                "missing_skills": analysis.get("missing_skills", []),
                "interview_questions": analysis.get("interview_questions", []),
                "score_breakdown": analysis.get("score_breakdown", [])
            })
            
        except Exception as e:
            results.append({"filename": file.filename, "score": 0, "error": str(e)})

    # Sort by score descending (highest matching first)
    results.sort(key=lambda x: x["score"], reverse=True)
    
    return results


@router.post("/distill-onboarding")
async def distill_onboarding(
    bio: str = Form(""),
    goals: str = Form(""),
    experience_files: List[UploadFile] = File(default=[]),
    discovery_files: List[UploadFile] = File(default=[])
):
    """
    Distills a profile from LinkedIn Bio, CVs, and Goals.
    """
    try:
        combined_experience_text = ""
        combined_discovery_text = ""

        # Extract from Experience Files (CVs)
        for file in experience_files:
            content = await file.read()
            if file.filename.endswith(".pdf"):
                combined_experience_text += ai_engine.extract_text_from_pdf(content) + "\n"
            elif file.filename.endswith(".docx"):
                combined_experience_text += ai_engine.extract_text_from_docx(content) + "\n"

        # Extract from Discovery Files
        for file in discovery_files:
            content = await file.read()
            if file.filename.endswith(".pdf"):
                combined_discovery_text += ai_engine.extract_text_from_pdf(content) + "\n"
            elif file.filename.endswith(".docx"):
                combined_discovery_text += ai_engine.extract_text_from_docx(content) + "\n"

        # Combine goals with discovery doc text
        full_needs_text = f"Goals: {goals}\n\nDiscovery Docs Content:\n{combined_discovery_text}"

        # Distill with AI
        distilled = await ai_engine.distill_onboarding_profile(
            bio=bio,
            cv_text=combined_experience_text,
            goals=full_needs_text
        )

        return distilled

    except Exception as e:
        print(f"Onboarding Distill Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- AI CHAT ENDPOINT ---
class ChatRequest(BaseModel):
    prompt: str

@router.post("/chat")
async def ai_chat(request: ChatRequest):
    try:
        from .engine import model
        if not model:
            return {"response": "AI Chat is currently unavailable (No API Key)."}
            
        response = model.generate_content(request.prompt)
        return {"response": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
