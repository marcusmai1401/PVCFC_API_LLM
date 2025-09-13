# tools/extract_pilot.py
from pathlib import Path
import json
from app.rag.document_detector import DocumentDetector, PDFType
from app.rag.extractors.vector_extractor import VectorExtractor

src = Path("data/raw/phase1_pilot")
out = Path("data/processed")
out.mkdir(parents=True, exist_ok=True)

detector = DocumentDetector(sample_pages=5)
extractor = VectorExtractor()

print("=" * 60)
print("PDF EXTRACTION PILOT TEST")
print("=" * 60)

for pdf in src.glob("*.pdf"):
    print(f"\nProcessing: {pdf.name}")
    print("-" * 40)
    
    try:
        # Detect PDF type
        det = detector.detect_pdf_type(pdf)
        pdf_type = det["type"].value if hasattr(det["type"], "value") else str(det["type"])
        confidence = det.get('confidence', 0)
        
        print(f"Type: {pdf_type}")
        print(f"Confidence: {confidence:.2%}")
        print(f"Pages: {det.get('total_pages', 0)}")
        print(f"Vector/Scan pages: {det.get('vector_pages', 0)}/{det.get('scan_pages', 0)}")
        
        if pdf_type == "vector":
            print("Action: Extracting text...")
            res = extractor.extract_with_structure(pdf)
            
            # Save extraction result
            output_file = out / (pdf.stem + ".json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=2)
            
            # Print statistics
            stats = res.get('statistics', {})
            print(f"Extracted: {stats.get('total_blocks', 0)} blocks, {stats.get('total_characters', 0)} characters")
            print(f"Saved to: {output_file}")
            
        elif pdf_type == "scan":
            print("Action: Skipping (scan - OCR not implemented yet)")
            
        else:  # mixed
            print("Action: Processing as mixed document")
            print("Extracting vector pages only...")
            res = extractor.extract_with_structure(pdf)
            
            # Save extraction result
            output_file = out / (pdf.stem + "_mixed.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=2)
                
            stats = res.get('statistics', {})
            print(f"Extracted: {stats.get('total_blocks', 0)} blocks from vector pages")
            print(f"Saved to: {output_file}")
            
    except Exception as e:
        print(f"ERROR: {e}")
        
print("\n" + "=" * 60)
print("PILOT TEST COMPLETED")
print("=" * 60)
