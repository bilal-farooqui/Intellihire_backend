import fitz  # PyMuPDF
import docx
import re
import os

def extract_text_from_pdf(pdf_path):
    """PDF file se saara text nikalne ke liye."""
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
    return text

def extract_text_from_docx(docx_path):
    """Word (.docx) file se saara text nikalne ke liye."""
    text = ""
    try:
        doc = docx.Document(docx_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        print(f"Error reading Docx {docx_path}: {e}")
    return text

def clean_resume_text(text):
    """
    Text ko clean karne ke liye:
    1. Extra spaces/newlines hatata hai.
    2. Lowercase karta hai (AI ke liye behtar hai).
    3. URLS aur Email addresses ko generalize/remove kar sakta hai (optional).
    """
    # Remove extra whitespace and newlines
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters but keep common punctuation
    text = re.sub(r'[^a-zA-Z0-9\s,.@+-]', '', text)
    
    return text.strip().lower()

def process_resume(file_path):
    """Main function jo file extension check karke text nikalta hai."""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.pdf':
        raw_text = extract_text_from_pdf(file_path)
    elif ext == '.docx':
        raw_text = extract_text_from_docx(file_path)
    else:
        return None, "Unsupported file format"
    
    if not raw_text.strip():
        return None, "Could not extract text or file is empty"
        
    cleaned_text = clean_resume_text(raw_text)
    return cleaned_text, None
