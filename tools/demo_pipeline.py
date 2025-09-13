"""
Demo Full Pipeline: Extract → Normalize → Convert → Chunk → Index
"""
from pathlib import Path
import json
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from app.rag.document_detector import DocumentDetector
from app.rag.extractors.vector_extractor import VectorExtractor
from app.rag.normalizers.text_normalizer import TextNormalizer
from app.rag.normalizers.unit_normalizer import UnitNormalizer
from app.rag.normalizers.tag_normalizer import TagNormalizer
from app.rag.converters.markdown_converter import MarkdownConverter
from app.rag.chunkers.hierarchical_chunker import HierarchicalChunker
from app.rag.indexers.bm25_indexer import BM25Indexer


def process_document(pdf_path: Path):
    """Process single document through full pipeline"""
    print(f"\n{'='*60}")
    print(f"Processing: {pdf_path.name}")
    print('='*60)
    
    # 1. Detect PDF type
    print("\n1. Detecting PDF type...")
    detector = DocumentDetector()
    detection = detector.detect_pdf_type(pdf_path)
    pdf_type = detection["type"].value if hasattr(detection["type"], "value") else str(detection["type"])
    print(f"   Type: {pdf_type} (confidence: {detection.get('confidence', 0):.2%})")
    
    if pdf_type == "scan":
        print("   [SKIP] Scan document - OCR not implemented")
        return None
    
    # 2. Extract text
    print("\n2. Extracting text...")
    extractor = VectorExtractor()
    extraction = extractor.extract_with_structure(pdf_path)
    stats = extraction.get('statistics', {})
    print(f"   Extracted: {stats.get('total_blocks', 0):,} blocks, {stats.get('total_characters', 0):,} characters")
    
    # 3. Normalize text
    print("\n3. Normalizing text...")
    text_normalizer = TextNormalizer()
    unit_normalizer = UnitNormalizer()
    tag_normalizer = TagNormalizer()
    
    normalized_blocks = 0
    for page in extraction['pages']:
        for block in page['blocks']:
            original = block['text']
            # Apply normalizations
            block['text'] = text_normalizer.normalize(block['text'])
            block['text'] = unit_normalizer.normalize(block['text'])
            
            if original != block['text']:
                normalized_blocks += 1
    
    print(f"   Normalized {normalized_blocks} blocks")
    
    # Extract tags
    all_text = ' '.join(page['full_text'] for page in extraction['pages'])
    tags = tag_normalizer.extract_tags(all_text[:50000])  # Sample first 50k chars
    print(f"   Found {len(tags)} equipment tags")
    
    # 4. Convert to Markdown
    print("\n4. Converting to Markdown...")
    converter = MarkdownConverter(preserve_bbox=False, preserve_fonts=False)
    md_result = converter.convert_with_structure(extraction)
    markdown = md_result['markdown']
    structure = md_result['structure']
    print(f"   Markdown length: {len(markdown):,} characters")
    print(f"   Headings found: {len(structure['headings'])}")
    
    # Save markdown
    output_dir = Path("data/processed/markdown")
    output_dir.mkdir(parents=True, exist_ok=True)
    md_file = output_dir / f"{pdf_path.stem}.md"
    converter.save_markdown(markdown, md_file, structure)
    print(f"   Saved to: {md_file}")
    
    # 5. Create chunks
    print("\n5. Creating chunks...")
    chunker = HierarchicalChunker(
        max_chunk_size=500,  # tokens
        chunk_overlap=50,
        use_token_count=True
    )
    
    doc_id = pdf_path.stem.replace(' ', '_')[:20]
    chunks = chunker.chunk_markdown(markdown, doc_id=doc_id)
    
    chunk_stats = chunker.get_chunk_statistics(chunks)
    print(f"   Created {chunk_stats['total_chunks']} chunks")
    print(f"   Avg chunk size: {chunk_stats['avg_chunk_size']:.1f} tokens")
    print(f"   Size range: {chunk_stats['min_chunk_size']}-{chunk_stats['max_chunk_size']} tokens")
    
    return chunks


def main():
    """Run demo on sample files"""
    # Process vector PDFs
    pdf_files = [
        Path("data/raw/phase1_pilot/Data Sheet for CO2 Compressor Steam Turbine.rev0E.pdf"),
        # Skip large P&ID for demo (117 pages takes time)
        # Path("data/raw/phase1_pilot/01. P&ID Ammonia Unit Rev12 (04000).pdf"),
    ]
    
    all_chunks = []
    
    for pdf_file in pdf_files:
        if pdf_file.exists():
            chunks = process_document(pdf_file)
            if chunks:
                all_chunks.extend(chunks)
    
    if not all_chunks:
        print("\nNo chunks created (all documents were scans)")
        return
    
    # 6. Build search index
    print(f"\n{'='*60}")
    print("6. Building BM25 Search Index")
    print('='*60)
    
    indexer = BM25Indexer()
    chunk_dicts = [chunk.to_dict() for chunk in all_chunks]
    indexer.build_index(chunk_dicts)
    
    index_stats = indexer.get_statistics()
    print(f"   Documents indexed: {index_stats['num_documents']}")
    print(f"   Total tokens: {index_stats['total_tokens']:,}")
    print(f"   Unique tokens: {index_stats['unique_tokens']:,}")
    
    # Save index
    index_dir = Path("artifacts/index/bm25")
    indexer.save_index(index_dir)
    print(f"   Index saved to: {index_dir}")
    
    # 7. Test search
    print(f"\n{'='*60}")
    print("7. Testing Search")
    print('='*60)
    
    queries = [
        "steam turbine",
        "CO2 compressor",
        "temperature",
        "pressure",
        "KT06101"
    ]
    
    for query in queries:
        print(f"\nQuery: '{query}'")
        results = indexer.search(query, top_k=3)
        
        if results:
            for i, result in enumerate(results, 1):
                print(f"  {i}. Score: {result['score']:.2f}")
                print(f"     Text: {result['text'][:100]}...")
                if result['metadata'].get('heading'):
                    print(f"     Section: {result['metadata']['heading']}")
        else:
            print("  No results found")
    
    print(f"\n{'='*60}")
    print("PIPELINE DEMO COMPLETED SUCCESSFULLY!")
    print('='*60)
    print("\nSummary:")
    print(f"  - PDF type detection")
    print(f"  - Text extraction")
    print(f"  - Text normalization")
    print(f"  - Markdown conversion")
    print(f"  - Hierarchical chunking")
    print(f"  - BM25 index building")
    print(f"  - Search functionality")
    print("\nAll Phase 1 components working correctly!")


if __name__ == "__main__":
    main()
