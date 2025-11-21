"""
Test Gemini API Simple
Minimal script to verify if Gemini Embedding API is working at all.
"""
import os
import sys
import time
from pathlib import Path
import google.generativeai as genai

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set Google Cloud credentials
credentials_path = PROJECT_ROOT / "credentials.json"
if credentials_path.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path)
    print(f"Credentials set: {credentials_path}")

from app.core.config import settings

def main():
    print("Testing Gemini Embedding API...")
    
    api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: No API Key found!")
        return

    print(f"API Key found (starts with): {api_key[:5]}...")
    
    genai.configure(api_key=api_key)
    
    model_name = "models/embedding-001"
    text = "Hello, this is a test of the emergency embedding system."
    
    print(f"Model: {model_name}")
    print(f"Text: {text}")
    print("Sending request...")
    
    start = time.time()
    try:
        result = genai.embed_content(
            model=model_name,
            content=text,
            task_type="retrieval_document"
        )
        elapsed = time.time() - start
        
        if 'embedding' in result:
            print(f"SUCCESS! Got embedding of length {len(result['embedding'])}")
            print(f"Time taken: {elapsed:.2f}s")
        else:
            print("FAILED: No embedding in response")
            print(result)
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    main()
