import os
import shutil
import pytest
import yaml
from modules.rag_retriever import RAGRetriever
from scripts.ingest_rag import ingest, CHROMA_PATH as INGEST_CHROMA_PATH

# Mock domain for testing
TEST_DOMAIN_CONFIG = {
    "domains": [
        {
            "name": "Test Biology",
            "level": "secondary",
            "topics": ["Photosynthesis", "Mitochondria"]
        }
    ]
}

@pytest.fixture
def clean_chroma():
    """Ensures a clean chroma_db state for tests."""
    test_chroma = os.path.join('temp', 'test_chroma_db')
    if os.path.exists(test_chroma):
        shutil.rmtree(test_chroma)
    os.makedirs(test_chroma, exist_ok=True)
    return test_chroma

def test_ingestion_and_retrieval(clean_chroma, monkeypatch):
    """
    End-to-end test for RAG system:
    1. Create a dummy domains.yaml
    2. Run ingestion (mocking LLM if possible, but here we'll let it call if needed or use existing files)
    3. Verify retrieve() returns relevant content
    """
    # 1. Setup mock config
    mock_config_path = os.path.join('config', 'domains_test.yaml')
    with open(mock_config_path, 'w', encoding='utf-8') as f:
        yaml.dump(TEST_DOMAIN_CONFIG, f)
    
    # Patch paths in ingestion script
    monkeypatch.setattr("scripts.ingest_rag.CHROMA_PATH", clean_chroma)
    monkeypatch.setenv("GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY")) # Ensure key is available
    
    # 2. Run Ingestion
    # Note: This will call LLM unless files exist in resources/curriculum/test_biology/
    # For a fast test, we'll create a dummy file
    test_file_dir = os.path.join('resources', 'curriculum', 'test_biology')
    os.makedirs(test_file_dir, exist_ok=True)
    test_file_path = os.path.join(test_file_dir, 'photosynthesis.md')
    with open(test_file_path, 'w', encoding='utf-8') as f:
        f.write("Photosynthesis is a process used by plants and other organisms to convert light energy into chemical energy.")
    
    # Mocking config path inside ingest()
    import scripts.ingest_rag
    original_config = os.path.join('config', 'domains.yaml')
    # Backup original or just point to test one
    # We'll patch the path in ingest() via monkeypatching 'config/domains.yaml' check
    
    # Actually, simpler to just temporarily replace config/domains.yaml
    shutil.copy(original_config, 'config/domains.yaml.bak')
    shutil.copy(mock_config_path, 'config/domains.yaml')
    
    try:
        ingest()
        
        # 3. Verify Retrieval
        # Patch RAGRetriever path
        monkeypatch.setattr("modules.rag_retriever.CHROMA_PATH", clean_chroma)
        retriever = RAGRetriever()
        # Reset singleton for test
        retriever._initialized = False 
        retriever.__init__()
        
        results = retriever.retrieve("What is photosynthesis?", domain="Test Biology")
        
        assert len(results) > 0
        assert "Photosynthesis" in results[0]
        print("\n[SUCCESS] RAG Ingestion and Retrieval verified.")
        
    finally:
        # Cleanup
        if os.path.exists('config/domains.yaml.bak'):
            shutil.move('config/domains.yaml.bak', 'config/domains.yaml')
        if os.path.exists(mock_config_path):
            os.remove(mock_config_path)

if __name__ == "__main__":
    # If run directly without pytest
    test_ingestion_and_retrieval(os.path.join('temp', 'test_chroma_db'), None)
