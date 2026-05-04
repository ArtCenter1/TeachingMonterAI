import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from notebooklm import NotebookLMClient, AudioFormat, AudioLength, VideoFormat, VideoStyle
from loguru import logger

class NotebookLMManager:
    def __init__(self):
        self.client: Optional[NotebookLMClient] = None
        self._init_lock = asyncio.Lock()

    async def _ensure_client(self) -> Optional[NotebookLMClient]:
        """Ensures the client is initialised lazily.
        
        Prioritises NOTEBOOKLM_AUTH_JSON env var so Docker containers work
        without needing the host's ~/.notebooklm filesystem mounted.
        """
        async with self._init_lock:
            if self.client:
                return self.client

            auth_json = os.getenv("NOTEBOOKLM_AUTH_JSON")
            try:
                if auth_json:
                    # Docker-friendly path: auth injected via .env
                    import tempfile, json as _json
                    _json.loads(auth_json)  # validate before writing
                    with tempfile.NamedTemporaryFile(
                        mode="w", suffix=".json", delete=False
                    ) as tmp:
                        tmp.write(auth_json)
                        tmp_path = tmp.name
                    self.client = await NotebookLMClient.from_storage(tmp_path)
                    logger.info("NotebookLMManager: Initialised from NOTEBOOKLM_AUTH_JSON env var.")
                else:
                    # Host path: from_storage reads ~/.notebooklm/storage_state.json
                    self.client = await NotebookLMClient.from_storage()
                    logger.info("NotebookLMManager: Successfully initialised from storage.")
                return self.client
            except Exception as e:
                logger.error(f"NotebookLMManager: Failed to initialise from storage: {e}")
                self.client = None
                return None


    async def create_notebook_for_topic(self, topic: str, domain: str) -> Optional[str]:
        """Creates a new notebook and returns the notebook_id."""
        client = await self._ensure_client()
        if not client:
            return None
        
        try:
            title = f"Teaching Monster: {topic} ({domain})"
            notebook = await client.notebooks.create(title=title)
            logger.info(f"NotebookLM: Created notebook '{title}' with ID {notebook.id}")
            return notebook.id
        except Exception as e:
            logger.error(f"NotebookLM: Failed to create notebook: {e}")
            return None

    async def add_sources(self, notebook_id: str, texts: List[str]):
        """Adds text sources to the notebook."""
        client = await self._ensure_client()
        if not client:
            return
        
        for i, text in enumerate(texts):
            try:
                # Truncate title for source
                source_title = f"Source {i+1}: {text[:30]}..."
                await client.sources.add_text(notebook_id, text, title=source_title)
                logger.debug(f"NotebookLM: Added source {i+1} to {notebook_id}")
            except Exception as e:
                logger.error(f"NotebookLM: Failed to add source {i+1}: {e}")

    async def generate_audio_overview(self, notebook_id: str, output_path: str) -> Optional[str]:
        """Generates and downloads the Audio Overview (Podcast)."""
        client = await self._ensure_client()
        if not client:
            return None
        
        try:
            logger.info(f"NotebookLM: Generating Audio Overview for {notebook_id}...")
            # Using DEEP_DIVE format for comprehensive educational content
            status = await client.artifacts.generate_audio(
                notebook_id, 
                audio_format=AudioFormat.DEEP_DIVE,
                audio_length=AudioLength.DEFAULT
            )
            
            # Wait for completion
            await client.artifacts.wait_for_completion(status.task_id)
            
            # Download the audio
            await client.artifacts.download_audio(notebook_id, output_path)
            logger.info(f"NotebookLM: Audio Overview saved to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"NotebookLM: Audio generation failed: {e}")
            return None

    async def ask_for_structured_facts(self, notebook_id: str, topic: str) -> List[Dict[str, Any]]:
        """Uses chat to extract structured facts from the notebook sources."""
        client = await self._ensure_client()
        if not client:
            return []
        
        prompt = f"""
        Act as a pedagogical expert. Based on the sources in this notebook, 
        extract 7-10 core educational facts about '{topic}' suitable for AP/IB students.
        
        Return ONLY a JSON array of objects with 'claim', 'citation', and 'confidence' (0.0-1.0).
        """
        
        try:
            response = await client.chat.ask(notebook_id, prompt)
            from .utils import extract_json
            facts = extract_json(response.text)
            return facts if isinstance(facts, list) else []
        except Exception as e:
            logger.error(f"NotebookLM: Chat fact extraction failed: {e}")
            return []

    async def get_video_plan(self, notebook_id: str) -> Optional[str]:
        """Generates a video overview plan if possible."""
        # Note: generate_video might return a video file or a plan. 
        # For now, we'll stick to audio + custom visuals to keep 'Teaching Monster' branding.
        pass

notebooklm_manager = NotebookLMManager()
