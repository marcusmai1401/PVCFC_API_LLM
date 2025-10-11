#!/usr/bin/env python
import os
import sys

import numpy as np
import weaviate
import weaviate.classes as wvc

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from app.services.embedding import get_embedding_service


def main():
    svc = get_embedding_service()
    query = "CO2 compressor discharge pressure"
    qvec = svc.embed_query(query).tolist()

    client = weaviate.connect_to_local(host="localhost", port=8080)
    try:
        coll = client.collections.get("Chunk")
        res = coll.query.near_vector(
            near_vector=qvec,
            limit=5,
            include_vector=True,
            return_metadata=wvc.query.MetadataQuery(distance=True),
            return_properties=["doc_id", "equipment_type", "doc_type", "vendor"],
        )
        print("Top 5 semantic results:")
        for obj in res.objects:
            doc_id = obj.properties.get("doc_id")
            eqt = obj.properties.get("equipment_type")
            dt = obj.properties.get("doc_type")
            vendor = obj.properties.get("vendor")
            dist = obj.metadata.distance if obj.metadata else None
            v = obj.vector
            if isinstance(v, dict):
                # Take the first vector in dict
                first_key = next(iter(v.keys())) if v else None
                v = v.get(first_key) if first_key else None
            vnorm = float(np.linalg.norm(v)) if v is not None else None
            print(
                f"- {doc_id} | {eqt} | {dt} | {vendor} | dist={dist:.4f} | norm={vnorm:.4f}"
            )
    finally:
        client.close()


if __name__ == "__main__":
    main()
