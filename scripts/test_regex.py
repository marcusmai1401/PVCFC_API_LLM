import re


def clean_text_original(text):
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if line:
            cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()


def clean_text_fixed(text):
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if line:
            # Collapse multiple spaces within the line
            line = re.sub(r"[ \t]+", " ", line)
            cleaned_lines.append(line)

    # Join with newlines
    text = "\n".join(cleaned_lines)
    return text


sample = """
Table Header 1    Header 2
Row 1 Col 1       Row 1 Col 2

Row 2 Col 1       Row 2 Col 2
"""

print("--- Original ---")
print(f"'{clean_text_original(sample)}'")
print("\n--- Fixed ---")
print(f"'{clean_text_fixed(sample)}'")
