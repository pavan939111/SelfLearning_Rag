import os
from sentence_transformers import SentenceTransformer
from utils.logger import get_logger

class BiomedicalEmbedder:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BiomedicalEmbedder, cls).__new__(cls)
            cls._instance._init_embedder()
        return cls._instance
        
    def _init_embedder(self):
        self.dimension = 768
        self.model_name = 'pritamdeka/S-PubMedBert-MS-MARCO'
        self.logger = get_logger(__name__)
        self.model = None
        
    def _ensure_model_loaded(self):
        if self.model is not None:
            return
            
        # Prevent HuggingFace from attempting network requests for a "local" model
        os.environ["HF_HUB_OFFLINE"] = "1"
        
        # Load the model directly into RAM
        # WARNING: This requires ~450MB RAM and may cause OOM on 512MB free tier containers
        self.logger.info(f"Loading local SentenceTransformer model (lazy): {self.model_name}...")
        try:
            self.model = SentenceTransformer(self.model_name, local_files_only=True)
        except Exception as e:
            self.logger.warning(f"Failed to load with local_files_only=True. Attempting network download... {e}")
            os.environ["HF_HUB_OFFLINE"] = "0"
            self.model = SentenceTransformer(self.model_name)
            
        self.logger.info("Model loaded successfully.")

    def embed_text(self, text: str) -> list[float]:
        """Embeds a single string into a 768-dimensional vector."""
        self._ensure_model_loaded()
        return self.model.encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list:
        """Embeds a batch of strings into a list of vectors."""
        self._ensure_model_loaded()
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
