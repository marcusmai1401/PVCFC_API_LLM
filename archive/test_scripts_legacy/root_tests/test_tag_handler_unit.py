#!/usr/bin/env python
"""Unit test for PID tag handler"""

from app.rag.pid_tag_handler import PIDTagHandler

handler = PIDTagHandler()

test_queries = [
    "Tag 04 ZLH 2038A nằm ở trang nào của file P&ID?",
    "Cho tôi biết tag 04 LAHH 2091 xuất hiện ở trang nào?",
    "Tag 04 TI 5027 có trong file P&ID không?",
    "Áp suất vận hành tối đa là bao nhiêu?",  # Not a tag query
]

print("\n" + "=" * 80)
print("TAG HANDLER UNIT TEST")
print("=" * 80 + "\n")

for query in test_queries:
    print(f"Query: {query}")
    detection = handler.detect_tag_query(query)
    print(f"  Is tag query: {detection.is_tag_query}")
    print(f"  Tag name: {detection.tag_name}")
    print(f"  Query type: {detection.query_type}")
    print()

print("=" * 80 + "\n")
