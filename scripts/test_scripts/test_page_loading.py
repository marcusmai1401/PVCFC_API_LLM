#!/usr/bin/env python
"""
Test script để kiểm tra tính năng load full page PDF
"""
import json
from pathlib import Path


def check_doc_id_map():
    """Kiểm tra doc_id_map có tồn tại và có dữ liệu không"""
    map_path = Path("artifacts/ingestion/doc_id_map.json")
    if not map_path.exists():
        print("❌ Không tìm thấy doc_id_map.json")
        return False

    with open(map_path, "r", encoding="utf-8") as f:
        doc_map = json.load(f)

    print(f"✅ Tìm thấy doc_id_map với {len(doc_map)} entries")
    # In ra 3 entries mẫu
    for i, (doc_id, pdf_path) in enumerate(list(doc_map.items())[:3]):
        print(f"   - {doc_id[:40]}... -> {pdf_path}")
    return True


def test_pdf_loading():
    """Test load một trang PDF trực tiếp"""
    try:
        import re

        import fitz  # PyMuPDF

        # Lấy một PDF path mẫu từ doc_id_map
        map_path = Path("artifacts/ingestion/doc_id_map.json")
        with open(map_path, "r", encoding="utf-8") as f:
            doc_map = json.load(f)

        if not doc_map:
            print("❌ doc_id_map rỗng")
            return False

        # Lấy entry đầu tiên
        doc_id = list(doc_map.keys())[0]
        pdf_path = doc_map[doc_id]

        print(f"\n📄 Test load PDF: {pdf_path}")

        if not Path(pdf_path).exists():
            print(f"❌ PDF không tồn tại: {pdf_path}")
            return False

        # Load PDF và lấy text trang 1
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            print("❌ PDF không có trang nào")
            doc.close()
            return False

        page_obj = doc[0]  # Trang 1
        raw_text = page_obj.get_text()
        doc.close()

        # Clean text
        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
        text = re.sub(r"\s+", " ", "\n".join(lines)).strip()

        print(f"✅ Load được trang 1 với {len(text)} ký tự")
        print(f"   Preview: {text[:200]}...")
        return True

    except ImportError:
        print("❌ Không cài đặt PyMuPDF")
        return False
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return False


def test_retriever_upgrade():
    """Test xem retriever có upgrade text không"""
    try:
        from app.rag.retriever import HybridRetriever, RetrievalResult

        # Tạo mock result
        mock_result = RetrievalResult(
            chunk_id="test_chunk",
            text="This is a short chunk text",
            score=0.8,
            source="bm25",
            metadata={
                "doc_id": list(json.load(open("artifacts/ingestion/doc_id_map.json")))[
                    0
                ],
                "page": 1,
            },
            doc_id=list(json.load(open("artifacts/ingestion/doc_id_map.json")))[0],
            page=1,
            bbox=None,
            parent_id=None,
        )

        retriever = HybridRetriever()
        upgraded = retriever._upgrade_results_with_full_pages([mock_result])

        if upgraded and len(upgraded[0].text) > len(mock_result.text):
            print(f"\n✅ Retriever upgrade hoạt động:")
            print(f"   Text gốc: {len(mock_result.text)} chars")
            print(f"   Text sau upgrade: {len(upgraded[0].text)} chars")
            print(f"   Metadata: {upgraded[0].metadata.get('full_page', False)}")
            return True
        else:
            print("\n❌ Retriever không upgrade được text")
            return False

    except Exception as e:
        print(f"\n❌ Không test được retriever: {e}")
        return False


if __name__ == "__main__":
    print("🔍 KIỂM TRA TÍNH NĂNG LOAD FULL PAGE PDF\n")
    print("=" * 50)

    tests = [
        ("1. Kiểm tra doc_id_map", check_doc_id_map),
        ("2. Test load PDF trực tiếp", test_pdf_loading),
        ("3. Test retriever upgrade", test_retriever_upgrade),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n{name}:")
        result = test_func()
        results.append(result)

    print("\n" + "=" * 50)
    print("KẾT QUẢ:")
    for i, (name, result) in enumerate(zip([n for n, _ in tests], results)):
        status = "✅" if result else "❌"
        print(f"  {status} {name}")

    all_passed = all(results)
    if all_passed:
        print("\n🎉 TẤT CẢ TEST ĐỀU PASS! Logic đã đúng.")
    else:
        print("\n⚠️  Một số test fail, cần kiểm tra lại.")
