import logging
import os
import sys
from unittest.mock import patch

# Ensure repo root is on sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import app.rag.generator as genmod
from app.rag.generator import GeneratorConfig, ResponseGenerator
from app.rag.query_transform import QueryFilters, QueryIntent, TransformedQuery
from app.rag.retriever import RetrievalResult

# Configure logging to stdout at INFO level
logging.getLogger().setLevel(logging.INFO)


def build_docs(mapped: bool = True):
    doc_id = "DOC001" if mapped else "DOC999"
    docs = [
        RetrievalResult(
            chunk_id="chunk1",
            text="Spec table with pressure 10 bar",
            score=0.9,
            source="bm25",
            metadata={"doc_id": doc_id, "page": 12},
            doc_id=doc_id,
            page=12,
        )
    ]
    return docs


def run_case_off():
    print("=== Vision OFF (no mapping) ===")
    # Force empty doc_id_map
    genmod._DOC_ID_MAP_CACHE = {}

    cfg = GeneratorConfig(enable_vision_generation=True)
    g = ResponseGenerator(cfg)

    q = TransformedQuery(
        original="Áp suất vận hành tối đa?",
        normalized="maximum operating pressure",
        intent=QueryIntent.ASK,
        filters=QueryFilters(),
        language="vi",
    )
    docs = build_docs(mapped=False)

    # Call private vision path to produce gating OFF log
    g._try_vision_generation(
        english_query=q.normalized,
        original_query=q.original,
        context="[Doc 1] p.12: Max operating pressure 10 bar",
        doc_mapping={1: docs[0]},
        retrieved_docs=docs,
        language=q.language,
    )


def run_case_on():
    print("=== Vision ON (with mapping, stubbed renderer & gemini) ===")
    # Provide mapping
    genmod._DOC_ID_MAP_CACHE = {"DOC001": "C:/test/doc1.pdf"}

    cfg = GeneratorConfig(enable_vision_generation=True)
    g = ResponseGenerator(cfg)

    q = TransformedQuery(
        original="Áp suất vận hành tối đa?",
        normalized="maximum operating pressure",
        intent=QueryIntent.ASK,
        filters=QueryFilters(),
        language="vi",
    )
    docs = build_docs(mapped=True)

    # Patch renderer and gemini client/types
    class FakeResp:
        text = "Áp suất vận hành tối đa là 10 bar [Doc 1, p.12]"

    class FakeModels:
        def generate_content(self, model, contents, config):
            return FakeResp()

    class FakeClient:
        def __init__(self, api_key=None):
            self.models = FakeModels()

    class FakeTypes:
        class Content:
            def __init__(self, role=None, parts=None):
                self.role = role
                self.parts = parts

        class Part:
            @staticmethod
            def from_text(text):
                return ("text", text)

            @staticmethod
            def from_bytes(mime_type=None, data=None):
                return ("bytes", len(data) if data else 0)

        class GenerateContentConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

    with patch(
        "tools.pdf_renderer.render_page_to_image",
        return_value=(b"img", {"w": 100, "h": 100}),
    ):
        with patch("app.services.llm.get_api_key_for", return_value="fake"):
            with patch("google.genai.types", FakeTypes):
                # Patch genai.Client in google module path
                with patch("google.genai.Client", FakeClient):
                    # Run full generate to trigger ON path & logs
                    g.generate(q, docs)


if __name__ == "__main__":
    run_case_off()
    run_case_on()
