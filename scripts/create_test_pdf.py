"""
Create a simple test PDF for testing the PDF renderer
"""

import os
from pathlib import Path

try:
    import fitz
except ImportError:
    import pymupdf as fitz


def create_test_pdf():
    """Create a multi-page test PDF with various content using PyMuPDF."""

    # Ensure output directory exists
    output_dir = Path("data/test")
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = output_dir / "test_document.pdf"

    # Create a new PDF document
    doc = fitz.open()

    # Page 1: Title page with shapes
    page1 = doc.new_page(width=612, height=792)  # Letter size in points

    # Add title text
    page1.insert_text((306, 100), "Test PDF Document", fontsize=24, color=(0, 0, 0))
    page1.insert_text(
        (220, 150), "Generated for PDF Renderer Testing", fontsize=14, color=(0, 0, 0)
    )
    page1.insert_text((100, 250), "This is page 1 of the test document.", fontsize=12)
    page1.insert_text(
        (100, 280), "It contains basic text elements and shapes.", fontsize=12
    )

    # Draw shapes
    # Red rectangle
    page1.draw_rect(fitz.Rect(100, 400, 200, 500), color=(1, 0, 0), fill=(1, 0, 0))

    # Green circle
    page1.draw_circle(fitz.Point(300, 450), 50, color=(0, 1, 0), fill=(0, 1, 0))

    # Blue ellipse (approximated with rect)
    page1.draw_oval(fitz.Rect(400, 400, 500, 500), color=(0, 0, 1), fill=(0, 0, 1))

    # Page number
    page1.insert_text((512, 742), "Page 1", fontsize=10)

    # Page 2: Text content
    page2 = doc.new_page(width=612, height=792)

    page2.insert_text((100, 100), "Page 2: Text Content", fontsize=18, color=(0, 0, 0))

    y_position = 150
    text_lines = [
        "This is the second page of the test document.",
        "It contains multiple lines of text to test text extraction.",
        "",
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        "Ut enim ad minim veniam, quis nostrud exercitation ullamco.",
        "",
        "This page also tests:",
        "• Bullet points",
        "• Multiple paragraphs",
        "• Different text styles",
    ]

    for line in text_lines:
        if line:  # Skip empty lines for insert_text
            page2.insert_text((100, y_position), line, fontsize=12)
        y_position += 30

    # Page number
    page2.insert_text((512, 742), "Page 2", fontsize=10)

    # Page 3: Tables and data
    page3 = doc.new_page(width=612, height=792)

    page3.insert_text(
        (100, 100), "Page 3: Tables and Data", fontsize=18, color=(0, 0, 0)
    )

    # Table header
    page3.insert_text((100, 150), "Item", fontsize=12)
    page3.insert_text((200, 150), "Quantity", fontsize=12)
    page3.insert_text((300, 150), "Price", fontsize=12)

    # Draw line under header
    page3.draw_line(fitz.Point(100, 155), fitz.Point(380, 155))

    # Table data
    table_data = [
        ("Product A", "10", "$25.00"),
        ("Product B", "5", "$15.50"),
        ("Product C", "8", "$30.00"),
        ("Product D", "3", "$45.75"),
    ]

    y_pos = 180
    for item, qty, price in table_data:
        page3.insert_text((100, y_pos), item, fontsize=12)
        page3.insert_text((200, y_pos), qty, fontsize=12)
        page3.insert_text((300, y_pos), price, fontsize=12)
        y_pos += 25

    # Page number
    page3.insert_text((512, 742), "Page 3", fontsize=10)

    # Save the PDF
    doc.save(str(pdf_path))
    doc.close()

    print(f"Test PDF created: {pdf_path}")
    return str(pdf_path)


if __name__ == "__main__":
    # Create test PDF using PyMuPDF
    pdf_path = create_test_pdf()
    print(f"Successfully created test PDF at: {pdf_path}")
