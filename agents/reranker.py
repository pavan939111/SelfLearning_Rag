import os
from sentence_transformers import CrossEncoder
from utils.logger import get_logger

class LocalReranker:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LocalReranker, cls).__new__(cls)
            cls._instance._init_reranker()
        return cls._instance
        
    def _init_reranker(self):
        self.model_name = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
        self.logger = get_logger(__name__)
        
        # Enforce offline-first logic
        os.environ["HF_HUB_OFFLINE"] = "1"
        self.logger.info(f"Loading local CrossEncoder model: {self.model_name}...")
        try:
            self.model = CrossEncoder(self.model_name, local_files_only=True)
        except Exception as e:
            self.logger.warning(f"Failed to load CrossEncoder locally with local_files_only=True. Attempting online download... {e}")
            os.environ["HF_HUB_OFFLINE"] = "0"
            try:
                self.model = CrossEncoder(self.model_name)
            except Exception as online_err:
                self.logger.error(f"Failed to download CrossEncoder: {online_err}")
                self.model = None
                raise online_err
        
        if self.model:
            self.logger.info("CrossEncoder model loaded successfully.")

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        """
        Predict relevance scores for list of (query, document) text pairs.
        """
        if not self.model:
            raise RuntimeError("CrossEncoder model not initialized")
        
        if not pairs:
            return []
            
        scores = self.model.predict(pairs)
        # Ensure scores are a list of floats
        if not isinstance(scores, list):
            try:
                scores = scores.tolist()
            except AttributeError:
                if isinstance(scores, (float, int)):
                    return [float(scores)]
                scores = list(scores)
        return [float(s) for s in scores]
