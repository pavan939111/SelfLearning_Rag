import os
import sys
import time
import json
import random
from google import genai

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.qdrant_client import QdrantManager
from database.neo4j_client import Neo4jManager
from utils.logger import get_logger
from utils.llm_utils import get_gemini_key

logger = get_logger("build_contradiction_graph")

def check_contradiction(text1: str, text2: str) -> tuple[bool, float]:
    try:
        client = genai.Client(api_key=get_gemini_key())
        
        prompt = (
            "Do these two abstracts contradict each other?\n"
            f"Abstract 1: {text1}\n\n"
            f"Abstract 2: {text2}\n\n"
            "Reply JSON:\n"
            "{\n"
            '  "contradicts": true/false,\n'
            '  "confidence": 0.0 to 1.0\n'
            "}"
        )
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        text = response.text.strip()
        
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end+1]
            
        data = json.loads(text)
        return data.get("contradicts", False), data.get("confidence", 0.0)
    except Exception as e:
        logger.warning(f"Gemini check failed: {e}")
        return False, 0.0

def main():
    qdrant = QdrantManager()
    neo4j = Neo4jManager()
    
    if not qdrant.client or not neo4j.driver:
        logger.error("Database connections not available.")
        return
        
    clusters = ["immunotherapy", "drug_interactions", "genomics"]
    
    for cluster in clusters:
        logger.info(f"Processing cluster: {cluster}")
        
        # Scroll Qdrant for paper_ids in this cluster
        paper_ids = set()
        offset = None
        
        while True:
            records, offset = qdrant.client.scroll(
                collection_name=qdrant.COLLECTIONS["document"],
                scroll_filter={"must": [{"key": "topic_cluster", "match": {"value": cluster}}]},
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=True
            )
            
            for record in records:
                p_id = record.payload.get("paper_id")
                if p_id:
                    paper_ids.add((p_id, record.payload.get("text", ""), record.vector))
                    
            if offset is None:
                break
                
        paper_list = list(paper_ids)
        if len(paper_list) > 50:
            paper_list = random.sample(paper_list, 50)
            
        logger.info(f"Sampled {len(paper_list)} papers for cluster {cluster}")
        
        for idx, (p_id, text, vector) in enumerate(paper_list):
            if idx % 10 == 0:
                logger.info(f"  Processed {idx}/{len(paper_list)} papers...")
                
            # Search for highly similar chunks from OTHER papers
            results = qdrant.search_chunks(query_embedding=vector, level="document", top_k=5)
            
            for r in results:
                other_p_id = r.get("paper_id")
                other_text = r.get("text", "")
                score = r.get("score", 0.0)
                
                if other_p_id and other_p_id != p_id and score > 0.85:
                    time.sleep(3) # Throttle Gemini
                    contradicts, conf = check_contradiction(text, other_text)
                    
                    if contradicts and conf > 0.7:
                        logger.info(f"Found contradiction between {p_id} and {other_p_id} (conf: {conf})")
                        neo4j.create_contradiction_relationship(
                            paper_id_a=p_id,
                            paper_id_b=other_p_id,
                            confidence=conf,
                            topic=cluster
                        )
                        
                        # Update Qdrant contradiction_flag for both
                        qdrant.update_payload(
                            collection_name=qdrant.COLLECTIONS["document"],
                            payload={"contradiction_flag": True},
                            filter_key="paper_id",
                            filter_value=p_id
                        )
                        qdrant.update_payload(
                            collection_name=qdrant.COLLECTIONS["document"],
                            payload={"contradiction_flag": True},
                            filter_key="paper_id",
                            filter_value=other_p_id
                        )

if __name__ == "__main__":
    main()
