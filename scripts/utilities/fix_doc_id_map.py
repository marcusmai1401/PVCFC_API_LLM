"""
Hotfix script to update doc_id_map.json with correct page counts from actual PDF files
"""
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    import pymupdf as fitz


def fix_doc_id_map(dry_run=False):
    """
    Update doc_id_map.json with actual page counts from PDF files

    Args:
        dry_run: If True, only show what would be changed without modifying the file
    """

    # Load doc_id_map
    doc_id_map_path = Path("artifacts/ingestion/doc_id_map.json")
    if not doc_id_map_path.exists():
        print(f"❌ ERROR: {doc_id_map_path} not found")
        return False

    # Create backup
    if not dry_run:
        backup_path = doc_id_map_path.with_suffix(
            f".json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        print(f"📦 Creating backup: {backup_path}")
        import shutil

        shutil.copy2(doc_id_map_path, backup_path)

    # Load map
    with open(doc_id_map_path, "r", encoding="utf-8") as f:
        doc_id_map = json.load(f)

    print(f"📂 Loaded doc_id_map with {len(doc_id_map)} entries")
    print("=" * 100)

    # Track changes
    updates = []
    errors = []
    no_change = 0

    # Update page counts
    for doc_id, doc_info in doc_id_map.items():
        if not isinstance(doc_info, dict):
            continue

        pdf_path = doc_info.get("pdf_path")
        expected_pages = doc_info.get("total_pages", 0)
        file_name = doc_info.get("file_name", "unknown")

        if not pdf_path:
            continue

        # Check if PDF exists
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            errors.append(
                {
                    "doc_id": doc_id,
                    "file_name": file_name,
                    "error": "PDF file not found",
                }
            )
            continue

        # Get actual page count
        try:
            with fitz.open(pdf_path) as doc:
                actual_pages = doc.page_count
        except Exception as e:
            errors.append({"doc_id": doc_id, "file_name": file_name, "error": str(e)})
            continue

        # Compare and update
        if actual_pages != expected_pages:
            update_info = {
                "doc_id": doc_id,
                "file_name": file_name,
                "old_pages": expected_pages,
                "new_pages": actual_pages,
                "difference": actual_pages - expected_pages,
            }
            updates.append(update_info)

            print(f"✏️  UPDATING: {file_name}")
            print(
                f"   Old: {expected_pages} pages → New: {actual_pages} pages (Δ {actual_pages - expected_pages:+d})"
            )

            if not dry_run:
                doc_info["total_pages"] = actual_pages
        else:
            no_change += 1

    # Print summary
    print("=" * 100)
    print("SUMMARY:")
    print(f"  ✅ Documents with correct page count: {no_change}")
    print(f"  ✏️  Documents to update: {len(updates)}")
    print(f"  ❌ Errors: {len(errors)}")
    print()

    if errors:
        print("=" * 100)
        print("ERRORS:")
        for err in errors:
            print(f"  ❌ {err['file_name']}: {err['error']}")
        print()

    if updates:
        print("=" * 100)
        print("DETAILED UPDATE LIST:")
        for i, update in enumerate(updates, 1):
            print(f"{i}. {update['file_name']}")
            print(
                f"   {update['old_pages']} → {update['new_pages']} pages (Δ {update['difference']:+d})"
            )
        print()

    # Save updated map
    if not dry_run and updates:
        print("=" * 100)
        print("💾 Saving updated doc_id_map.json...")
        with open(doc_id_map_path, "w", encoding="utf-8") as f:
            json.dump(doc_id_map, f, indent=2, ensure_ascii=False)
        print(f"✅ Successfully updated {len(updates)} documents in {doc_id_map_path}")
        print()
        print("⚠️  IMPORTANT: Restart backend service to load updated metadata!")
        print("   Command: ./start_backend.ps1 (or restart manually)")
    elif dry_run:
        print("=" * 100)
        print("🔍 DRY RUN MODE - No changes were made")
        print("   Run without --dry-run to apply changes")

    # Save update report
    if updates:
        report_file = Path("artifacts/doc_id_map_updates.json")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "dry_run": dry_run,
                    "summary": {
                        "total_documents": len(doc_id_map),
                        "no_change": no_change,
                        "updated": len(updates),
                        "errors": len(errors),
                    },
                    "updates": updates,
                    "errors": errors,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        print(f"📄 Update report saved to: {report_file}")

    return len(errors) == 0


if __name__ == "__main__":
    print("=" * 100)
    print("📝 doc_id_map.json Hotfix Script")
    print("=" * 100)
    print()

    # Check for dry-run flag
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("🔍 Running in DRY RUN mode (no changes will be made)")
        print()

    try:
        success = fix_doc_id_map(dry_run=dry_run)

        if success:
            print()
            print("=" * 100)
            print("✅ HOTFIX COMPLETED SUCCESSFULLY")
            print("=" * 100)
            sys.exit(0)
        else:
            print()
            print("=" * 100)
            print("⚠️  HOTFIX COMPLETED WITH ERRORS")
            print("=" * 100)
            sys.exit(1)

    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(2)
