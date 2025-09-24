#!/usr/bin/env python3
"""
Generate synthetic QA pairs from processed documents.
Creates diverse questions for testing RAG pipeline without needing full golden dataset.
"""
import argparse
import json

# Add project root to path
import os
import random
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from loguru import logger


@dataclass
class QACandidate:
    """A candidate QA pair."""

    id: str
    query: str
    doc_hints: List[str]  # Expected document IDs
    expected_answer_snippet: Optional[str] = None
    expected_citations: Optional[List[Dict[str, Any]]] = None
    language: str = "vi"
    category: str = "lookup"  # lookup, locate, report, negative, ambiguous
    type: str = "factual"  # factual, procedural, safety, troubleshooting
    difficulty: str = "medium"  # easy, medium, hard
    confidence: float = 1.0  # Confidence in this QA pair
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return asdict(self)


class DocumentAnalyzer:
    """Analyze processed documents to extract entities and content."""

    def __init__(self):
        self.equipment_ids = set()
        self.valve_tags = set()
        self.instrument_tags = set()
        self.line_numbers = set()
        self.parameters = set()
        self.values = {}  # parameter -> values
        self.procedures = []
        self.safety_items = []

    def analyze_document(self, doc_data: Dict[str, Any], doc_id: str) -> Dict[str, Any]:
        """Analyze a single document and extract entities."""
        logger.info(f"Analyzing document: {doc_id}")

        # Extract all text blocks
        all_text = []
        for page in doc_data.get("pages", []):
            for block in page.get("blocks", []):
                text = block.get("text", "").strip()
                if text:
                    all_text.append(text)

        # Combine all text for analysis
        full_text = " ".join(all_text)

        # Extract entities using regex patterns
        self._extract_equipment_ids(full_text)
        self._extract_valve_tags(full_text)
        self._extract_instrument_tags(full_text)
        self._extract_line_numbers(full_text)
        self._extract_parameters(full_text)
        self._extract_procedures(all_text)
        self._extract_safety_items(all_text)

        # Return summary
        return {
            "doc_id": doc_id,
            "total_pages": doc_data.get("total_pages", 0),
            "total_blocks": sum(
                len(page.get("blocks", [])) for page in doc_data.get("pages", [])
            ),
            "equipment_ids": list(self.equipment_ids),
            "valve_tags": list(self.valve_tags)[:10],  # Limit for brevity
            "parameters_found": len(self.parameters),
            "procedures_found": len(self.procedures),
        }

    def _extract_equipment_ids(self, text: str):
        """Extract equipment IDs like KT06101, FT-101, etc."""
        # Pattern for equipment IDs: 2-3 letters + 5-6 digits
        patterns = [
            r"\b[A-Z]{2,3}\d{5,6}\b",  # KT06101, FT12345
            r"\b[A-Z]{2,3}-\d{3,5}\b",  # KT-101, FT-1001
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            self.equipment_ids.update(matches)

    def _extract_valve_tags(self, text: str):
        """Extract valve tags like XV-101, PV-201, etc."""
        pattern = r"\b[A-Z]{1,3}V-?\d{3,5}\b"
        matches = re.findall(pattern, text)
        self.valve_tags.update(matches)

    def _extract_instrument_tags(self, text: str):
        """Extract instrument tags like PT-101, TT-201, etc."""
        patterns = [
            r"\b[PTFILQ]T-?\d{3,5}\b",  # PT-101, TT-201, etc.
            r"\b[PTFILQ]I-?\d{3,5}\b",  # PI-101, TI-201, etc.
            r"\b[PTFILQ]C-?\d{3,5}\b",  # PC-101, TC-201, etc.
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            self.instrument_tags.update(matches)

    def _extract_line_numbers(self, text: str):
        """Extract line numbers like 4"-HC-10001."""
        pattern = r'\b\d+["\s]*-[A-Z]{2,4}-\d{4,6}\b'
        matches = re.findall(pattern, text)
        self.line_numbers.update(matches)

    def _extract_parameters(self, text: str):
        """Extract parameters and their values."""
        # Common technical parameters
        param_patterns = {
            "pressure": r"(\d+(?:\.\d+)?)\s*(bar|psi|kPa|MPa)",
            "temperature": r"(\d+(?:\.\d+)?)\s*(°C|K|°F)",
            "flow": r"(\d+(?:\.\d+)?)\s*(m³/h|kg/h|l/h|m3/h)",
            "power": r"(\d+(?:\.\d+)?)\s*(kW|MW|HP|hp)",
            "voltage": r"(\d+(?:\.\d+)?)\s*(V|kV|mV)",
            "current": r"(\d+(?:\.\d+)?)\s*(A|mA|kA)",
            "speed": r"(\d+(?:\.\d+)?)\s*(rpm|m/s|km/h)",
        }

        for param, pattern in param_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                self.parameters.add(param)
                self.values[param] = matches[:5]  # Keep first 5 values

    def _extract_procedures(self, text_blocks: List[str]):
        """Extract procedural text (steps, instructions)."""
        procedure_indicators = [
            "step",
            "procedure",
            "instruction",
            "operation",
            "bước",
            "quy trình",
            "hướng dẫn",
            "vận hành",
        ]

        for block in text_blocks:
            lower_block = block.lower()
            if any(indicator in lower_block for indicator in procedure_indicators):
                if len(block) > 50 and len(block) < 300:  # Reasonable length
                    self.procedures.append(block.strip())

    def _extract_safety_items(self, text_blocks: List[str]):
        """Extract safety-related content."""
        safety_indicators = [
            "safety",
            "warning",
            "caution",
            "danger",
            "hazard",
            "an toàn",
            "cảnh báo",
            "nguy hiểm",
            "rủi ro",
        ]

        for block in text_blocks:
            lower_block = block.lower()
            if any(indicator in lower_block for indicator in safety_indicators):
                if len(block) > 30 and len(block) < 200:
                    self.safety_items.append(block.strip())


class QATemplateEngine:
    """Generate QA pairs using templates and extracted entities."""

    def __init__(self, analyzer: DocumentAnalyzer):
        self.analyzer = analyzer
        self.qa_candidates = []
        self.id_counter = 1

    def generate_all_qa(self) -> List[QACandidate]:
        """Generate all types of QA pairs."""
        logger.info("Generating QA pairs from templates...")

        # Generate different categories
        self._generate_factual_lookup()
        self._generate_entity_location()
        self._generate_procedural()
        self._generate_safety()
        self._generate_troubleshooting()
        self._generate_negative_cases()
        self._generate_ambiguous_cases()

        logger.info(f"Generated {len(self.qa_candidates)} QA candidates")
        return self.qa_candidates

    def _next_id(self) -> str:
        """Get next QA ID."""
        qa_id = f"Q{self.id_counter:04d}"
        self.id_counter += 1
        return qa_id

    def _add_qa(self, query: str, doc_hints: List[str], **kwargs):
        """Add a QA candidate."""
        qa = QACandidate(id=self._next_id(), query=query, doc_hints=doc_hints, **kwargs)
        self.qa_candidates.append(qa)

    def _generate_factual_lookup(self):
        """Generate factual lookup questions."""
        templates = [
            # Equipment specifications
            (
                "Áp suất vận hành của {equipment} là bao nhiêu?",
                ["datasheet"],
                "lookup",
                "factual",
                "easy",
            ),
            (
                "Nhiệt độ làm việc tối đa của {equipment}?",
                ["datasheet"],
                "lookup",
                "factual",
                "easy",
            ),
            (
                "Công suất định mức của {equipment} là gì?",
                ["datasheet"],
                "lookup",
                "factual",
                "easy",
            ),
            (
                "Thông số kỹ thuật chính của {equipment}?",
                ["datasheet"],
                "lookup",
                "factual",
                "medium",
            ),
            # Parameters
            (
                "Giá trị áp suất trong hệ thống là bao nhiêu?",
                ["datasheet", "pid"],
                "lookup",
                "factual",
                "medium",
            ),
            (
                "Dải nhiệt độ vận hành của hệ thống?",
                ["datasheet"],
                "lookup",
                "factual",
                "easy",
            ),
            # English versions
            (
                "What is the operating pressure of {equipment}?",
                ["datasheet"],
                "lookup",
                "factual",
                "easy",
            ),
            (
                "Maximum temperature for {equipment}?",
                ["datasheet"],
                "lookup",
                "factual",
                "easy",
            ),
        ]

        # Generate with equipment IDs
        equipment_list = list(self.analyzer.equipment_ids)[:5]  # Use first 5
        for equipment in equipment_list:
            for template, doc_hints, category, type_, difficulty in templates[
                :6
            ]:  # First 6 templates
                if "{equipment}" in template:
                    query = template.replace("{equipment}", equipment)
                    language = (
                        "vi"
                        if any(
                            c in query
                            for c in "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
                        )
                        else "en"
                    )
                    self._add_qa(
                        query,
                        doc_hints,
                        category=category,
                        type=type_,
                        difficulty=difficulty,
                        language=language,
                        confidence=0.9,
                    )

        # Generate with parameters
        for param, values in list(self.analyzer.values.items())[
            :3
        ]:  # First 3 parameters
            self._add_qa(
                f"Giá trị {param} trong hệ thống là bao nhiêu?",
                ["datasheet"],
                category="lookup",
                type="factual",
                difficulty="medium",
                confidence=0.8,
            )

    def _generate_entity_location(self):
        """Generate entity location questions."""
        templates = [
            (
                "Tìm vị trí của {entity} trên bản vẽ",
                ["pid"],
                "locate",
                "factual",
                "easy",
            ),
            ("Thiết bị {entity} nằm ở đâu?", ["pid"], "locate", "factual", "easy"),
            (
                "{entity} được đặt tại vị trí nào?",
                ["pid"],
                "locate",
                "factual",
                "medium",
            ),
            ("Locate {entity} on the P&ID", ["pid"], "locate", "factual", "easy"),
            ("Where is {entity} positioned?", ["pid"], "locate", "factual", "easy"),
        ]

        # Combine all entities
        all_entities = (
            list(self.analyzer.equipment_ids)[:3]
            + list(self.analyzer.valve_tags)[:3]
            + list(self.analyzer.instrument_tags)[:3]
        )

        for entity in all_entities:
            for template, doc_hints, category, type_, difficulty in templates[
                :3
            ]:  # First 3 templates
                query = template.replace("{entity}", entity)
                language = (
                    "vi"
                    if any(
                        c in query
                        for c in "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
                    )
                    else "en"
                )
                self._add_qa(
                    query,
                    doc_hints,
                    category=category,
                    type=type_,
                    difficulty=difficulty,
                    language=language,
                    confidence=0.9,
                )

    def _generate_procedural(self):
        """Generate procedural questions."""
        templates = [
            (
                "Quy trình vận hành {equipment} như thế nào?",
                ["om", "sop"],
                "lookup",
                "procedural",
                "medium",
            ),
            (
                "Các bước khởi động {equipment}?",
                ["om", "sop"],
                "lookup",
                "procedural",
                "medium",
            ),
            (
                "Làm thế nào để bảo trì {equipment}?",
                ["om"],
                "lookup",
                "procedural",
                "hard",
            ),
            (
                "Quy trình shutdown {equipment}?",
                ["om", "sop"],
                "lookup",
                "procedural",
                "medium",
            ),
            (
                "How to operate {equipment}?",
                ["om", "sop"],
                "lookup",
                "procedural",
                "medium",
            ),
        ]

        equipment_list = list(self.analyzer.equipment_ids)[:3]
        for equipment in equipment_list:
            for template, doc_hints, category, type_, difficulty in templates:
                query = template.replace("{equipment}", equipment)
                language = (
                    "vi"
                    if any(
                        c in query
                        for c in "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
                    )
                    else "en"
                )
                self._add_qa(
                    query,
                    doc_hints,
                    category=category,
                    type=type_,
                    difficulty=difficulty,
                    language=language,
                    confidence=0.7,
                )

    def _generate_safety(self):
        """Generate safety questions."""
        templates = [
            (
                "Những lưu ý an toàn khi vận hành {equipment}?",
                ["om", "sop"],
                "lookup",
                "safety",
                "hard",
            ),
            (
                "Biện pháp an toàn cho {equipment}?",
                ["om", "sop"],
                "lookup",
                "safety",
                "medium",
            ),
            ("Rủi ro khi vận hành {equipment}?", ["om"], "lookup", "safety", "hard"),
            (
                "Safety precautions for {equipment}?",
                ["om", "sop"],
                "lookup",
                "safety",
                "medium",
            ),
        ]

        equipment_list = list(self.analyzer.equipment_ids)[:2]
        for equipment in equipment_list:
            for template, doc_hints, category, type_, difficulty in templates:
                query = template.replace("{equipment}", equipment)
                language = (
                    "vi"
                    if any(
                        c in query
                        for c in "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
                    )
                    else "en"
                )
                self._add_qa(
                    query,
                    doc_hints,
                    category=category,
                    type=type_,
                    difficulty=difficulty,
                    language=language,
                    confidence=0.6,
                )

    def _generate_troubleshooting(self):
        """Generate troubleshooting questions."""
        templates = [
            (
                "Khi {equipment} bị lỗi thì phải làm gì?",
                ["om"],
                "lookup",
                "troubleshooting",
                "hard",
            ),
            (
                "Cách khắc phục sự cố {equipment}?",
                ["om"],
                "lookup",
                "troubleshooting",
                "hard",
            ),
            (
                "Nguyên nhân {equipment} không hoạt động?",
                ["om"],
                "lookup",
                "troubleshooting",
                "hard",
            ),
            (
                "Troubleshooting {equipment} issues?",
                ["om"],
                "lookup",
                "troubleshooting",
                "hard",
            ),
        ]

        equipment_list = list(self.analyzer.equipment_ids)[:2]
        for equipment in equipment_list:
            for template, doc_hints, category, type_, difficulty in templates:
                query = template.replace("{equipment}", equipment)
                language = (
                    "vi"
                    if any(
                        c in query
                        for c in "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
                    )
                    else "en"
                )
                self._add_qa(
                    query,
                    doc_hints,
                    category=category,
                    type=type_,
                    difficulty=difficulty,
                    language=language,
                    confidence=0.5,
                )

    def _generate_negative_cases(self):
        """Generate negative test cases (should return 'no evidence')."""
        negative_queries = [
            # Non-existent equipment
            "Thông số kỹ thuật của KT99999?",
            "Áp suất vận hành của ABC12345?",
            "Specifications for XYZ-9999?",
            # Wrong domain questions
            "Giá cả của thiết bị KT06101?",
            "Ai là nhà sản xuất turbine?",
            "Khi nào bảo trì lần cuối?",
            "What is the cost of KT06101?",
            # Impossible combinations
            "Nhiệt độ tối thiểu của valve XV-999?",
            "Công suất của đường ống 4-HC-10001?",
            "Minimum temperature of pipe line?",
            # Future/predictive questions
            "Khi nào cần thay thế KT06101?",
            "Tuổi thọ còn lại của turbine?",
            "When will equipment fail?",
        ]

        for query in negative_queries:
            language = (
                "vi"
                if any(
                    c in query
                    for c in "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
                )
                else "en"
            )
            self._add_qa(
                query,
                [],
                category="negative",
                type="factual",
                difficulty="medium",
                language=language,
                confidence=1.0,
            )

    def _generate_ambiguous_cases(self):
        """Generate ambiguous questions that need clarification."""
        ambiguous_queries = [
            # Vague references
            "Áp suất của turbine là bao nhiêu?",  # Which turbine? Which pressure?
            "Thông số của compressor?",  # Which specs?
            "Temperature of the system?",  # Which temperature?
            # Multiple possible interpretations
            "Valve ở đâu?",  # Which valve?
            "Làm sao để vận hành?",  # Operate what?
            "How to start?",  # Start what?
            # Context-dependent
            "Giá trị này là gì?",  # Which value?
            "Thiết bị đó hoạt động thế nào?",  # Which equipment?
            "What is the capacity?",  # Of what?
        ]

        for query in ambiguous_queries:
            language = (
                "vi"
                if any(
                    c in query
                    for c in "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
                )
                else "en"
            )
            self._add_qa(
                query,
                ["datasheet", "pid"],
                category="ambiguous",
                type="factual",
                difficulty="hard",
                language=language,
                confidence=0.8,
            )


def load_documents(data_dir: Path) -> Dict[str, Any]:
    """Load all processed documents."""
    documents = {}

    json_files = list(data_dir.glob("*.json"))
    for json_file in json_files:
        if json_file.name.endswith(".json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    doc_id = json_file.stem
                    documents[doc_id] = data
                    logger.info(f"Loaded document: {doc_id}")
            except Exception as e:
                logger.error(f"Failed to load {json_file}: {e}")

    return documents


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic QA pairs")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/processed"),
        help="Directory with processed documents",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/qa/synthetic_qa_candidates.jsonl"),
        help="Output JSONL file",
    )
    parser.add_argument(
        "--target-count",
        type=int,
        default=80,
        help="Target number of QA pairs to generate",
    )

    args = parser.parse_args()

    logger.info(f"Generating synthetic QA pairs from {args.data_dir}")

    # Load documents
    documents = load_documents(args.data_dir)
    if not documents:
        logger.error("No documents found!")
        return

    # Analyze documents to extract entities
    analyzer = DocumentAnalyzer()
    for doc_id, doc_data in documents.items():
        summary = analyzer.analyze_document(doc_data, doc_id)
        logger.info(f"Analysis summary for {doc_id}: {summary}")

    # Generate QA pairs
    engine = QATemplateEngine(analyzer)
    qa_candidates = engine.generate_all_qa()

    # Shuffle and limit to target count
    random.shuffle(qa_candidates)
    qa_candidates = qa_candidates[: args.target_count]

    # Save to file
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for qa in qa_candidates:
            f.write(json.dumps(qa.to_dict(), ensure_ascii=False) + "\n")

    # Print summary
    logger.info(f"\nGenerated {len(qa_candidates)} QA pairs:")

    # Category breakdown
    categories = {}
    languages = {}
    difficulties = {}

    for qa in qa_candidates:
        categories[qa.category] = categories.get(qa.category, 0) + 1
        languages[qa.language] = languages.get(qa.language, 0) + 1
        difficulties[qa.difficulty] = difficulties.get(qa.difficulty, 0) + 1

    print(f"\nCategories: {dict(categories)}")
    print(f"Languages: {dict(languages)}")
    print(f"Difficulties: {dict(difficulties)}")
    print(f"\nSaved to: {args.output}")


if __name__ == "__main__":
    main()
