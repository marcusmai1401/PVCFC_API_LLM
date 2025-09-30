"""
Example script demonstrating how to use Gemini API in the application
"""
import asyncio

import google.generativeai as genai

from app.core.config import settings
from app.services.llm import get_api_key_for, get_model_for, get_provider_for


def test_tier_configuration():
    """Test and display tier configuration"""
    print("=" * 60)
    print("TIER CONFIGURATION")
    print("=" * 60)

    # Test light tier
    light_provider = get_provider_for("light")
    light_model = get_model_for("light")
    print(f"Light Tier:")
    print(f"  Provider: {light_provider}")
    print(f"  Model: {light_model}")

    # Test heavy tier
    heavy_provider = get_provider_for("heavy")
    heavy_model = get_model_for("heavy")
    print(f"\nHeavy Tier:")
    print(f"  Provider: {heavy_provider}")
    print(f"  Model: {heavy_model}")

    # Get API key
    api_key = get_api_key_for("gemini")
    print(f"\nAPI Key: {api_key[:10]}... (configured)")
    print()


def simple_chat_example():
    """Simple chat example with both tiers"""
    print("=" * 60)
    print("SIMPLE CHAT EXAMPLE")
    print("=" * 60)

    # Configure API
    api_key = get_api_key_for("gemini")
    genai.configure(api_key=api_key)

    # Test prompt
    test_prompt = "Explain what a PLC is in 2 sentences for an industrial engineer."

    # Light tier (fast/cheap)
    print("\n1. LIGHT TIER (gemini-1.5-flash):")
    print("-" * 40)
    light_model = genai.GenerativeModel(get_model_for("light"))
    light_response = light_model.generate_content(test_prompt)
    print(f"Response: {light_response.text}")

    # Heavy tier (quality)
    print("\n2. HEAVY TIER (gemini-1.5-pro):")
    print("-" * 40)
    heavy_model = genai.GenerativeModel(get_model_for("heavy"))
    heavy_response = heavy_model.generate_content(test_prompt)
    print(f"Response: {heavy_response.text}")


def industrial_qa_example():
    """Industrial Q&A example"""
    print("\n" + "=" * 60)
    print("INDUSTRIAL Q&A EXAMPLE")
    print("=" * 60)

    api_key = get_api_key_for("gemini")
    genai.configure(api_key=api_key)

    # Use heavy tier for technical questions
    model = genai.GenerativeModel(get_model_for("heavy"))

    questions = [
        "What are the main differences between Modbus RTU and Modbus TCP?",
        "How do you calculate the proper size for a VFD for a 50HP motor?",
        "What safety standards apply to industrial control panels in Vietnam?",
    ]

    for i, question in enumerate(questions, 1):
        print(f"\nQ{i}: {question}")
        print("-" * 40)
        response = model.generate_content(question)
        print(
            f"A{i}: {response.text[:500]}..."
            if len(response.text) > 500
            else f"A{i}: {response.text}"
        )


def document_analysis_example():
    """Example of document analysis use case"""
    print("\n" + "=" * 60)
    print("DOCUMENT ANALYSIS EXAMPLE")
    print("=" * 60)

    api_key = get_api_key_for("gemini")
    genai.configure(api_key=api_key)

    # Simulate document content
    document_content = """
    TECHNICAL SPECIFICATION
    Equipment: Variable Frequency Drive
    Model: ABB ACS550-01-012A-4
    Power: 5.5 kW / 7.5 HP
    Input: 380-480V, 3-phase, 50/60Hz
    Output: 0-480V, 12A max
    Protection: IP21
    Communication: Modbus RTU, Profibus DP optional
    Features: Built-in PID controller, Energy optimizer, Safe torque off (STO)
    """

    # Use light tier for extraction
    model = genai.GenerativeModel(get_model_for("light"))

    prompt = f"""
    Extract the following information from this technical specification:
    1. Equipment type
    2. Manufacturer
    3. Model number
    4. Power rating
    5. Communication protocols

    Document:
    {document_content}

    Format the output as a JSON object.
    """

    print("Extracting information from technical document...")
    print("-" * 40)
    response = model.generate_content(prompt)
    print(f"Extracted Data:\n{response.text}")


def cost_comparison():
    """Show cost optimization strategy"""
    print("\n" + "=" * 60)
    print("COST OPTIMIZATION STRATEGY")
    print("=" * 60)

    print(
        """
    Recommended Usage Pattern:

    1. LIGHT TIER (gemini-1.5-flash) - Use for:
       ✓ Document parsing and extraction
       ✓ Simple Q&A and lookups
       ✓ Data formatting and transformation
       ✓ Development and testing
       Cost: ~$0.075 per 1M input tokens

    2. HEAVY TIER (gemini-1.5-pro) - Use for:
       ✓ Complex technical analysis
       ✓ Final customer-facing responses
       ✓ Critical decision support
       ✓ Multi-step reasoning tasks
       Cost: ~$3.50 per 1M input tokens

    💡 Using tiers appropriately can reduce costs by 80-90% while
       maintaining quality where it matters!
    """
    )


def main():
    """Run all examples"""
    print("\n🚀 GEMINI API USAGE EXAMPLES\n")

    try:
        # Show configuration
        test_tier_configuration()

        # Run examples
        simple_chat_example()
        industrial_qa_example()
        document_analysis_example()

        # Show cost strategy
        cost_comparison()

        print("\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Check your API key is valid")
        print("2. Check your internet connection")
        print("3. Verify you have API quota remaining")


if __name__ == "__main__":
    main()
