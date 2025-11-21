#!/usr/bin/env python3
"""
Script to check available Google Gemini models with current API key.
Usage: python scripts/utilities/check_gemini_models.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import google.generativeai as genai
from dotenv import load_dotenv


def check_gemini_models():
    """Check and list all available Gemini models that support generateContent."""
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY not found in .env file")
        return
    
    # Configure API
    genai.configure(api_key=api_key)
    
    print("=" * 80)
    print("🔍 Checking Available Gemini Models")
    print("=" * 80)
    print()
    
    try:
        # List all models
        all_models = genai.list_models()
        
        # Filter models that support generateContent
        generate_models = [
            model for model in all_models 
            if 'generateContent' in model.supported_generation_methods
        ]
        
        if not generate_models:
            print("⚠️  No models found that support generateContent")
            return
        
        print(f"✅ Found {len(generate_models)} models supporting generateContent:\n")
        
        # Print detailed information
        for i, model in enumerate(generate_models, 1):
            print(f"{'─' * 80}")
            print(f"Model #{i}")
            print(f"{'─' * 80}")
            print(f"  Name:          {model.name}")
            print(f"  Display Name:  {model.display_name}")
            print(f"  Version:       {getattr(model, 'version', 'N/A')}")
            print(f"  Description:   {getattr(model, 'description', 'N/A')[:100]}...")
            
            # Print generation methods
            methods = model.supported_generation_methods
            print(f"  Methods:       {', '.join(methods)}")
            
            # Print input/output token limits if available
            if hasattr(model, 'input_token_limit'):
                print(f"  Input Limit:   {model.input_token_limit:,} tokens")
            if hasattr(model, 'output_token_limit'):
                print(f"  Output Limit:  {model.output_token_limit:,} tokens")
            
            print()
        
        print("=" * 80)
        print("💡 Recommended models for production:")
        print("=" * 80)
        
        # Identify latest/best models
        pro_models = [m for m in generate_models if 'pro' in m.name.lower()]
        flash_models = [m for m in generate_models if 'flash' in m.name.lower()]
        
        if pro_models:
            print("\n🏆 Pro Models (Best performance):")
            for model in pro_models:
                print(f"  • {model.name}")
        
        if flash_models:
            print("\n⚡ Flash Models (Fast & efficient):")
            for model in flash_models:
                print(f"  • {model.name}")
        
        print()
        
    except Exception as e:
        print(f"❌ Error listing models: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_gemini_models()
