import os
import requests
import hashlib
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
VIDEO_CACHE_DIR = os.path.join("temp", "cache_videos")

class PexelsClient:
    """
    Client for interacting with the Pexels Video API.
    Handles searching for educational B-roll and downloading fragments for rendering.
    """
    def __init__(self):
        self.api_key = PEXELS_API_KEY
        self.base_url = "https://api.pexels.com/videos/search"
        
        # Ensure cache directory exists
        os.makedirs(VIDEO_CACHE_DIR, exist_ok=True)
        
        if not self.api_key or "your_" in self.api_key:
            logger.warning("PEXELS_API_KEY not configured. Visuals will fall back to static slides.")

    def search_videos(self, query: str, min_duration: int = 5, orientation: str = "landscape") -> list:
        """
        Searches for videos on Pexels based on keywords.
        Returns a list of dictionaries with video metadata and direct download URLs.
        """
        if not self.api_key or not query:
            return []
            
        headers = {"Authorization": self.api_key}
        # per_page 15 gives us enough variety to choose the best quality
        params = {
            "query": query,
            "per_page": 15,
            "orientation": orientation
        }
        
        try:
            logger.info(f"Pexels: Searching for '{query}'...")
            response = requests.get(self.base_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            videos = []
            for v in data.get("videos", []):
                # Filter by duration to ensure it covers the segment
                if v.get("duration", 0) >= min_duration:
                    # Select the best quality available (prefer HD over SD)
                    files = v.get("video_files", [])
                    # Sort files by width descending to get highest resolution available
                    files.sort(key=lambda x: x.get("width", 0), reverse=True)
                    
                    # We usually want something around 1280x720 or 1920x1080 for the pipeline
                    # MPT pattern: filter out 4K if we want to save bandwidth, or just take the best.
                    target_file = next((f for f in files if f.get("quality") in ["hd", "sd"]), None)
                    
                    # Fallback to the first available if no 'hd'/'sd' label
                    if not target_file and files:
                        target_file = files[0]
                    
                    if target_file and target_file.get("link"):
                        videos.append({
                            "id": v["id"],
                            "url": target_file["link"],
                            "duration": v["duration"],
                            "width": target_file.get("width"),
                            "height": target_file.get("height"),
                            "query": query
                        })
            
            logger.debug(f"Pexels: Found {len(videos)} suitable videos for '{query}'")
            return videos

        except Exception as e:
            logger.error(f"Pexels: Search failed for query '{query}': {e}")
            return []

    def download_video(self, url: str) -> str:
        """
        Downloads a video file from Pexels and saves it to the local cache.
        Returns the absolute path to the downloaded file, or empty string on failure.
        """
        if not url:
            return ""
            
        # Generate a unique stable filename based on the URL
        url_hash = hashlib.md5(url.encode()).hexdigest()
        file_path = os.path.join(VIDEO_CACHE_DIR, f"pexels_{url_hash}.mp4")
        
        # Check cache first
        if os.path.exists(file_path):
            # Basic sanity check: is the file > 1KB?
            if os.path.getsize(file_path) > 1024:
                logger.debug(f"Pexels: Cache hit for {url}")
                return os.path.abspath(file_path)
        
        try:
            logger.info(f"Pexels: Downloading B-roll from {url}...")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)
            
            logger.success(f"Pexels: Downloaded successfully to {file_path}")
            return os.path.abspath(file_path)
            
        except Exception as e:
            logger.error(f"Pexels: Download failed for {url}: {e}")
            # Clean up partial download
            if os.path.exists(file_path):
                os.remove(file_path)
            return ""

# Shared instance for use across modules
pexels_client = PexelsClient()
