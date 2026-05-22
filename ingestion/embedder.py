import torch
from transformers import AutoTokenizer, AutoModel
from ingestion.chunker import Chunk
from utils.logger import get_logger
from config import get_config

class BiomedicalEmbedder:

    MODEL_NAME = "pritamdeka/S-PubMedBert-MS-MARCO"

    def __init__(self):
        self.logger = get_logger(__name__)
        self.config = get_config()

        self.logger.info(f"Loading embedding model via transformers: {self.MODEL_NAME}")

        # Use CPU for Windows compatibility by default, check for CUDA
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.logger.info(f"Using device: {self.device}")

        self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)
        self.model = AutoModel.from_pretrained(self.MODEL_NAME).to(self.device)

        self.dimension = self.model.config.hidden_size
        self.logger.info(
            f"Model loaded. Embedding dimension: {self.dimension}"
        )

    def _mean_pooling(self, model_output, attention_mask):
        token_embeddings = model_output[0] # First element of model_output contains all token embeddings
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        try:
            encoded_input = self.tokenizer(text, padding=True, truncation=True, return_tensors='pt').to(self.device)
            with torch.no_grad():
                model_output = self.model(**encoded_input)
            
            sentence_embeddings = self._mean_pooling(model_output, encoded_input['attention_mask'])
            sentence_embeddings = torch.nn.functional.normalize(sentence_embeddings, p=2, dim=1)
            
            return sentence_embeddings[0].cpu().tolist()
        except Exception as e:
            self.logger.error(f"Embedding failed for text: {e}")
            # Return zero vector as fallback
            return [0.0] * self.dimension

    def embed_batch(self, texts: list[str],
                    batch_size: int = 32) -> list[list[float]]:
        """Embed a list of texts in batches."""
        if not texts:
            return []

        self.logger.info(
            f"Embedding {len(texts)} texts "
            f"in batches of {batch_size}..."
        )

        all_embeddings = []
        try:
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                encoded_input = self.tokenizer(batch_texts, padding=True, truncation=True, return_tensors='pt').to(self.device)
                
                with torch.no_grad():
                    model_output = self.model(**encoded_input)
                
                sentence_embeddings = self._mean_pooling(model_output, encoded_input['attention_mask'])
                sentence_embeddings = torch.nn.functional.normalize(sentence_embeddings, p=2, dim=1)
                
                all_embeddings.extend(sentence_embeddings.cpu().tolist())
                
            return all_embeddings

        except Exception as e:
            self.logger.error(f"Batch embedding failed: {e}")
            self.logger.info("Falling back to single embedding...")
            return [self.embed_text(t) for t in texts]

    def embed_chunks(self,
                     chunks: list[Chunk],
                     batch_size: int = 32) -> list[tuple[Chunk, list[float]]]:
        """
        Embed a list of chunks.
        Returns list of (chunk, embedding) tuples.
        """
        if not chunks:
            return []

        texts = [chunk.text for chunk in chunks]
        embeddings = self.embed_batch(texts, batch_size)

        return list(zip(chunks, embeddings))
