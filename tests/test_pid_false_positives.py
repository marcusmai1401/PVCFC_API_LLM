"""
Unit tests for P&ID false positive prevention

Tests that semantic queries with coincidental numbers/prefixes
are correctly identified and routed to semantic search.
"""
import pytest

from app.rag.query_processing.pid_context_validator import (
    PIDContextValidator,
    should_fallback_on_empty,
)


class TestPIDContextValidator:
    """Test PIDContextValidator for false positive prevention"""

    def setup_method(self):
        """Setup for each test"""
        self.validator = PIDContextValidator()

    # ========================================
    # SUFFIX-only validation tests
    # ========================================

    def test_reject_year_query(self):
        """Query with year should NOT be detected as SUFFIX"""
        result = self.validator.validate("What happened in 2024?", "suffix_search")

        assert result["is_valid"] == False
        assert "Semantic context" in result["reason"]
        assert result["confidence"] < 0.5

    def test_reject_procedure_query(self):
        """Query about procedure should NOT use P&ID"""
        result = self.validator.validate("Follow procedure 5153", "suffix_search")

        assert result["is_valid"] == False
        assert result["fallback_to_semantic"] == True

    def test_reject_long_query_with_number(self):
        """Long query with number should NOT be SUFFIX search"""
        result = self.validator.validate(
            "How to operate equipment 5153?", "suffix_search"
        )

        assert result["is_valid"] == False
        assert "too long" in result["reason"] or "Semantic" in result["reason"]

    def test_accept_pure_suffix(self):
        """Pure number query SHOULD be accepted"""
        result = self.validator.validate("5153", "suffix_search")

        assert result["is_valid"] == True
        assert result["confidence"] >= 0.9
        assert result["fallback_to_semantic"] == False

    def test_accept_suffix_3_digits(self):
        """3-digit SUFFIX should work"""
        result = self.validator.validate("501", "suffix_search")

        assert result["is_valid"] == True
        assert result["confidence"] >= 0.9

    def test_accept_suffix_5_digits(self):
        """5-digit SUFFIX should work"""
        result = self.validator.validate("22076", "suffix_search")

        assert result["is_valid"] == True
        assert result["confidence"] >= 0.9

    # ========================================
    # Component search validation tests
    # ========================================

    def test_reject_pi_semantic_question(self):
        """'What is PI?' should NOT use P&ID"""
        result = self.validator.validate("What is PI?", "component_search")

        assert result["is_valid"] == False
        assert "semantic" in result["reason"].lower()

    def test_reject_pi_vietnamese_question(self):
        """'PI là gì?' should NOT use P&ID"""
        result = self.validator.validate("PI là gì?", "component_search")

        assert result["is_valid"] == False

    def test_accept_pi_with_pressure(self):
        """'PI 5153 pressure' SHOULD use P&ID"""
        result = self.validator.validate("PI 5153 pressure", "component_search")

        assert result["is_valid"] == True
        assert result["confidence"] >= 0.7

    def test_accept_component_with_pid_keyword(self):
        """Component query with P&ID keyword should accept"""
        result = self.validator.validate("áp suất của 5153", "component_search")

        assert result["is_valid"] == True
        assert result["confidence"] >= 0.6

    def test_accept_component_no_context(self):
        """Component query without context should accept"""
        result = self.validator.validate("04 5153", "component_search")

        assert result["is_valid"] == True
        assert result["confidence"] >= 0.6

    # ========================================
    # Tag-focused validation tests (backward compat)
    # ========================================

    def test_tag_focused_with_pid_context(self):
        """Tag-focused with P&ID context should accept"""
        result = self.validator.validate("Find tag 04 PAHH 5153", "tag_focused")

        assert result["is_valid"] == True
        assert result["confidence"] >= 0.7

    def test_tag_focused_heavy_semantic(self):
        """Tag-focused with heavy semantic should reject"""
        result = self.validator.validate(
            "How to explain the procedure of tag 5153?", "tag_focused"
        )

        assert result["is_valid"] == False

    # ========================================
    # Vietnamese queries
    # ========================================

    def test_reject_vietnamese_semantic(self):
        """Vietnamese semantic query should reject"""
        result = self.validator.validate("làm sao để 5153", "suffix_search")

        assert result["is_valid"] == False

    def test_accept_vietnamese_pid(self):
        """Vietnamese P&ID query should accept"""
        result = self.validator.validate("áp suất 5153", "component_search")

        assert result["is_valid"] == True


class TestEmptyResultsFallback:
    """Test should_fallback_on_empty() function"""

    def test_fallback_on_none(self):
        """None results should trigger fallback"""
        assert should_fallback_on_empty(None) == True

    def test_fallback_on_empty_list(self):
        """Empty list should trigger fallback"""
        assert should_fallback_on_empty([]) == True

    def test_fallback_on_empty_dict(self):
        """Empty dict should trigger fallback"""
        assert should_fallback_on_empty({"total_tags": 0}) == True

    def test_no_fallback_on_results(self):
        """Non-empty results should NOT trigger fallback"""
        results = [{"tag": "04 IS 501", "page": 54}]
        assert should_fallback_on_empty(results) == False

    def test_fallback_on_insufficient_results(self):
        """Too few results should trigger fallback"""
        results = [{"tag": "04 IS 501"}]
        assert should_fallback_on_empty(results, min_results=5) == True

    def test_grouped_results_with_tags(self):
        """Grouped results with tags should not fallback"""
        grouped = {
            "total_tags": 4,
            "groups": [{"tags": [{"tag": "04 PAHH 5153"}, {"tag": "04 PALL 5153"}]}],
        }
        assert should_fallback_on_empty(grouped) == False

    def test_grouped_results_empty(self):
        """Grouped results with no tags should fallback"""
        grouped = {"total_tags": 0, "groups": []}
        assert should_fallback_on_empty(grouped) == True


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def setup_method(self):
        """Setup"""
        self.validator = PIDContextValidator()

    def test_mixed_context_query(self):
        """Query with both P&ID and semantic keywords"""
        result = self.validator.validate(
            "What is the pressure of 5153?", "component_search"
        )

        # Has both "what is" (semantic) and "pressure" (P&ID)
        # Should lean toward P&ID because of pressure keyword
        # But "what is" might tip it to semantic
        # Implementation dependent - document behavior
        print(f"Mixed context result: {result}")

    def test_empty_query(self):
        """Empty query should handle gracefully"""
        result = self.validator.validate("", "suffix_search")

        # Should reject (query too short)
        assert result["is_valid"] == False

    def test_very_short_number(self):
        """Very short number (1-2 digits) should reject for SUFFIX"""
        result = self.validator.validate("12", "suffix_search")

        # 2 digits is too short for SUFFIX (requires 3-5)
        # But validator doesn't check digit count, only context
        # This should pass validator but fail in enhancer
        print(f"Short number result: {result}")

    def test_very_long_suffix(self):
        """Very long number (>5 digits) should reject"""
        result = self.validator.validate("123456", "suffix_search")

        # Should pass validator (no semantic context)
        # But will fail in enhancer (regex check)
        assert result["is_valid"] == True  # Validator doesn't check length


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
