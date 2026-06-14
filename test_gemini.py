import os
from dotenv import load_dotenv
import google.generativeai as genai

def test_gemini():
    load_dotenv()
    key = os.getenv("GOOGLE_API_KEY")
    print(f"Testing key: {key[:10]}... (length {len(key)})")
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content("Hello")
        print("Success! Response text:", response.text)
    except Exception as e:
        print("Failed with error:", e)

if __name__ == "__main__":
    test_gemini()
