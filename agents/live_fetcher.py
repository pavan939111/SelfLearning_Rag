import requests
from config import get_config
from utils.logger import get_logger
from ingestion.fetcher import PaperRecord

class LiveFetcher:
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__)
    
    def fetch(self, query: str, limit: int = 5) -> list[PaperRecord]:
        try:
            self.logger.info(f"Live fetching for query: {query}")
            return [PaperRecord(
                paper_id="live_123",
                title="Mock Live Paper",
                abstract="This is a live fetched mock paper.",
                year=2024,
                journal="Test Journal"
            )]
        except Exception as e:
            self.logger.error(f"Live fetch failed: {e}")
            return []
            
    def detect_cluster(self, query: str) -> str:
        try:
            return "general"
        except Exception as e:
            return "general"
