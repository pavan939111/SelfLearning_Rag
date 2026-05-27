from ingestion.chunker import Chunk
from utils.logger import get_logger

class BiomedicalEmbedder:
    def __init__(self):
        self._model = None
        self.dimension = 768
        self.model_name = 'pritamdeka/S-PubMedBert-MS-MARCO'
        self.logger = get_logger(__name__)

    @property
    def model(self):
        if self._model is None:
            self.logger.info('Loading embedding model...')
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self.dimension = self._model.get_embedding_dimension()
            self.logger.info('Model loaded')
        return self._model

    def embed_text(self, text: str) -> list[float]:
        return self.model.encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list:
        return self.model.encode(texts).tolist()

    def embed_chunks(self, chunks: list) -> list:
        texts = [
            getattr(c, 'text', c.get('text', ''))
            if isinstance(c, dict) else c.text
            for c in chunks
        ]
        embeddings = self.model.encode(texts)
        return list(zip(chunks, embeddings.tolist()))
