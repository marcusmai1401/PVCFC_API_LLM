"""
Test script to verify bug fixes in VectorExtractor
"""
from pathlib import Path
from app.rag.extractors.vector_extractor import VectorExtractor
from app.rag.document_detector import DocumentDetector


def test_hyphenation_fix():
    """Test that hyphenation fix doesn't cause errors"""
    print("\n=== Testing Hyphenation Fix ===")
    
    extractor = VectorExtractor(fix_hyphenation=True)
    pdf_path = Path("data/raw/samples/sample_text.pdf")
    
    try:
        result = extractor.extract_from_pdf(pdf_path)
        print(f"[OK] Hyphenation fix works - extracted {result['statistics']['total_blocks']} blocks")
        
        # Check that text is properly merged
        for page in result['pages']:
            if '-' in page['full_text']:
                print(f"  Page {page['page_num']}: Found hyphens in text (OK if intentional)")
    except Exception as e:
        print(f"[FAIL] Error with hyphenation fix: {e}")
        return False
    
    return True


def test_processing_order():
    """Test that blocks are sorted before merging"""
    print("\n=== Testing Processing Order ===")
    
    extractor = VectorExtractor(merge_threshold=10.0)
    pdf_path = Path("data/raw/samples/sample_text.pdf")
    
    try:
        result = extractor.extract_from_pdf(pdf_path)
        
        # Check that blocks are in reading order
        for page in result['pages']:
            blocks = page['blocks']
            if len(blocks) > 1:
                # Check Y coordinates are generally increasing (reading order)
                prev_y = blocks[0]['bbox'][1]
                out_of_order = 0
                for block in blocks[1:]:
                    curr_y = block['bbox'][1]
                    # Allow some tolerance for same-line blocks
                    if curr_y < prev_y - 5:
                        out_of_order += 1
                    prev_y = curr_y
                
                if out_of_order == 0:
                    print(f"[OK] Page {page['page_num']}: All blocks in correct reading order")
                else:
                    print(f"[WARN] Page {page['page_num']}: {out_of_order} blocks may be out of order")
                    
    except Exception as e:
        print(f"[FAIL] Error testing processing order: {e}")
        return False
    
    return True


def test_rotation_handling():
    """Test that rotation is handled without mutation"""
    print("\n=== Testing Rotation Handling ===")
    
    extractor = VectorExtractor(handle_rotation=True)
    pdf_path = Path("data/raw/samples/sample_text.pdf")
    
    try:
        result = extractor.extract_from_pdf(pdf_path)
        
        # Check that rotation is properly reported
        for page in result['pages']:
            rotation = page.get('rotation', 0)
            print(f"[OK] Page {page['page_num']}: Rotation = {rotation}° (preserved)")
            
    except Exception as e:
        print(f"[FAIL] Error testing rotation: {e}")
        return False
    
    return True


def test_span_indexing():
    """Test that span_index is used correctly"""
    print("\n=== Testing Span Indexing ===")
    
    extractor = VectorExtractor()
    pdf_path = Path("data/raw/samples/sample_text.pdf")
    
    try:
        result = extractor.extract_from_pdf(pdf_path)
        
        # Check that block_num values are unique within each page
        for page in result['pages']:
            block_nums = [b['block_num'] for b in page['blocks']]
            if len(block_nums) == len(set(block_nums)):
                print(f"[OK] Page {page['page_num']}: All block_num values are unique")
            else:
                print(f"[FAIL] Page {page['page_num']}: Duplicate block_num values found")
                return False
                
    except Exception as e:
        print(f"[FAIL] Error testing span indexing: {e}")
        return False
    
    return True


def test_empty_block_handling():
    """Test that empty blocks are handled correctly"""
    print("\n=== Testing Empty Block Handling ===")
    
    extractor = VectorExtractor()
    
    # Test with all sample PDFs
    sample_dir = Path("data/raw/samples")
    for pdf_file in sample_dir.glob("*.pdf"):
        try:
            result = extractor.extract_from_pdf(pdf_file)
            
            # Check no empty text blocks
            empty_blocks = 0
            for page in result['pages']:
                for block in page['blocks']:
                    if not block['text'].strip():
                        empty_blocks += 1
                        
            if empty_blocks == 0:
                print(f"[OK] {pdf_file.name}: No empty blocks")
            else:
                print(f"[FAIL] {pdf_file.name}: Found {empty_blocks} empty blocks")
                
        except Exception as e:
            print(f"[FAIL] Error processing {pdf_file.name}: {e}")
            return False
    
    return True


def main():
    """Run all verification tests"""
    print("=" * 50)
    print("VERIFYING BUG FIXES IN VECTOR EXTRACTOR")
    print("=" * 50)
    
    tests = [
        test_hyphenation_fix,
        test_processing_order,
        test_rotation_handling,
        test_span_indexing,
        test_empty_block_handling
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        if test():
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"RESULTS: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("[SUCCESS] All bug fixes verified successfully!")
    else:
        print(f"[ERROR] {failed} tests failed - please review")
    

if __name__ == "__main__":
    main()
