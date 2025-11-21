"""
Check Weaviate Status
Verifies the number of objects in Weaviate.
"""
import os
import sys
import weaviate
from pathlib import Path
from loguru import logger

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def main():
    logger.info("Checking Weaviate Status...")
    
    weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    
    try:
        # Try v4 client first
        try:
            client = weaviate.connect_to_local(
                port=8080,
                grpc_port=50051
            )
            logger.info("Connected using Weaviate v4 client")
            
            # v4 aggregation
            collections = client.collections.list_all()
            if not collections:
                logger.warning("No collections found.")
                
            total_objects = 0
            for name in collections:
                col = client.collections.get(name)
                count = col.aggregate.over_all(total_count=True).total_count
                logger.info(f"Collection '{name}': {count:,} objects")
                total_objects += count
                
            logger.info(f"Total Weaviate Objects: {total_objects:,}")
            client.close()
            return

        except AttributeError:
            # Fallback to v3 client
            logger.info("Falling back to Weaviate v3 client")
            client = weaviate.Client(
                url=weaviate_url,
                timeout_config=(5, 15)
            )
            
            if not client.is_ready():
                logger.error("Weaviate is not ready!")
                return

            # Get schema to find classes
            schema = client.schema.get()
            classes = schema.get('classes', [])
            
            if not classes:
                logger.warning("No classes found in Weaviate schema.")
            
            total_objects = 0
            for cls in classes:
                class_name = cls['class']
                # Aggregate count
                result = client.query.aggregate(class_name).with_meta_count().do()
                count = 0
                try:
                    count = result['data']['Aggregate'][class_name][0]['meta']['count']
                except:
                    pass
                
                logger.info(f"Class '{class_name}': {count:,} objects")
                total_objects += count
                
            logger.info(f"Total Weaviate Objects: {total_objects:,}")
            
    except Exception as e:
        logger.error(f"Failed to check Weaviate: {e}")

if __name__ == "__main__":
    main()
