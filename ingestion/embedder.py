import os
from sentence_transformers import SentenceTransformer
from utils.logger import get_logger

class BiomedicalEmbedder:
    def __init__(self):
        self.dimension = 768
        self.model_name = 'pritamdeka/S-PubMedBert-MS-MARCO'
        self.logger = get_logger(__name__)
        
        # Load the model directly into RAM
        # WARNING: This requires ~450MB RAM and may cause OOM on 512MB free tier containers
        self.logger.info(f"Loading local SentenceTransformer model: {self.model_name}...")
        self.model = SentenceTransformer(self.model_name)
        self.logger.info("Model loaded successfully.")

    def embed_text(self, text: str) -> list[float]:
        """Embeds a single string into a 768-dimensional vector."""
        return self.model.encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list:
        """Embeds a batch of strings into a list of vectors."""
        return self.model.encode(texts).tolist()

    def embed_chunks(self, chunks: list) -> list:
        """
        Embeds a list of chunk objects (either dictionaries or Pydantic models).
        Returns a list of tuples: (chunk, embedding_vector)
        """
        texts = [
            getattr(c, 'text', c.get('text', ''))
            if isinstance(c, dict) else c.text
            for c in chunks
        ]
        embeddings = self.embed_batch(texts)
        return list(zip(chunks, embeddings))
