#!/usr/bin/env python3
from app.rag.query_transform import QueryTransformer
from app.rag.retriever import create_hybrid_retriever


def main():
    qt = QueryTransformer(enable_hyde=True)
    # Vietnamese
    q_vi = "Áp suất vận hành của KT06101 là bao nhiêu?"
    tq_vi = qt.transform(query=q_vi, filters=None, language="vi")
    r = create_hybrid_retriever()
    res_vi = r.search(tq_vi)
    print("VI normalized:", tq_vi.normalized)
    print("VI intent:", tq_vi.intent)
    print("VI hyde count:", len(tq_vi.hyde_queries) if tq_vi.hyde_queries else 0)
    print("VI results:", len(res_vi))
    if res_vi:
        print(
            "Top doc_id:",
            res_vi[0].doc_id,
            "page:",
            res_vi[0].page,
            "score:",
            res_vi[0].score,
        )

    # English
    q_en = "What is the operating pressure of KT06101?"
    tq_en = qt.transform(query=q_en, filters=None, language="en")
    res_en = r.search(tq_en)
    print("EN normalized:", tq_en.normalized)
    print("EN intent:", tq_en.intent)
    print("EN results:", len(res_en))
    if res_en:
        print(
            "Top doc_id:",
            res_en[0].doc_id,
            "page:",
            res_en[0].page,
            "score:",
            res_en[0].score,
        )


if __name__ == "__main__":
    main()
