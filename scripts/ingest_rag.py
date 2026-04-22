import chromadb
from chromadb.config import Settings

import os
import sys
import yaml
import asyncio
import hashlib
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.llm_client import LLMClient

# Instantiate the shared LLM client (uses OpenRouter + Gemini pool, not raw API)
_llm = LLMClient()

# Setup Directories
CURRICULUM_DIR = os.path.join('resources', 'curriculum')
CHROMA_PATH = os.path.join('temp', 'chroma_db')

def slugify(text: str) -> str:
    """Simple slugifier for file paths and collections."""
    return text.lower().replace(" ", "_").replace("/", "_").replace("'", "").replace("-", "_")

def generate_curriculum(domain: str, topic: str, level: str) -> str:
    """Calls LLM to generate a comprehensive curriculum summary for a topic."""
    prompt = f"""
You are an expert curriculum writer for {level}-level education.
Write a comprehensive teaching summary for the topic: '{topic}' (subject: {domain}).
Cover: core concepts, common student misconceptions, key vocabulary,
worked examples with step-by-step solutions, and 2-3 memorable analogies.
Length: ~1,500 words. Format: plain prose (no headers, no markdown bolding of everything).
Simply provide the high-quality educational text.
"""
    print(f"  [LLM] Generating curriculum for: {domain} / {topic}...")
    try:
        result = asyncio.run(_llm.generate_text(
            prompt=prompt,
            temperature=0.4,
            max_tokens=2048,
            model_size="medium",
        ))
        return result
    except Exception as e:
        print(f"  [ERROR] LLM generation failed: {e}")
        return f"Error generating content for {topic}."

def get_or_create_curriculum(domain: str, topic: str, level: str) -> tuple:
    """Retrieves existing file or generates new one via LLM."""
    domain_slug = slugify(domain)
    topic_slug = slugify(topic)
    
    domain_dir = os.path.join(CURRICULUM_DIR, domain_slug)
    os.makedirs(domain_dir, exist_ok=True)
    
    file_path = os.path.join(domain_dir, f"{topic_slug}.md")
    
    if os.path.exists(file_path):
        print(f"  [DISK] Found existing file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read(), "manual"
    
    content = generate_curriculum(domain, topic, level)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return content, "auto_generated"

def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 300) -> List[str]:
    """Splits text into overlapping chunks for RAG."""
    chunks = []
    if len(text) <= chunk_size:
        return [text]
        
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start += (chunk_size - overlap)
    return chunks

def ingest():
    """Main ingestion pipeline."""
    config_path = os.path.join('config', 'domains.yaml')
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found. Run setup_domains.py first.")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    domains = config.get('domains', [])
    if not domains:
        print("No domains found in config.")
        return

    print(f"--- Teaching Monster RAG Ingestion ---")
    print(f"Found {len(domains)} subject domains.")

    # Initialize Chroma
    os.makedirs(CHROMA_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    
    # We'll use a local embedding function if possible to avoid API overhead during search later
    # But for ingestion, we use Chroma's default or we can specify the one we want.
    # The plan standardizes on all-MiniLM-L6-v2.
    from chromadb.utils import embedding_functions
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

    for domain in domains:
        domain_name = domain['name']
        level = domain['level']
        topics = domain['topics']
        domain_slug = slugify(domain_name)
        
        print(f"\nProcessing Domain: {domain_name} (Level: {level})")
        
        # Unique collection per domain
        collection_name = f"domain_{domain_slug}"
        # Clean collection if it exists to ensure freshness
        try:
            client.delete_collection(name=collection_name)
            print(f"  [DB] Resetting collection: {collection_name}")
        except:
            pass
            
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=sentence_transformer_ef,
            metadata={"hnsw:space": "cosine"}
        )

        for topic in topics:
            content, source_type = get_or_create_curriculum(domain_name, topic, level)
            chunks = chunk_text(content)
            
            ids = [f"{domain_slug}_{slugify(topic)}_{i}" for i in range(len(chunks))]
            metadatas = [{
                "domain": domain_name,
                "level": level,
                "topic": topic,
                "source": source_type,
                "chunk_index": i
            } for i in range(len(chunks))]
            
            collection.add(
                documents=chunks,
                metadatas=metadatas,
                ids=ids
            )
            print(f"    [OK] Ingested {len(chunks)} chunks for topic: {topic}")

    print("\n[DONE] RAG Ingestion complete. Knowledge base is ready.")

if __name__ == "__main__":
    ingest()
