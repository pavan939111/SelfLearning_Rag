from neo4j import GraphDatabase
from tenacity import retry, stop_after_attempt, wait_fixed
from config import get_config
from utils.logger import get_logger

config = get_config()
logger = get_logger(__name__, level=config.log_level)

class Neo4jManager:
    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(
                config.neo4j_uri, 
                auth=(config.neo4j_username, config.neo4j_password)
            )
            logger.info("Initialized Neo4j driver")
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j driver: {e}")
            self.driver = None

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def test_connection(self) -> bool:
        """
        Tests connection to Neo4j by running a simple Cypher query.
        """
        if not self.driver:
            return False
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1 AS test")
                val = result.single()["test"]
                if val == 1:
                    logger.info("Neo4j AuraDB: OK - CONNECTED")
                    return True
            return False
        except Exception as e:
            logger.error(f"Neo4j AuraDB: FAIL - {e}")
            return False

    def close(self):
        """
        Closes the driver connection.
        """
        if self.driver:
            self.driver.close()
            logger.info("Closed Neo4j driver connection")

    def create_paper_node(self, paper) -> bool:
        """
        Creates a Paper node in Neo4j.
        paper is a PaperRecord or dict.
        """
        if not self.driver:
            logger.warning("Neo4j driver is not available.")
            return False
            
        try:
            # Handle both object and dict dynamically
            if hasattr(paper, "to_dict"):
                p_dict = paper.to_dict()
            elif hasattr(paper, "__dict__"):
                p_dict = paper.__dict__
            else:
                p_dict = dict(paper)
                
            authors_raw = p_dict.get("authors", [])
            if isinstance(authors_raw, str):
                authors = [a.strip() for a in authors_raw.split(",") if a.strip()]
            elif isinstance(authors_raw, list):
                authors = [str(a) for a in authors_raw]
            else:
                authors = []

            # Safely extract values with defaults to never crash
            params = {
                "paper_id": str(p_dict.get("paper_id", "")),
                "title": str(p_dict.get("title", "")),
                "year": int(p_dict.get("year", 0)) if p_dict.get("year") is not None else 0,
                "journal": str(p_dict.get("journal", "") or ""),
                "authors": authors,
                "topic_cluster": str(p_dict.get("topic_cluster", "") or ""),
                "evidence_level": str(p_dict.get("evidence_level", "") or ""),
                "ingestion_date": str(p_dict.get("ingestion_date", "") or ""),
                "freshness_score": float(p_dict.get("freshness_score", 0.0)) if p_dict.get("freshness_score") is not None else 0.0,
                "contradiction_flag": bool(p_dict.get("contradiction_flag", False))
            }
            
            cypher = """
            MERGE (p:Paper {paper_id: $paper_id})
            SET p.title = $title,
                p.year = $year,
                p.journal = $journal,
                p.authors = $authors,
                p.topic_cluster = $topic_cluster,
                p.evidence_level = $evidence_level,
                p.ingestion_date = $ingestion_date,
                p.freshness_score = $freshness_score,
                p.contradiction_flag = $contradiction_flag
            RETURN p
            """
            with self.driver.session() as session:
                session.run(cypher, **params)
            return True
        except Exception as e:
            logger.error(f"Failed to create paper node in Neo4j: {e}")
            return False

    def create_papers_batch(self, papers) -> int:
        """
        Create multiple paper nodes in one transaction.
        Processes in batches of 50.
        Returns count of successfully created nodes.
        """
        if not self.driver or not papers:
            return 0
            
        success_count = 0
        try:
            # Process in batches of 50
            batch_size = 50
            for i in range(0, len(papers), batch_size):
                batch = papers[i:i + batch_size]
                batch_params = []
                for paper in batch:
                    # Parse paper record
                    if hasattr(paper, "to_dict"):
                        p_dict = paper.to_dict()
                    elif hasattr(paper, "__dict__"):
                        p_dict = paper.__dict__
                    else:
                        p_dict = dict(paper)
                        
                    authors_raw = p_dict.get("authors", [])
                    if isinstance(authors_raw, str):
                        authors = [a.strip() for a in authors_raw.split(",") if a.strip()]
                    elif isinstance(authors_raw, list):
                        authors = [str(a) for a in authors_raw]
                    else:
                        authors = []

                    batch_params.append({
                        "paper_id": str(p_dict.get("paper_id", "")),
                        "title": str(p_dict.get("title", "")),
                        "year": int(p_dict.get("year", 0)) if p_dict.get("year") is not None else 0,
                        "journal": str(p_dict.get("journal", "") or ""),
                        "authors": authors,
                        "topic_cluster": str(p_dict.get("topic_cluster", "") or ""),
                        "evidence_level": str(p_dict.get("evidence_level", "") or ""),
                        "ingestion_date": str(p_dict.get("ingestion_date", "") or ""),
                        "freshness_score": float(p_dict.get("freshness_score", 0.0)) if p_dict.get("freshness_score") is not None else 0.0,
                        "contradiction_flag": bool(p_dict.get("contradiction_flag", False))
                    })
                
                # Cypher batch merge
                batch_cypher = """
                UNWIND $papers AS p_data
                MERGE (p:Paper {paper_id: p_data.paper_id})
                SET p.title = p_data.title,
                    p.year = p_data.year,
                    p.journal = p_data.journal,
                    p.authors = p_data.authors,
                    p.topic_cluster = p_data.topic_cluster,
                    p.evidence_level = p_data.evidence_level,
                    p.ingestion_date = p_data.ingestion_date,
                    p.freshness_score = p_data.freshness_score,
                    p.contradiction_flag = p_data.contradiction_flag
                RETURN count(p) AS count
                """
                with self.driver.session() as session:
                    res = session.run(batch_cypher, papers=batch_params)
                    single_res = res.single()
                    if single_res:
                        success_count += single_res["count"]
                    else:
                        success_count += len(batch)
        except Exception as e:
            logger.error(f"Failed to create papers batch in Neo4j: {e}")
            
        return success_count

    def get_paper_count(self) -> int:
        """
        Returns count of Paper nodes in Neo4j.
        """
        if not self.driver:
            return 0
        try:
            with self.driver.session() as session:
                res = session.run("MATCH (p:Paper) RETURN count(p) as count")
                single_res = res.single()
                return single_res["count"] if single_res else 0
        except Exception as e:
            logger.error(f"Failed to get paper count from Neo4j: {e}")
            return 0

    def create_topic_cluster_nodes(self) -> bool:
        """
        Create TopicCluster nodes and connect papers to their clusters.
        """
        if not self.driver:
            return False
        try:
            with self.driver.session() as session:
                # 1. Create topic cluster nodes
                session.run('MERGE (:TopicCluster {name: "immunotherapy"})')
                session.run('MERGE (:TopicCluster {name: "drug_interactions"})')
                session.run('MERGE (:TopicCluster {name: "genomics"})')
                
                # 2. Connect papers to their cluster
                session.run("""
                MATCH (p:Paper), (c:TopicCluster)
                WHERE p.topic_cluster = c.name
                MERGE (p)-[:BELONGS_TO]->(c)
                """)
            return True
        except Exception as e:
            logger.error(f"Failed to create topic clusters and relationships in Neo4j: {e}")
            return False

    def create_contradiction_relationship(self, paper_id_a: str, paper_id_b: str, confidence: float, topic: str) -> bool:
        """Creates a CONTRADICTS relationship between two papers."""
        if not self.driver: return False
        try:
            cypher = """
            MATCH (a:Paper {paper_id: $paper_id_a})
            MATCH (b:Paper {paper_id: $paper_id_b})
            MERGE (a)-[r:CONTRADICTS {
                confidence: $confidence,
                topic: $topic,
                detected_at: datetime()
            }]->(b)
            RETURN r
            """
            with self.driver.session() as session:
                session.run(cypher, paper_id_a=paper_id_a, paper_id_b=paper_id_b, confidence=confidence, topic=topic)
            return True
        except Exception as e:
            logger.warning(f"Neo4j contradiction relation error: {e}")
            return False

    def create_supersedes_relationship(self, new_paper_id: str, old_paper_id: str, reason: str) -> bool:
        """Creates SUPERSEDES relationship when newer paper updates older paper."""
        if not self.driver: return False
        try:
            cypher = """
            MATCH (new:Paper {paper_id: $new_paper_id})
            MATCH (old:Paper {paper_id: $old_paper_id})
            MERGE (new)-[r:SUPERSEDES {
                reason: $reason,
                created_at: datetime()
            }]->(old)
            SET old.contradiction_flag = true, old.superseded_by = $new_paper_id
            RETURN r
            """
            with self.driver.session() as session:
                session.run(cypher, new_paper_id=new_paper_id, old_paper_id=old_paper_id, reason=reason)
            return True
        except Exception as e:
            logger.warning(f"Neo4j supersedes relation error: {e}")
            return False

    def get_contradictions_for_paper(self, paper_id: str) -> list[dict]:
        """Find all papers that contradict this paper."""
        if not self.driver: return []
        try:
            cypher = """
            MATCH (p:Paper {paper_id: $paper_id})
            OPTIONAL MATCH (p)-[r:CONTRADICTS]-(other:Paper)
            RETURN other.paper_id as paper_id, other.title as title, 
                   r.confidence as confidence, r.topic as topic
            """
            res_list = []
            with self.driver.session() as session:
                res = session.run(cypher, paper_id=paper_id)
                for record in res:
                    if record["paper_id"]:
                        res_list.append(dict(record))
            return res_list
        except Exception as e:
            logger.warning(f"Neo4j get_contradictions error: {e}")
            return []

    def get_contradiction_stats(self) -> dict:
        """Count total contradiction relationships."""
        if not self.driver: return {"total_contradictions": 0}
        try:
            cypher = """
            MATCH ()-[r:CONTRADICTS]->()
            RETURN count(r) as total
            """
            with self.driver.session() as session:
                res = session.run(cypher)
                single = res.single()
                count = single["total"] if single else 0
                return {"total_contradictions": count}
        except Exception as e:
            logger.warning(f"Neo4j stats error: {e}")
            return {"total_contradictions": 0}

    def get_citation_neighbors(self, paper_ids: list[str], depth: int = 1) -> list[str]:
        if not self.driver or not paper_ids: return []
        try:
            cypher = f"""
            MATCH (p:Paper)
            WHERE p.paper_id IN $paper_ids
            MATCH (p)-[*1..{depth}]-(neighbor:Paper)
            RETURN DISTINCT neighbor.paper_id as paper_id
            LIMIT 20
            """
            res_list = []
            with self.driver.session() as session:
                res = session.run(cypher, paper_ids=paper_ids)
                for record in res:
                    if record["paper_id"]:
                        res_list.append(record["paper_id"])
            return res_list
        except Exception as e:
            logger.warning(f"Neo4j get_citation_neighbors error: {e}")
            return []

    def get_contradiction_neighbors(self, paper_ids: list[str]) -> list[str]:
        if not self.driver or not paper_ids: return []
        try:
            cypher = """
            MATCH (p:Paper)
            WHERE p.paper_id IN $paper_ids
            MATCH (p)-[:CONTRADICTS]-(other:Paper)
            RETURN DISTINCT other.paper_id as paper_id
            """
            res_list = []
            with self.driver.session() as session:
                res = session.run(cypher, paper_ids=paper_ids)
                for record in res:
                    if record["paper_id"]:
                        res_list.append(record["paper_id"])
            return res_list
        except Exception as e:
            logger.warning(f"Neo4j get_contradiction_neighbors error: {e}")
            return []

    def get_cluster_papers(self, topic_cluster: str, limit: int = 10) -> list[str]:
        if not self.driver or not topic_cluster: return []
        try:
            cypher = """
            MATCH (p:Paper)-[:BELONGS_TO]->(c:TopicCluster)
            WHERE c.name = $topic_cluster
            RETURN p.paper_id as paper_id
            ORDER BY p.year DESC
            LIMIT $limit
            """
            res_list = []
            with self.driver.session() as session:
                res = session.run(cypher, topic_cluster=topic_cluster, limit=limit)
                for record in res:
                    if record["paper_id"]:
                        res_list.append(record["paper_id"])
            return res_list
        except Exception as e:
            logger.warning(f"Neo4j get_cluster_papers error: {e}")
            return []

    def get_papers_metadata(self, paper_ids: list[str]) -> dict[str, dict]:
        if not self.driver or not paper_ids: return {}
        try:
            cypher = """
            MATCH (p:Paper)
            WHERE p.paper_id IN $paper_ids
            RETURN p.paper_id as paper_id, p.title as title, p.journal as journal, p.year as year, p.authors as authors
            """
            metadata = {}
            with self.driver.session() as session:
                res = session.run(cypher, paper_ids=paper_ids)
                for record in res:
                    pid = record["paper_id"]
                    metadata[pid] = {
                        "title": record.get("title") or "Unknown Title",
                        "journal": record.get("journal") or "Unknown Journal",
                        "year": record.get("year") or 2020,
                        "authors": record.get("authors") or []
                    }
            return metadata
        except Exception as e:
            logger.warning(f"Neo4j get_papers_metadata error: {e}")
            return {}
