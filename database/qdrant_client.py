from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    VectorParams, Distance, PayloadSchemaType,
    CreateCollection, OptimizersConfigDiff, PointStruct
)
import uuid
from tenacity import retry, stop_after_attempt, wait_fixed
from config import get_config
from utils.logger import get_logger

config = get_config()
logger = get_logger(__name__, level=config.log_level)

class QdrantManager:

    COLLECTIONS = {
        "document":     "failurerag_document",
        "section":      "failurerag_section",
        "semantic":     "failurerag_semantic",
        "proposition":  "failurerag_proposition",
    }
    
    STAGING_COLLECTIONS = {
        "document":     "failurerag_document_staging",
        "section":      "failurerag_section_staging",
        "semantic":     "failurerag_semantic_staging",
        "proposition":  "failurerag_proposition_staging",
    }

    def __init__(self):
        try:
            self.client = QdrantClient(
                url=config.qdrant_url,
                api_key=config.qdrant_api_key
            )
            logger.info("Initialized Qdrant client")
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            self.client = None

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def test_connection(self) -> bool:
        """
        Tests connection to Qdrant cluster by getting collections.
        """
        if not self.client:
            return False
        try:
            # Simple ping-like operation
            self.client.get_collections()
            logger.info("Qdrant Cloud: OK - CONNECTED")
            return True
        except Exception as e:
            logger.error(f"Qdrant Cloud: FAIL - {e}")
            return False

    def get_collections(self) -> list:
        """
        Lists all existing collections in the cluster.
        """
        if not self.client:
            return []
        try:
            collections = self.client.get_collections()
            return [c.name for c in collections.collections]
        except Exception as e:
            logger.error(f"Failed to list Qdrant collections: {e}")
            return []

    def get_embedding_dimension(self) -> int:
        """Loads embedder to get its dimension."""
        embedder = BiomedicalEmbedder()
        return embedder.dimension

    def create_collections(self,
                           dimension: int,
                           recreate: bool = False) -> bool:
        """Creates collections for all hierarchy levels if they don't exist."""
        try:
            existing = [
                c.name for c in
                self.client.get_collections().collections
            ]

            for level, collection_name in self.COLLECTIONS.items():

                if collection_name in existing:
                    if recreate:
                        logger.info(
                            f"Deleting existing: {collection_name}"
                        )
                        self.client.delete_collection(collection_name)
                    else:
                        logger.info(
                            f"Already exists: {collection_name}"
                        )
                        continue

                logger.info(f"Creating: {collection_name}")

                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=dimension,
                        distance=Distance.COSINE,
                    ),
                    optimizers_config=OptimizersConfigDiff(
                        indexing_threshold=1000
                    )
                )

                # Create payload indexes for fast filtering
                indexes = {
                    "topic_cluster":      PayloadSchemaType.KEYWORD,
                    "year":               PayloadSchemaType.INTEGER,
                    "evidence_level":     PayloadSchemaType.KEYWORD,
                    "freshness_score":    PayloadSchemaType.FLOAT,
                    "contradiction_flag": PayloadSchemaType.BOOL,
                    "paper_id":           PayloadSchemaType.KEYWORD,
                    "level":              PayloadSchemaType.KEYWORD,
                    "section_type":       PayloadSchemaType.KEYWORD,
                }

                for field_name, schema_type in indexes.items():
                    self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field_name,
                        field_schema=schema_type,
                    )
                    logger.debug(
                        f"Index created: {field_name} "
                        f"on {collection_name}"
                    )

                logger.info(
                    f"Collection ready: {collection_name}"
                )

            return True

        except Exception as e:
            logger.error(f"Collection creation failed: {e}")
            return False

    def collection_exists(self, level: str) -> bool:
        """Checks if a collection for a specific hierarchy level exists."""
        try:
            name = self.COLLECTIONS[level]
            existing = self.get_collections()
            return name in existing
        except Exception:
            return False

    def get_collection_info(self, level: str) -> dict:
        """Returns metadata about a specific hierarchical collection."""
        try:
            name = self.COLLECTIONS[level]
            info = self.client.get_collection(name)
            return {
                "name": name,
                "vectors_count": getattr(info, "vectors_count", 0),
                "points_count": getattr(info, "points_count", 0),
                "status": str(info.status),
            }
        except Exception as e:
            logger.error(f"Get collection info failed: {e}")
            return {}

    def insert_chunks(self,
                      chunk_embeddings: list[tuple],
                      level: str,
                      batch_size: int = 100,
                      is_staging: bool = False) -> int:
        """
        Insert chunks with their embeddings into Qdrant.

        Args:
            chunk_embeddings: list of (Chunk, embedding) tuples
            level: one of document/section/semantic/proposition
            batch_size: points per upsert call
            is_staging: if True, inserts into the staging collection

        Returns:
            Number of points successfully inserted
        """
        if not chunk_embeddings:
            return 0

        collection_name = self.STAGING_COLLECTIONS[level] if is_staging else self.COLLECTIONS[level]
        total_inserted = 0

        # Process in batches
        for i in range(0, len(chunk_embeddings), batch_size):
            batch = chunk_embeddings[i:i + batch_size]
            points = []

            for chunk, embedding in batch:
                # Build payload from chunk metadata
                payload = {
                    "chunk_id":          chunk.chunk_id,
                    "paper_id":          chunk.paper_id,
                    "level":             chunk.level.value,
                    "text":              chunk.text,
                    "parent_chunk_id":   chunk.parent_chunk_id,
                    "section_type":      chunk.section_type,
                    "topic_cluster":     chunk.topic_cluster,
                    "year":              chunk.year,
                    "journal":           chunk.journal,
                    "evidence_level":    chunk.evidence_level,
                    "ingestion_date":    chunk.ingestion_date,
                    "freshness_score":   chunk.freshness_score,
                    "contradiction_flag":chunk.contradiction_flag,
                    "char_count":        chunk.char_count,
                    "chunk_index":       chunk.chunk_index,
                }

                # Use deterministic ID from chunk_id
                # hash chunk_id to a consistent integer
                point_id = abs(hash(chunk.chunk_id)) % (2**63)

                points.append(PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                ))

            try:
                self.client.upsert(
                    collection_name=collection_name,
                    points=points,
                    wait=True
                )
                total_inserted += len(points)
                logger.info(
                    f"Inserted batch {i//batch_size + 1}: "
                    f"{len(points)} points into {collection_name}"
                )

            except Exception as e:
                logger.error(
                    f"Batch insert failed for {collection_name}: {e}"
                )
                continue

        logger.info(
            f"Total inserted into {collection_name}: {total_inserted}"
        )
        return total_inserted

    def search_chunks(self,
                      query_embedding: list[float],
                      level: str,
                      top_k: int = 5,
                      filters: dict | None = None) -> list[dict]:
        """
        Search for similar chunks in a collection.

        Args:
            query_embedding: query vector
            level: collection level to search
            top_k: number of results
            filters: optional payload filters dict
                     e.g. {"topic_cluster": "immunotherapy"}

        Returns:
            list of dicts with text, score, and metadata
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        collection_name = self.COLLECTIONS[level]

        # Build filter if provided
        qdrant_filter = None
        if filters:
            conditions = []
            for field, value in filters.items():
                conditions.append(
                    FieldCondition(
                        key=field,
                        match=MatchValue(value=value)
                    )
                )
            if conditions:
                qdrant_filter = Filter(must=conditions)

        try:
            # Using query_points for compatibility with qdrant-client 1.18.0
            results = self.client.query_points(
                collection_name=collection_name,
                query=query_embedding,
                query_filter=qdrant_filter,
                limit=top_k,
                with_payload=True,
            )

            return [
                {
                    "chunk_id":      r.payload.get("chunk_id", ""),
                    "paper_id":      r.payload.get("paper_id", ""),
                    "text":          r.payload.get("text", ""),
                    "score":         r.score,
                    "level":         r.payload.get("level", ""),
                    "section_type":  r.payload.get("section_type", ""),
                    "topic_cluster": r.payload.get("topic_cluster", ""),
                    "year":          r.payload.get("year", 0),
                    "freshness_score": r.payload.get(
                        "freshness_score", 1.0
                    ),
                    "contradiction_flag": r.payload.get(
                        "contradiction_flag", False
                    ),
                }
                for r in results.points
            ]

        except Exception as e:
            logger.error(f"Search failed in {collection_name}: {e}")
            return []

    def create_staging_collections(self, dimension: int, recreate: bool = False) -> bool:
        """Creates staging collections for validation before promotion."""
        try:
            existing = [c.name for c in self.client.get_collections().collections]
            for level, collection_name in self.STAGING_COLLECTIONS.items():
                if collection_name in existing:
                    if recreate:
                        logger.info(f"Deleting existing staging: {collection_name}")
                        self.client.delete_collection(collection_name)
                    else:
                        logger.info(f"Staging already exists: {collection_name}")
                        continue

                logger.info(f"Creating staging: {collection_name}")
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
                    optimizers_config=OptimizersConfigDiff(indexing_threshold=1000)
                )

                indexes = {
                    "topic_cluster": PayloadSchemaType.KEYWORD,
                    "paper_id": PayloadSchemaType.KEYWORD,
                    "level": PayloadSchemaType.KEYWORD,
                }
                for field_name, schema_type in indexes.items():
                    self.client.create_payload_index(
                        collection_name=collection_name, field_name=field_name, field_schema=schema_type
                    )
            return True
        except Exception as e:
            logger.error(f"Staging collection creation failed: {e}")
            return False

    def validate_staging(self, level: str, test_queries: list[str]) -> dict:
        """Runs test_queries against staging collection and validates average score."""
        try:
            from ingestion.embedder import BiomedicalEmbedder
            embedder = BiomedicalEmbedder()
            
            collection_name = self.STAGING_COLLECTIONS[level]
            scores = []
            
            for query in test_queries:
                embedding = embedder.embed_text(query)
                results = self.client.query_points(
                    collection_name=collection_name,
                    query=embedding,
                    limit=1,
                    with_payload=False
                )
                if results.points:
                    scores.append(results.points[0].score)
                    
            if len(scores) != len(test_queries) or not scores:
                return {"passed": False, "scores": scores, "avg_score": 0.0, "reason": "Not all queries returned results"}
                
            avg_score = sum(scores) / len(scores)
            passed = avg_score > 0.5
            
            return {
                "passed": passed,
                "scores": scores,
                "avg_score": avg_score,
                "reason": f"Avg score {avg_score:.2f} > 0.5" if passed else f"Avg score {avg_score:.2f} <= 0.5"
            }
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {"passed": False, "scores": [], "avg_score": 0.0, "reason": str(e)}

    def promote_staging_to_production(self, level: str) -> bool:
        """Scrolls from staging, upserts to production, and clears staging."""
        try:
            staging_name = self.STAGING_COLLECTIONS[level]
            prod_name = self.COLLECTIONS[level]
            
            offset = None
            total_promoted = 0
            while True:
                records, offset = self.client.scroll(
                    collection_name=staging_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True
                )
                
                if not records:
                    break
                    
                points = [
                    PointStruct(id=r.id, vector=r.vector, payload=r.payload)
                    for r in records
                ]
                
                if points:
                    self.client.upsert(collection_name=prod_name, points=points, wait=True)
                    total_promoted += len(points)
                    
                if offset is None:
                    break
                    
            logger.info(f"Promoted {total_promoted} chunks from {staging_name} to {prod_name}")
            
            # Clear staging
            self.client.delete_collection(staging_name)
            self.create_staging_collections(len(records[0].vector) if records else 768, recreate=False)
            
            return True
        except Exception as e:
            logger.error(f"Promotion failed: {e}")
            return False
