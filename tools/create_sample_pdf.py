"""
Create sample PDF files for testing
"""
import fitz  # PyMuPDF
from pathlib import Path
from loguru import logger


def create_simple_text_pdf(output_path: str = "data/raw/samples/sample_text.pdf"):
    """Create a simple text PDF for testing"""
    
    # Create output directory if not exists
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create new PDF
    doc = fitz.open()
    
    # Page 1: Title and introduction
    page1 = doc.new_page(width=595, height=842)  # A4 size
    
    # Add title (larger font)
    page1.insert_text(
        (50, 50),
        "Technical Document Sample",
        fontsize=20,
        fontname="Helvetica-Bold"
    )
    
    # Add subtitle
    page1.insert_text(
        (50, 80),
        "Equipment Specification KT06101",
        fontsize=14,
        fontname="Helvetica"
    )
    
    # Add paragraph
    page1.insert_text(
        (50, 120),
        "This is a sample technical document for testing the PDF processing pipeline.\n"
        "It contains various elements like headings, paragraphs, and technical data.",
        fontsize=11,
        fontname="Helvetica"
    )
    
    # Add section heading
    page1.insert_text(
        (50, 180),
        "1. Operating Parameters",
        fontsize=14,
        fontname="Helvetica-Bold"
    )
    
    # Add technical content
    page1.insert_text(
        (50, 210),
        "Maximum Operating Pressure: 25 bar\n"
        "Operating Temperature Range: -20°C to 150°C\n"
        "Flow Rate: 500 m³/h\n"
        "Power Consumption: 75 kW",
        fontsize=11,
        fontname="Helvetica"
    )
    
    # Page 2: More content
    page2 = doc.new_page(width=595, height=842)
    
    page2.insert_text(
        (50, 50),
        "2. Safety Instructions",
        fontsize=14,
        fontname="Helvetica-Bold"
    )
    
    page2.insert_text(
        (50, 80),
        "• Always wear appropriate PPE\n"
        "• Check pressure gauges before operation\n"
        "• Ensure proper ventilation\n"
        "• Follow lockout/tagout procedures",
        fontsize=11,
        fontname="Helvetica"
    )
    
    page2.insert_text(
        (50, 180),
        "3. Maintenance Schedule",
        fontsize=14,
        fontname="Helvetica-Bold"
    )
    
    page2.insert_text(
        (50, 210),
        "Daily: Visual inspection\n"
        "Weekly: Check oil levels\n"
        "Monthly: Replace filters\n"
        "Annually: Complete overhaul",
        fontsize=11,
        fontname="Helvetica"
    )
    
    # Save PDF
    doc.save(str(output_path))
    doc.close()
    
    logger.info(f"Created sample PDF: {output_path}")
    return str(output_path)


def create_mixed_pdf(output_path: str = "data/raw/samples/sample_mixed.pdf"):
    """Create a PDF with mixed content (text + images placeholder)"""
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    doc = fitz.open()
    
    # Page with text
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text(
        (50, 50),
        "P&ID Diagram Reference",
        fontsize=16,
        fontname="Helvetica-Bold"
    )
    
    page1.insert_text(
        (50, 100),
        "Equipment Tags:\n"
        "- KT06101: CO2 Compressor\n"
        "- PV-101: Pressure Valve\n"
        "- FT-205: Flow Transmitter",
        fontsize=11
    )
    
    # Draw a simple rectangle to simulate diagram
    rect = fitz.Rect(100, 200, 400, 400)
    page1.draw_rect(rect, color=(0, 0, 0), width=1)
    page1.insert_text((220, 300), "DIAGRAM AREA", fontsize=14)
    
    # Page 2: Mostly empty (simulating scanned page)
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text(
        (250, 400),
        "[Scanned Content]",
        fontsize=10,
        color=(0.5, 0.5, 0.5)
    )
    
    doc.save(str(output_path))
    doc.close()
    
    logger.info(f"Created mixed PDF: {output_path}")
    return str(output_path)


def create_datasheet_pdf(output_path: str = "data/raw/samples/sample_datasheet.pdf"):
    """Create a datasheet-style PDF with tables"""
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    
    # Title
    page.insert_text(
        (50, 50),
        "DATASHEET - KT06101 CO2 COMPRESSOR",
        fontsize=16,
        fontname="Helvetica-Bold"
    )
    
    # Specifications section
    page.insert_text(
        (50, 100),
        "Technical Specifications:",
        fontsize=12,
        fontname="Helvetica-Bold"
    )
    
    # Table-like content
    y_pos = 130
    specs = [
        ("Parameter", "Value", "Unit"),
        ("-" * 20, "-" * 20, "-" * 10),
        ("Model", "KT06101", "-"),
        ("Type", "Centrifugal", "-"),
        ("Capacity", "500", "m³/h"),
        ("Pressure", "25", "bar"),
        ("Temperature", "150", "°C"),
        ("Power", "75", "kW"),
        ("Weight", "2500", "kg"),
    ]
    
    for row in specs:
        line = f"{row[0]:<25} {row[1]:<20} {row[2]:<10}"
        page.insert_text((50, y_pos), line, fontsize=10, fontname="Courier")
        y_pos += 20
    
    # Notes section
    page.insert_text(
        (50, y_pos + 30),
        "Notes:",
        fontsize=12,
        fontname="Helvetica-Bold"
    )
    
    page.insert_text(
        (50, y_pos + 50),
        "1. All measurements at standard conditions\n"
        "2. Regular maintenance required every 2000 hours\n"
        "3. Use only approved lubricants",
        fontsize=10
    )
    
    doc.save(str(output_path))
    doc.close()
    
    logger.info(f"Created datasheet PDF: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    # Create all sample PDFs
    create_simple_text_pdf()
    create_mixed_pdf()
    create_datasheet_pdf()
    print("Sample PDFs created successfully!")
