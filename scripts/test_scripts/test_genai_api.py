"""
Test correct usage of google-genai Part API
Version: 1.36.0
"""

print("Testing google-genai Part API...")

try:
    from google import genai
    from google.genai import types

    print("✓ Import successful")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    exit(1)

# Test 1: Part with text
print("\n[Test 1] Creating Part with text...")
try:
    # Try different methods
    methods = []

    # Method 1: Direct init with text kwarg
    try:
        part1 = types.Part(text="Test prompt text")
        methods.append(("types.Part(text=...)", "SUCCESS", part1))
    except Exception as e:
        methods.append(("types.Part(text=...)", f"FAILED: {e}", None))

    # Method 2: from_text() with no args
    try:
        part2 = types.Part.from_text()
        methods.append(
            ("types.Part.from_text()", "SUCCESS (but need to check if usable)", part2)
        )
    except Exception as e:
        methods.append(("types.Part.from_text()", f"FAILED: {e}", None))

    # Method 3: from_text() with text arg (old way - might fail)
    try:
        part3 = types.Part.from_text("Test prompt")
        methods.append(("types.Part.from_text('text')", "SUCCESS", part3))
    except Exception as e:
        methods.append(("types.Part.from_text('text')", f"FAILED: {e}", None))

    # Print results
    print("\nResults:")
    for method_name, status, obj in methods:
        print(f"  {method_name}: {status}")
        if obj:
            print(f"    Type: {type(obj)}")
            print(f"    Has text attr: {hasattr(obj, 'text')}")
            if hasattr(obj, "text"):
                print(f"    Text value: {getattr(obj, 'text', None)}")

    # Find working method
    working = [m for m in methods if "SUCCESS" in m[1] and m[2] is not None]
    if working:
        recommended = working[0]
        print(f"\n✓ RECOMMENDED METHOD: {recommended[0]}")
    else:
        print("\n✗ No working method found!")

except Exception as e:
    print(f"✗ Test 1 failed: {e}")
    import traceback

    traceback.print_exc()

# Test 2: Part with image/bytes
print("\n[Test 2] Creating Part with image data...")
try:
    fake_image = b"fake_image_bytes_data"
    mime_type = "image/png"

    methods = []

    # Method 1: from_bytes
    try:
        part = types.Part.from_bytes(data=fake_image, mime_type=mime_type)
        methods.append(
            ("types.Part.from_bytes(data=..., mime_type=...)", "SUCCESS", part)
        )
    except Exception as e:
        methods.append(
            ("types.Part.from_bytes(data=..., mime_type=...)", f"FAILED: {e}", None)
        )

    # Method 2: Direct init with inline_data
    try:
        part = types.Part(inline_data={"mime_type": mime_type, "data": fake_image})
        methods.append(("types.Part(inline_data={...})", "SUCCESS", part))
    except Exception as e:
        methods.append(("types.Part(inline_data={...})", f"FAILED: {e}", None))

    # Print results
    print("\nResults:")
    for method_name, status, obj in methods:
        print(f"  {method_name}: {status}")
        if obj:
            print(f"    Type: {type(obj)}")

    working = [m for m in methods if "SUCCESS" in m[1] and m[2] is not None]
    if working:
        recommended = working[0]
        print(f"\n✓ RECOMMENDED METHOD: {recommended[0]}")
    else:
        print("\n✗ No working method found!")

except Exception as e:
    print(f"✗ Test 2 failed: {e}")
    import traceback

    traceback.print_exc()

# Test 3: Content with parts
print("\n[Test 3] Creating Content with parts...")
try:
    text_part = types.Part(text="Hello")
    parts = [text_part]
    content = types.Content(role="user", parts=parts)
    print(f"✓ Content created successfully")
    print(f"  Role: {content.role}")
    print(f"  Parts count: {len(content.parts)}")
except Exception as e:
    print(f"✗ Test 3 failed: {e}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("Check the results above to determine correct API usage.")
print("The recommended methods will be used in the fix.")
