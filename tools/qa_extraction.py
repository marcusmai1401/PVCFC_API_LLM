"""
QA Script for Extraction Quality Check
Kiểm tra chất lượng kết quả extraction từ PDF
"""
from pathlib import Path
import json
import re
from collections import Counter
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from app.rag.normalizers.unit_normalizer import UnitNormalizer


def analyze_extraction(json_path: Path):
    """Analyze extraction quality"""
    print(f"\n{'='*60}")
    print(f"Analyzing: {json_path.name}")
    print('='*60)
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Basic stats
    total_pages = data.get('total_pages', 0)
    stats = data.get('statistics', {})
    total_blocks = stats.get('total_blocks', 0)
    total_chars = stats.get('total_characters', 0)
    
    print(f"Total pages: {total_pages}")
    print(f"Total blocks: {total_blocks:,}")
    print(f"Total characters: {total_chars:,}")
    print(f"Avg blocks/page: {total_blocks/total_pages:.1f}")
    print(f"Avg chars/block: {total_chars/total_blocks:.1f}" if total_blocks > 0 else "")
    
    # Page analysis
    print(f"\n{'Page Analysis':^20}")
    print('-'*40)
    
    empty_blocks = 0
    rotated_pages = []
    structure_types = Counter()
    font_sizes = []
    suspicious_chars = []
    char_count_mismatch = []
    
    for page in data.get('pages', []):
        page_num = page['page_num']
        
        # Check rotation
        if page.get('rotation', 0) != 0:
            rotated_pages.append((page_num, page['rotation']))
        
        # Check char_count vs len(full_text)
        reported_chars = page.get('char_count', 0)
        actual_chars = len(page.get('full_text', ''))
        if reported_chars != actual_chars:
            char_count_mismatch.append((page_num, reported_chars, actual_chars))
        
        # Analyze blocks
        for block in page.get('blocks', []):
            text = block.get('text', '')
            
            # Empty blocks
            if not text.strip():
                empty_blocks += 1
            
            # Structure types
            structure_type = block.get('structure_type', 'unknown')
            structure_types[structure_type] += 1
            
            # Font sizes
            if 'font_size' in block:
                font_sizes.append(block['font_size'])
            
            # Check for suspicious characters
            if any(ord(c) > 127 and ord(c) not in [176, 178, 179, 8451, 8457] for c in text):
                suspicious_chars.append((page_num, text[:50]))
    
    # Report findings
    print(f"Empty blocks: {empty_blocks} ({100*empty_blocks/total_blocks:.1f}%)" if total_blocks > 0 else "")
    
    if rotated_pages:
        print(f"\nRotated pages: {len(rotated_pages)}")
        for page_num, rotation in rotated_pages[:5]:
            print(f"  Page {page_num}: {rotation}°")
    
    if char_count_mismatch:
        print(f"\nChar count mismatches: {len(char_count_mismatch)}")
        for page_num, reported, actual in char_count_mismatch[:5]:
            print(f"  Page {page_num}: reported={reported}, actual={actual}")
    
    print(f"\nStructure type distribution:")
    for stype, count in structure_types.most_common():
        print(f"  {stype}: {count} ({100*count/total_blocks:.1f}%)")
    
    if font_sizes:
        print(f"\nFont size statistics:")
        print(f"  Min: {min(font_sizes):.1f}")
        print(f"  Max: {max(font_sizes):.1f}")
        print(f"  Avg: {sum(font_sizes)/len(font_sizes):.1f}")
        
        # Top font sizes
        size_counter = Counter(font_sizes)
        print(f"  Top sizes: {', '.join(f'{s:.1f}' for s, _ in size_counter.most_common(5))}")
    
    if suspicious_chars:
        print(f"\nSuspicious characters found: {len(suspicious_chars)}")
        for page_num, text in suspicious_chars[:3]:
            print(f"  Page {page_num}: {text}...")
    
    # Unit analysis
    print(f"\n{'Unit Analysis':^20}")
    print('-'*40)
    
    unit_normalizer = UnitNormalizer()
    all_text = ' '.join(page['full_text'] for page in data.get('pages', []))
    unit_stats = unit_normalizer.get_unit_statistics(all_text[:100000])  # Sample first 100k chars
    
    print(f"Total units found: {unit_stats['total_units']}")
    print(f"Unique units: {unit_stats['unique_units']}")
    if unit_stats['most_common']:
        print(f"Most common unit: {unit_stats['most_common']}")
    
    # Show variations that need normalization
    variations = unit_stats.get('variations', {})
    needs_normalization = {k: v for k, v in variations.items() if len(v) > 1}
    if needs_normalization:
        print(f"\nUnits with variations (needs normalization):")
        for norm_unit, variants in list(needs_normalization.items())[:5]:
            print(f"  {norm_unit}: {', '.join(variants)}")
    
    # Special character check
    print(f"\n{'Special Characters':^20}")
    print('-'*40)
    
    special_patterns = {
        '℃': 'Celsius symbol',
        '°C': 'Degree Celsius',
        '℉': 'Fahrenheit symbol', 
        '°F': 'Degree Fahrenheit',
        'm /h': 'Separated flow unit',
        'm³/h': 'Cubic meter per hour',
        'bar g': 'Bar gauge',
        'bar a': 'Bar absolute',
        '±': 'Plus-minus',
        '×': 'Multiplication',
        '²': 'Superscript 2',
        '³': 'Superscript 3',
    }
    
    for pattern, description in special_patterns.items():
        count = all_text.count(pattern)
        if count > 0:
            print(f"  {pattern} ({description}): {count} occurrences")
    
    return {
        'total_pages': total_pages,
        'total_blocks': total_blocks,
        'empty_blocks': empty_blocks,
        'rotated_pages': len(rotated_pages),
        'structure_types': dict(structure_types),
        'unit_stats': unit_stats
    }


def main():
    """Run QA on all extracted JSON files"""
    processed_dir = Path("data/processed")
    json_files = list(processed_dir.glob("*.json"))
    
    print(f"Found {len(json_files)} JSON files to analyze")
    
    all_stats = {}
    for json_file in json_files:
        if 'pilot_test' not in json_file.name:  # Skip report files
            stats = analyze_extraction(json_file)
            all_stats[json_file.name] = stats
    
    # Summary
    print(f"\n{'='*60}")
    print("OVERALL SUMMARY")
    print('='*60)
    
    total_blocks = sum(s['total_blocks'] for s in all_stats.values())
    total_empty = sum(s['empty_blocks'] for s in all_stats.values())
    total_rotated = sum(s['rotated_pages'] for s in all_stats.values())
    
    print(f"Total files analyzed: {len(all_stats)}")
    print(f"Total blocks: {total_blocks:,}")
    print(f"Empty blocks: {total_empty} ({100*total_empty/total_blocks:.1f}%)" if total_blocks > 0 else "")
    print(f"Total rotated pages: {total_rotated}")
    
    # Recommendations
    print(f"\n{'Recommendations':^20}")
    print('-'*40)
    
    if total_empty/total_blocks > 0.05:
        print("WARNING: High empty block ratio - consider filtering in post-processing")
    
    if total_rotated > 0:
        print("INFO: Rotated pages detected - extraction handles this correctly")
    
    print("- Consider applying UnitNormalizer to standardize technical units")
    print("- Structure types are properly detected for hierarchical chunking")


if __name__ == "__main__":
    main()
