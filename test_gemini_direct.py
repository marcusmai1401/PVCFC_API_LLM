#!/usr/bin/env python3
"""Test Gemini API directly to debug issues"""

import os

from dotenv import load_dotenv

load_dotenv()


def test_gemini_api():
    """Test Gemini API directly"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ No GEMINI_API_KEY found in .env")
        return

    print(f"✓ API Key found: {api_key[:10]}...")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        print("✓ Client created")

        # Test simple generation
        model_name = "models/gemini-2.5-flash"
        prompt = "What is 2 + 2?"

        print(f"\nTesting model: {model_name}")
        print(f"Prompt: {prompt}")

        contents = [
            types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        ]

        config = types.GenerateContentConfig(temperature=0.7, max_output_tokens=100)

        response = client.models.generate_content(
            model=model_name, contents=contents, config=config
        )

        print(f"\nResponse type: {type(response)}")
        print(f"Has text attr: {hasattr(response, 'text')}")

        if hasattr(response, "text"):
            print(f"Response.text: {response.text}")
        else:
            print("No text attribute!")
            print(
                f"Available attributes: {[a for a in dir(response) if not a.startswith('_')]}"
            )

            if hasattr(response, "candidates"):
                print(f"Has candidates: {response.candidates}")
                if response.candidates:
                    for i, candidate in enumerate(response.candidates):
                        print(f"  Candidate {i}: {type(candidate)}")
                        if hasattr(candidate, "content"):
                            print(f"    Has content: {candidate.content}")
                            if hasattr(candidate.content, "parts"):
                                print(f"    Has parts: {candidate.content.parts}")
                                for j, part in enumerate(candidate.content.parts):
                                    print(f"      Part {j}: {part}")
                                    if hasattr(part, "text"):
                                        print(f"        Text: {part.text}")

        # Test with longer prompt
        print("\n" + "=" * 60)
        prompt2 = """Answer the following question based on the provided technical documents.

Question: What is the operating pressure of KT06101?

Context:
[Doc 1] CA.MAU FERTILIZER PLANT DOC NO. 07087-CP22-KT06101 WEC UREA UNIT Page 4/8 Rev. 0E SPECIAL PURPOSE STEAM TURBINE DATA SHEET 1 SERVICE: DRIVER FOR CO2 COMPRESSOR ITEM No. 2 KT06101 3 LUBRICATING AND CONTROL SYSTEM 3.13 Pressure switches Setting 3.13.1 Low lube oil pressure before startup

Instructions:
1. IMPORTANT: Start with a direct 1-2 sentence answer to the question
2. Cite sources using [Doc X] format

Answer:"""

        print(f"Testing with technical prompt (length: {len(prompt2)})")

        contents2 = [
            types.Content(role="user", parts=[types.Part.from_text(text=prompt2)])
        ]

        config2 = types.GenerateContentConfig(temperature=0.3, max_output_tokens=500)

        response2 = client.models.generate_content(
            model=model_name, contents=contents2, config=config2
        )

        if hasattr(response2, "text"):
            if response2.text:
                print(f"✓ Got response: {response2.text[:200]}...")
            else:
                print("❌ response2.text is None!")
                print(
                    f"Response2 attributes: {[a for a in dir(response2) if not a.startswith('_')]}"
                )

                # Check for blocked/filtered content
                if hasattr(response2, "candidates"):
                    print(f"Candidates: {response2.candidates}")
                    if response2.candidates:
                        for candidate in response2.candidates:
                            print(f"Candidate: {candidate}")
                            if hasattr(candidate, "finish_reason"):
                                print(f"  Finish reason: {candidate.finish_reason}")
                            if hasattr(candidate, "safety_ratings"):
                                print(f"  Safety ratings: {candidate.safety_ratings}")
        else:
            print("❌ No text attribute in response2")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_gemini_api()
