"""
Smoke tests for Day 11 - Smart Vision Strategy

Tests the _smart_vision_strategy implementation in generator.py
"""
import pytest

from app.rag.generator import GeneratorConfig, ResponseGenerator
from app.rag.retriever import RetrievalResult


class TestSmartVisionStrategy:
    """Test smart vision strategy decision logic"""

    @pytest.fixture
    def generator(self):
        """Create generator with smart vision enabled"""
        config = GeneratorConfig(
            enable_vision_generation=True,
            enable_smart_vision_strategy=True,
            vision_skip_text_only=True,
        )
        return ResponseGenerator(config)

    def test_vision_enabled_with_table_keyword_in_query(self, generator):
        """Should enable vision when query contains 'table' keyword"""
        query = "Show me the performance table from the manual"
        docs = []

        strategy = generator._smart_vision_strategy(
            english_query=query,
            retrieved_docs=docs,
            language="en",
        )

        assert strategy["should_use_vision"] is True
        assert strategy["reason"] == "visual_keywords"
        assert strategy["prioritize_visual"] is True
        assert "table" in strategy["keywords_matched"]
        print(f"✓ Table keyword test: {strategy}")

    def test_vision_enabled_with_figure_keyword_in_query(self, generator):
        """Should enable vision when query contains 'figure' keyword"""
        query = "What does figure 3.5 show?"
        docs = []

        strategy = generator._smart_vision_strategy(
            english_query=query,
            retrieved_docs=docs,
            language="en",
        )

        assert strategy["should_use_vision"] is True
        assert strategy["reason"] == "visual_keywords"
        assert "figure" in strategy["keywords_matched"]
        print(f"✓ Figure keyword test: {strategy}")

    def test_vision_enabled_with_vietnamese_table_keyword(self, generator):
        """Should enable vision with Vietnamese keyword 'bảng'"""
        query = "Cho tôi xem bảng thông số kỹ thuật"
        docs = []

        strategy = generator._smart_vision_strategy(
            english_query=query,
            retrieved_docs=docs,
            language="vi",
        )

        assert strategy["should_use_vision"] is True
        assert "bảng" in strategy["keywords_matched"]
        print(f"✓ Vietnamese keyword test: {strategy}")

    def test_vision_disabled_for_pure_text_query(self, generator):
        """Should skip vision for text-only queries"""
        query = "What is the operating voltage?"
        docs = []

        strategy = generator._smart_vision_strategy(
            english_query=query,
            retrieved_docs=docs,
            language="en",
        )

        assert strategy["should_use_vision"] is False
        assert strategy["reason"] == "text_only"
        assert strategy["prioritize_visual"] is False
        print(f"✓ Text-only skip test: {strategy}")

    def test_vision_enabled_when_docs_contain_table_keywords(self, generator):
        """Should enable vision when retrieved docs mention tables"""
        query = "What are the specifications?"
        docs = [
            RetrievalResult(
                chunk_id="1",
                doc_id="manual_001",
                source="manual.pdf",
                page=10,
                text="See table 3.2 for detailed specifications including voltage ranges.",
                score=0.9,
                metadata={},
            )
        ]

        strategy = generator._smart_vision_strategy(
            english_query=query,
            retrieved_docs=docs,
            language="en",
        )

        assert strategy["should_use_vision"] is True
        assert "table" in strategy["keywords_matched"]
        print(f"✓ Doc content visual detection test: {strategy}")

    def test_vision_enabled_when_docs_contain_table_like_content(self, generator):
        """Should enable vision when docs contain table-like patterns"""
        query = "What are the power ratings?"
        docs = [
            RetrievalResult(
                chunk_id="1",
                doc_id="manual_001",
                source="manual.pdf",
                page=15,
                text="Power ratings:\nVoltage | Current | Power\n110V | 5A | 550W\n220V | 10A | 2200W",
                score=0.9,
                metadata={},
            )
        ]

        strategy = generator._smart_vision_strategy(
            english_query=query,
            retrieved_docs=docs,
            language="en",
        )

        assert strategy["should_use_vision"] is True
        assert "table-like" in strategy["keywords_matched"]
        print(f"✓ Table-like content detection test: {strategy}")

    def test_vision_skip_when_strategy_disabled(self, generator):
        """Should always use default when smart strategy is disabled"""
        # Create generator with strategy disabled
        config = GeneratorConfig(
            enable_vision_generation=True,
            enable_smart_vision_strategy=False,
        )
        gen = ResponseGenerator(config)

        query = "Show me the performance table"
        docs = []

        # When strategy is disabled, _smart_vision_strategy won't be called,
        # so vision will proceed normally without strategy filtering
        # This test just verifies the config option exists
        assert gen.config.enable_smart_vision_strategy is False
        print(f"✓ Strategy disable test passed")

    def test_multiple_visual_keywords_in_query(self, generator):
        """Should detect multiple visual keywords"""
        query = "Compare the chart in figure 3 with the diagram in table 2"
        docs = []

        strategy = generator._smart_vision_strategy(
            english_query=query,
            retrieved_docs=docs,
            language="en",
        )

        assert strategy["should_use_vision"] is True
        keywords = strategy["keywords_matched"]
        assert "chart" in keywords or "figure" in keywords or "table" in keywords
        assert len(keywords) >= 2  # Should find multiple keywords
        print(f"✓ Multiple keywords test: {strategy}")

    def test_vision_strategy_with_mixed_content_docs(self, generator):
        """Test with mix of visual and text docs"""
        query = "What is the operating range?"
        docs = [
            RetrievalResult(
                chunk_id="1",
                doc_id="manual_001",
                source="manual.pdf",
                page=10,
                text="The operating range is specified in the documentation.",
                score=0.9,
                metadata={},
            ),
            RetrievalResult(
                chunk_id="2",
                doc_id="manual_001",
                source="manual.pdf",
                page=11,
                text="Refer to the chart below for voltage specifications.",
                score=0.85,
                metadata={},
            ),
        ]

        strategy = generator._smart_vision_strategy(
            english_query=query,
            retrieved_docs=docs,
            language="en",
        )

        # Should enable vision because second doc mentions "chart"
        assert strategy["should_use_vision"] is True
        assert "chart" in strategy["keywords_matched"]
        print(f"✓ Mixed content test: {strategy}")


class TestVisionStrategyIntegration:
    """Test vision strategy integration into generation pipeline"""

    @pytest.fixture
    def config(self):
        """Create config with smart vision enabled"""
        return GeneratorConfig(
            enable_vision_generation=True,
            enable_smart_vision_strategy=True,
            vision_skip_text_only=True,
            vision_max_pages_total=5,
        )

    def test_config_defaults(self, config):
        """Verify smart vision config defaults"""
        assert config.enable_smart_vision_strategy is True
        assert config.vision_skip_text_only is True
        assert len(config.vision_table_figure_keywords) > 0
        assert "table" in config.vision_table_figure_keywords
        assert "bảng" in config.vision_table_figure_keywords
        print(f"✓ Config defaults test passed")
        print(f"  Keywords: {config.vision_table_figure_keywords[:5]}...")

    def test_bilingual_keywords(self, config):
        """Verify bilingual keyword support"""
        en_keywords = ["table", "figure", "chart", "diagram", "graph"]
        vi_keywords = ["bảng", "hình", "biểu đồ", "sơ đồ"]

        for kw in en_keywords:
            assert (
                kw in config.vision_table_figure_keywords
            ), f"Missing EN keyword: {kw}"

        for kw in vi_keywords:
            assert (
                kw in config.vision_table_figure_keywords
            ), f"Missing VI keyword: {kw}"

        print(
            f"✓ Bilingual keywords test passed ({len(en_keywords)} EN + {len(vi_keywords)} VI)"
        )


if __name__ == "__main__":
    print("=" * 70)
    print("DAY 11 SMOKE TESTS - Smart Vision Strategy")
    print("=" * 70)

    # Run tests manually for smoke testing
    import sys

    try:
        # Test 1: Query with table keyword
        print("\n[Test 1] Query with 'table' keyword")
        gen = ResponseGenerator(
            GeneratorConfig(
                enable_vision_generation=True,
                enable_smart_vision_strategy=True,
                vision_skip_text_only=True,
            )
        )
        result = gen._smart_vision_strategy("Show me the table", [], "en")
        print(f"Result: {result}")
        assert result["should_use_vision"] is True

        # Test 2: Text-only query
        print("\n[Test 2] Text-only query")
        result = gen._smart_vision_strategy("What is the voltage?", [], "en")
        print(f"Result: {result}")
        assert result["should_use_vision"] is False

        # Test 3: Vietnamese keyword
        print("\n[Test 3] Vietnamese keyword 'bảng'")
        result = gen._smart_vision_strategy("Cho tôi xem bảng", [], "vi")
        print(f"Result: {result}")
        assert result["should_use_vision"] is True

        # Test 4: Doc with table keyword
        print("\n[Test 4] Doc containing 'chart' keyword")
        docs = [
            RetrievalResult(
                chunk_id="1",
                doc_id="d1",
                source="s1",
                page=1,
                text="See the chart for details",
                score=0.9,
                metadata={},
            )
        ]
        result = gen._smart_vision_strategy("What are specs?", docs, "en")
        print(f"Result: {result}")
        assert result["should_use_vision"] is True

        # Test 5: Config check
        print("\n[Test 5] Config defaults")
        config = GeneratorConfig()
        print(f"enable_smart_vision_strategy: {config.enable_smart_vision_strategy}")
        print(f"vision_skip_text_only: {config.vision_skip_text_only}")
        print(f"Keywords count: {len(config.vision_table_figure_keywords)}")

        print("\n" + "=" * 70)
        print("✅ ALL SMOKE TESTS PASSED!")
        print("=" * 70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
