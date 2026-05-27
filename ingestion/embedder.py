import os
import time
import requests
from utils.logger import get_logger

class BiomedicalEmbedder:
    def __init__(self):
        self.dimension = 768
        self.model_name = 'pritamdeka/S-PubMedBert-MS-MARCO'
        self.logger = get_logger(__name__)
        self.api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model_name}"

    def _get_headers(self):
        api_key = os.environ.get("HUGGINGFACE_API_KEY")
        if not api_key:
            self.logger.warning("HUGGINGFACE_API_KEY is not set. Using rate-limited free tier.")
            return {}
        return {"Authorization": f"Bearer {api_key}"}

    def _query(self, texts: list[str]) -> list:
        max_retries = 5
        retry_delay = 2
        for attempt in range(max_retries):
            try:
                response = requests.post(self.api_url, headers=self._get_headers(), json={"inputs": texts, "options": {"wait_for_model": True}})
                if response.status_code == 200:
                    return response.json()
                elif response.status_code in (429, 503): # Rate limit or model loading
                    self.logger.warning(f"HuggingFace API status {response.status_code}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    self.logger.error(f"HuggingFace API error: {response.text}")
                    response.raise_for_status()
            except Exception as e:
                self.logger.error(f"HuggingFace API exception: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay)
                retry_delay *= 2
        raise Exception("Max retries exceeded for HuggingFace API")

    def embed_text(self, text: str) -> list[float]:
        return self._query([text])[0]

    def embed_batch(self, texts: list[str]) -> list:
        return self._query(texts)

    def embed_chunks(self, chunks: list) -> list:
        texts = [
            getattr(c, 'text', c.get('text', ''))
            if isinstance(c, dict) else c.text
            for c in chunks
        ]
        embeddings = self.embed_batch(texts)
        return list(zip(chunks, embeddings))
