"""
🧪 Test Script for Streamlit UI Components

Verifies all UI components are working correctly.
"""

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_evaluation_viewer():
    """Test evaluation results viewer component."""
    print("✅ Testing Evaluation Results Viewer...")

    try:
        from components.evaluation_viewer import EvaluationResultsViewer

        viewer = EvaluationResultsViewer()

        # Test initialization
        assert viewer.results_dir.exists(), "Results directory should be created"

        # Test available results check
        results = viewer._get_available_results()
        print(f"  Found {len(results)} evaluation results")

        # Create sample result for testing
        sample_result = {
            "metrics": {
                "overall": {"total_questions": 50, "success_rate": 0.94},
                "retrieval": {"avg_recall_at_5": 0.85, "avg_precision_at_5": 0.92},
                "e2e": {"avg_citation_rate": 0.88, "avg_answer_quality": 0.82},
                "latency": {
                    "avg_total_latency_ms": 2300,
                    "p95_total_latency_ms": 4500,
                    "p99_total_latency_ms": 6000,
                },
            },
            "results": [
                {
                    "qa_id": "test_001",
                    "query": "What is RAG?",
                    "intent": "definition",
                    "generated_answer": "RAG stands for Retrieval-Augmented Generation...",
                    "citations": ["doc1.pdf", "doc2.md"],
                    "total_latency_ms": 2100,
                    "e2e_metrics": {"answer_quality": 0.85},
                    "retrieval_metrics": {"recall_at_5": 0.9},
                }
            ],
        }

        # Save test result
        test_file = viewer.results_dir / "test_result.json"
        with open(test_file, "w") as f:
            json.dump(sample_result, f)

        # Test loading
        loaded = viewer._load_evaluation_result(test_file)
        assert loaded is not None, "Should load test result"
        assert loaded["metrics"]["overall"]["total_questions"] == 50

        print("  ✅ Evaluation Viewer tests passed!")
        return True

    except Exception as e:
        print(f"  ❌ Evaluation Viewer test failed: {e}")
        traceback.print_exc()
        return False


def test_annotation_interface():
    """Test annotation interface component."""
    print("✅ Testing Annotation Interface...")

    try:
        from components.annotation_enhanced import (
            AnnotationManager,
            EnhancedAnnotationInterface,
        )

        # Test AnnotationManager
        manager = AnnotationManager()

        # Test data directory creation
        assert manager.data_dir.exists(), "Data directory should be created"

        # Test saving and loading QA dataset
        test_qa = {
            "qa_id": "test_qa_001",
            "query": "Test question",
            "intent": "definition",
            "expected_behavior": "Test behavior",
            "status": "pending",
        }

        manager.save_qa_dataset([test_qa])
        loaded_dataset = manager.load_qa_dataset()
        assert len(loaded_dataset) > 0, "Should load saved dataset"
        assert loaded_dataset[-1]["qa_id"] == "test_qa_001"

        # Test saving and loading annotations
        test_annotation = {
            "test_qa_001": {"relevance": "Good", "accuracy": "Correct", "flags": []}
        }

        manager.save_annotations(test_annotation)
        loaded_annotations = manager.load_annotations()
        assert "test_qa_001" in loaded_annotations, "Should load saved annotations"

        # Test interface initialization
        interface = EnhancedAnnotationInterface()
        assert interface.manager is not None, "Manager should be initialized"

        print("  ✅ Annotation Interface tests passed!")
        return True

    except Exception as e:
        print(f"  ❌ Annotation Interface test failed: {e}")
        traceback.print_exc()
        return False


def test_visualization_components():
    """Test visualization components."""
    print("✅ Testing Visualization Components...")

    try:
        import pandas as pd
        import plotly.express as px
        import plotly.graph_objects as go

        # Test plotly imports
        fig = go.Figure()
        assert fig is not None, "Should create plotly figure"

        # Test pandas integration
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        fig = px.scatter(df, x="x", y="y")
        assert fig is not None, "Should create plotly express figure"

        print("  ✅ Visualization tests passed!")
        return True

    except Exception as e:
        print(f"  ❌ Visualization test failed: {e}")
        print("  Make sure plotly is installed: pip install plotly")
        return False


def test_data_persistence():
    """Test data persistence functionality."""
    print("✅ Testing Data Persistence...")

    try:
        import json
        from pathlib import Path

        # Test directories
        data_dir = Path(__file__).parent.parent / "data" / "evaluation"
        results_dir = Path(__file__).parent.parent / "results" / "evaluation"

        data_dir.mkdir(parents=True, exist_ok=True)
        results_dir.mkdir(parents=True, exist_ok=True)

        assert data_dir.exists(), "Data directory should exist"
        assert results_dir.exists(), "Results directory should exist"

        # Test file operations
        test_data = {"test": "data", "timestamp": datetime.now().isoformat()}
        test_file = data_dir / "test_persistence.json"

        with open(test_file, "w") as f:
            json.dump(test_data, f)

        with open(test_file, "r") as f:
            loaded = json.load(f)

        assert loaded["test"] == "data", "Should persist and load data correctly"

        # Clean up
        test_file.unlink()

        print("  ✅ Data Persistence tests passed!")
        return True

    except Exception as e:
        print(f"  ❌ Data Persistence test failed: {e}")
        traceback.print_exc()
        return False


def test_integration():
    """Test integration between components."""
    print("✅ Testing Component Integration...")

    try:
        # Test import chain
        from streamlit_app.app import (
            show_annotation_page,
            show_evaluation_results,
            show_home_page,
            show_rag_demo,
        )

        # Test that functions are callable
        assert callable(show_home_page), "show_home_page should be callable"
        assert callable(show_annotation_page), "show_annotation_page should be callable"
        assert callable(
            show_evaluation_results
        ), "show_evaluation_results should be callable"

        print("  ✅ Integration tests passed!")
        return True

    except Exception as e:
        print(f"  ❌ Integration test failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("🧪 STREAMLIT UI COMPONENT TEST SUITE")
    print("=" * 60 + "\n")

    results = {
        "Evaluation Viewer": test_evaluation_viewer(),
        "Annotation Interface": test_annotation_interface(),
        "Visualization": test_visualization_components(),
        "Data Persistence": test_data_persistence(),
        "Integration": test_integration(),
    }

    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)

    for component, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {component}: {status}")

    total_passed = sum(results.values())
    total_tests = len(results)

    print("\n" + "-" * 60)
    print(f"  Total: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("\n🎉 All tests passed! The Streamlit UI is ready to use.")
        print("\nTo run the application:")
        print("  cd streamlit_app")
        print("  streamlit run app.py")
    else:
        print("\n⚠️ Some tests failed. Please check the errors above.")
        print("Common fixes:")
        print("  - Install missing dependencies: pip install streamlit plotly pandas")
        print("  - Check file paths and permissions")
        print("  - Ensure all component files are present")

    print("\n" + "=" * 60 + "\n")

    return total_passed == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
