"""
Spatial Component Indexer
Index tag components to OpenSearch for spatial search
"""
from typing import List

from loguru import logger
from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk

from app.config import get_config
from app.rag.spatial.schemas import SPATIAL_INDEX_MAPPING, SPATIAL_INDEX_NAME, Component


class SpatialComponentIndexer:
    """Index spatial components to OpenSearch"""

    def __init__(self, host: str = "localhost", port: int = 9200):
        """Initialize indexer with OpenSearch connection"""
        self.client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False,
        )
        self.index_name = SPATIAL_INDEX_NAME

    def create_index(self, recreate: bool = False):
        """Create spatial components index with proper mapping"""
        if recreate and self.client.indices.exists(index=self.index_name):
            logger.info(f"Deleting existing index: {self.index_name}")
            self.client.indices.delete(index=self.index_name)

        if not self.client.indices.exists(index=self.index_name):
            logger.info(f"Creating index: {self.index_name}")
            self.client.indices.create(
                index=self.index_name, body=SPATIAL_INDEX_MAPPING
            )
            logger.info(f"✓ Index created: {self.index_name}")
        else:
            logger.info(f"Index already exists: {self.index_name}")

    def index_components(self, components: List[Component]) -> int:
        """
        Index a list of components to OpenSearch

        Args:
            components: List of Component objects

        Returns:
            Number of components successfully indexed
        """
        if not components:
            logger.warning("No components to index")
            return 0

        actions = []
        for comp in components:
            center = comp.center

            doc = {
                "_index": self.index_name,
                "_source": {
                    "doc_id": comp.doc_id,
                    "page": comp.page,
                    "component": comp.text,
                    "component_type": comp.component_type,
                    "bbox": {
                        "x0": comp.bbox[0],
                        "y0": comp.bbox[1],
                        "x1": comp.bbox[2],
                        "y1": comp.bbox[3],
                    },
                    "center_x": center[0],
                    "center_y": center[1],
                    "span_id": comp.span_id,
                },
            }
            actions.append(doc)

        # Bulk index
        success, errors = bulk(
            self.client,
            actions,
            raise_on_error=False,
            refresh="wait_for",  # Wait for index refresh
        )

        if errors:
            logger.error(f"Indexing errors: {len(errors)}")
            for error in errors[:5]:  # Show first 5 errors
                logger.error(f"  {error}")

        logger.info(
            f"✓ Indexed {success}/{len(components)} components "
            f"(doc={components[0].doc_id}, page={components[0].page})"
        )

        return success

    def delete_page_components(self, doc_id: str, page: int):
        """Delete all components for a specific page"""
        self.client.delete_by_query(
            index=self.index_name,
            body={
                "query": {
                    "bool": {
                        "must": [{"term": {"doc_id": doc_id}}, {"term": {"page": page}}]
                    }
                }
            },
            refresh=True,
        )
        logger.info(f"Deleted components for {doc_id} page {page}")

    def get_component_count(self, doc_id: str = None, page: int = None) -> int:
        """Get count of indexed components"""
        query = {"match_all": {}}

        if doc_id or page:
            must = []
            if doc_id:
                must.append({"term": {"doc_id": doc_id}})
            if page:
                must.append({"term": {"page": page}})
            query = {"bool": {"must": must}}

        response = self.client.count(index=self.index_name, body={"query": query})

        return response["count"]

    def search_components(
        self,
        component_text: str = None,
        component_type: str = None,
        doc_id: str = None,
        page: int = None,
        size: int = 100,
    ) -> List[dict]:
        """Search for components"""
        must = []

        if component_text:
            must.append({"term": {"component": component_text}})
        if component_type:
            must.append({"term": {"component_type": component_type}})
        if doc_id:
            must.append({"term": {"doc_id": doc_id}})
        if page:
            must.append({"term": {"page": page}})

        query = {"bool": {"must": must}} if must else {"match_all": {}}

        response = self.client.search(
            index=self.index_name, body={"query": query, "size": size}
        )

        return [hit["_source"] for hit in response["hits"]["hits"]]
