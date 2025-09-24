"""
Test script to verify Gemini API connection in Streamlit app
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
env_path = project_root / ".env"
print(f"Loading .env from: {env_path}")
load_dotenv(env_path)

# Check environment variables
print("\n=== Environment Variables Check ===")
gemini_key = os.getenv("GEMINI_API_KEY")
if gemini_key:
    print(f"✅ GEMINI_API_KEY found: {gemini_key[:10]}...")
else:
    print("❌ GEMINI_API_KEY not found!")

print(f"LLM_PROVIDER: {os.getenv('LLM_PROVIDER')}")
print(f"LLM_MODEL_LIGHT: {os.getenv('LLM_MODEL_LIGHT')}")
print(f"LLM_MODEL_HEAVY: {os.getenv('LLM_MODEL_HEAVY')}")

# Test LLM Service
print("\n=== Testing LLM Service ===")
try:
    from app.services.llm import LLMService

    llm_service = LLMService()
    print("✅ LLM Service initialized successfully")

    # Try a simple generation
    response = llm_service.generate(
        prompt="Say 'Hello from Gemini!' in exactly 5 words.",
        temperature=0.1,
        max_tokens=50,
    )

    print(f"✅ Test generation successful!")
    print(f"Response: {response}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()

# Test Gemini integration module
print("\n=== Testing Gemini Integration Module ===")
try:
    from components.rag_gemini_integration import process_with_real_llm

    result = process_with_real_llm(
        query="What is the capital of France?",
        model="gemini-2.5-flash",
        max_tokens=100,
        temperature=0.1,
    )

    if result.get("error"):
        print(f"❌ Error in processing: {result['answer']}")
    else:
        print("✅ Gemini integration working!")
        print(f"Answer preview: {result['answer'][:200]}...")

except Exception as e:
    print(f"❌ Error importing/running integration: {e}")
    import traceback

    traceback.print_exc()

print("\n=== Test Complete ===")
