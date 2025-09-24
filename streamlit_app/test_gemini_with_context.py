"""
Test Gemini response with actual retrieved context
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

from app.services.llm_client import GeminiClient

# The actual content retrieved from BM25
context = """[Document 1 - Data Sheet for CO2 Compressor Steam Turbine.rev0E.pdf]:
CA.MAU FERTILIZER PLANT DOC NO. 07087-CP22-KT06101 WEC UREA UNIT Page 1/8 Rev. 0E SPECIAL PURPOSE STEAM TURBINE DATA SHEET 1 Unit: UREA SERVICE: ITEM No. 2 Supplier; KT06101 3 Quantity: 1 DRIVER FOR CO2 COMPRESSOR 4 Applicable to: 5 Type: Extraction-induction Condensate Turbine Model: Serial No.: 6 Driven equipment: CO2 COMPRESSOR ○-?Direct drive ○-<Gear 7 Note : ○-<Indicates information to be completed by purchaser ○-¡By manufacturer 8 PERFORMANCE 9 OPERATING POINTS SHAFT INLETï¼^saturated steamï¼% EXTRACTION/INJECTION EXHAUST 10 ○-<○-¡(As applicable) Power kW Speed RPM Flow Kg/h Press. MPa A Temp. ℃ Flow Kg/h Press. Bar A Temp. ℃ Press/tem p Bar A /℃ 11 Rated 12 Normal 0.15 13 Minimum 14 Piping design 15 ○-¡Steam rate Normal: Kg/kW.h Rated: Kg/kW.h Extraction ○-?Controlled ○-<Uncontrolled 16 ○-¡Heat rate Normal: MJ/kW.h Rated: MJ/kW.h Injection ○-?Controlled ○-<Uncontrolled
---End of Document 1---"""

query = "Give me some basic knowledge about CO2 compressor in SPECIAL PURPOSE STEAM TURBINE DATA SHEET"

prompt = f"""You have access to the following technical documents:

{context}

User Question: {query}

Instructions:
1. Answer based ONLY on the information in the documents above
2. If the answer is in the documents, provide specific details
3. If the answer is NOT in the documents, say "The provided documents do not contain information about [topic]"
4. Cite document numbers when referencing information

Answer:"""

print("Testing Gemini with actual context...")
print("=" * 60)
print(f"Query: {query}")
print("-" * 60)

gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    print("ERROR: GEMINI_API_KEY not found")
else:
    client = GeminiClient(api_key=gemini_api_key, model="gemini-2.0-flash-exp")

    try:
        response = client.generate(prompt=prompt, temperature=0.3, max_tokens=500)

        if hasattr(response, "content"):
            answer = response.content
        else:
            answer = str(response)

        print("Gemini Response:")
        print(answer)

    except Exception as e:
        print(f"Error: {e}")
