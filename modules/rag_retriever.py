import os
import chromadb
from chromadb.utils import embedding_functions
from loguru import logger

# Path to the persistent ChromaDB store
# In Docker, this will be baked into the image or volume-mounted
CHROMA_PATH = os.path.join(os.getcwd(), 'temp', 'chroma_db')

class RAGRetriever:
    """
    Local RAG engine using ChromaDB and sentence-transformers.
    Designed as a singleton to avoid re-loading embedding models multiple times.
    """
    _instance = None
    _client = None
    _embedding_function = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RAGRetriever, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        logger.info(f"Initializing RAGRetriever at {CHROMA_PATH}")
        
        # Ensure path exists
        if not os.path.exists(CHROMA_PATH):
            logger.warning(f"ChromaDB path {CHROMA_PATH} does not exist. Retrieval will fail until ingestion is run.")
            os.makedirs(CHROMA_PATH, exist_ok=True)
        
        try:
            # PersistentClient handles the SQLite connection
            self._client = chromadb.PersistentClient(path=CHROMA_PATH)
            
            # This handles model downloading if not present. 
            # In Docker, we pre-download this in the build stage.
            self._embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            self._initialized = True
            logger.success("RAGRetriever initialized successfully.")
        except Exception as e:
            logger.error(f"Critical error initializing RAGRetriever: {e}")
            self._client = None
            self._initialized = False

    def slugify(self, text: str) -> str:
        """Utility to match the collection naming convention in ingest_rag.py."""
        return text.lower().replace(" ", "_").replace("/", "_").replace("'", "").replace("-", "_")

    def retrieve(self, topic: str, domain: str = None, n_results: int = 10) -> list:
        """
        Retrieves the most semantically relevant curriculum chunks for a given topic.
        
        Args:
            topic: The search query (e.g., "Newton's Second Law").
            domain: The subject domain (e.g., "AP Physics"). If provided, limits search to that collection.
            n_results: Number of chunks to return.
            
        Returns:
            A list of strings containing the text chunks.
        """
        if not self._initialized or not self._client:
            logger.error("RAGRetriever not initialized. Returning empty list.")
            return []

        try:
            # If domain is provided, we use the specific collection for zero-hallucination precision
            if domain:
                collection_name = f"domain_{self.slugify(domain)}"
                logger.info(f"RAG: Querying collection '{collection_name}' for topic '{topic}'")
                
                try:
                    collection = self._client.get_collection(
                        name=collection_name, 
                        embedding_function=self._embedding_function
                    )
                    
                    results = collection.query(
                        query_texts=[topic],
                        n_results=n_results
                    )
                    
                    if results and 'documents' in results and results['documents']:
                        # Chroma returns a list of lists: [[chunk1, chunk2, ...]]
                        return results['documents'][0]
                    else:
                        logger.warning(f"RAG: No results found in collection {collection_name}")
                        
                except Exception as e:
                    logger.error(f"RAG: Collection {collection_name} not found or query failed: {e}")
            
            # Global search fallback (if domain is not provided or collection is missing)
            # This is a safety net; the primary path should be domain-specific.
            logger.info(f"RAG: Attempting global search for '{topic}' across all collections...")
            all_results = []
            
            # Simple global search: iterate all collections (efficient enough for < 20 collections)
            collections = self._client.list_collections()
            for col_info in collections:
                col = self._client.get_collection(name=col_info.name, embedding_function=self._embedding_function)
                res = col.query(query_texts=[topic], n_results=3)
                if res and 'documents' in res and res['documents']:
                    all_results.extend(res['documents'][0])
            
            return all_results[:n_results]

        except Exception as e:
            logger.error(f"RAG: General retrieval error: {e}")
            return []

# Export a shared instance for lazy loading
retriever = RAGRetriever()
