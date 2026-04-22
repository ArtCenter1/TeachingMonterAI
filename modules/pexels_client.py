import os
import requests
import hashlib
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
VIDEO_CACHE_DIR = os.path.join("temp", "cache_videos")

class PexelsClient:
    """
    Client for interacting with the Pexels Video API.
    Handles searching for educational B-roll and downloading fragments for rendering.
    """
    def __init__(self):
        self.pexels_key = PEXELS_API_KEY
        self.pixabay_key = PIXABAY_API_KEY
        self.pexels_url = "https://api.pexels.com/videos/search"
        self.pixabay_url = "https://pixabay.com/api/videos/"
        
        # Ensure cache directory exists
        os.makedirs(VIDEO_CACHE_DIR, exist_ok=True)
        
        if not self.pexels_key:
            logger.warning("PEXELS_API_KEY not configured.")
        if not self.pixabay_key:
            logger.debug("PIXABAY_API_KEY not configured (fallback source disabled).")

    def search_videos(self, query: str, min_duration: int = 5) -> list:
        """
        Searches Pexels first, then falls back to Pixabay.
        """
        results = self.search_pexels(query, min_duration)
        if not results and self.pixabay_key:
            logger.info(f"Pexels returned no results for '{query}'. Trying Pixabay...")
            results = self.search_pixabay(query, min_duration)
        return results

    def search_pexels(self, query: str, min_duration: int = 5, orientation: str = "landscape") -> list:
        if not self.pexels_key or not query:
            return []
            
        headers = {"Authorization": self.pexels_key}
        params = {
            "query": query,
            "per_page": 10,
            "orientation": orientation
        }
        
        try:
            response = requests.get(self.pexels_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            videos = []
            for v in data.get("videos", []):
                if v.get("duration", 0) >= min_duration:
                    files = v.get("video_files", [])
                    files.sort(key=lambda x: x.get("width", 0), reverse=True)
                    # Prefer HD/SD quality
                    target_file = next((f for f in files if f.get("quality") in ["hd", "sd"]), None)
                    if not target_file and files: target_file = files[0]
                    
                    if target_file and target_file.get("link"):
                        videos.append({
                            "id": f"pexels_{v['id']}",
                            "url": target_file["link"],
                            "duration": v["duration"],
                            "source": "pexels"
                        })
            return videos
        except Exception as e:
            logger.error(f"Pexels search failed: {e}")
            return []

    def search_pixabay(self, query: str, min_duration: int = 5) -> list:
        if not self.pixabay_key or not query:
            return []
            
        params = {
            "key": self.pixabay_key,
            "q": query,
            "video_type": "all",
            "per_page": 10
        }
        
        try:
            response = requests.get(self.pixabay_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            videos = []
            for v in data.get("hits", []):
                if v.get("duration", 0) >= min_duration:
                    # Pixabay returns multiple sizes in 'videos' dict
                    # sizes: large, medium, small, tiny
                    video_sizes = v.get("videos", {})
                    # Prefer medium (usually 1280x720) or large
                    best_size = video_sizes.get("medium") or video_sizes.get("large") or video_sizes.get("small")
                    
                    if best_size and best_size.get("url"):
                        videos.append({
                            "id": f"pixabay_{v['id']}",
                            "url": best_size["url"],
                            "duration": v["duration"],
                            "source": "pixabay"
                        })
            return videos
        except Exception as e:
            logger.error(f"Pixabay search failed: {e}")
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
        # Include source prefix to avoid collisions if identical hashes occur across sources
        prefix = "pexels" if "pexels.com" in url else "pixabay"
        file_path = os.path.join(VIDEO_CACHE_DIR, f"{prefix}_{url_hash}.mp4")
        
        # Check cache first
        if os.path.exists(file_path):
            if os.path.getsize(file_path) > 1024:
                logger.debug(f"VideoClient: Cache hit for {url}")
                return os.path.abspath(file_path)
        
        try:
            logger.info(f"VideoClient: Downloading B-roll from {url}...")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)
            
            logger.success(f"VideoClient: Downloaded successfully to {file_path}")
            return os.path.abspath(file_path)
            
        except Exception as e:
            logger.error(f"Pexels: Download failed for {url}: {e}")
            # Clean up partial download
            if os.path.exists(file_path):
                os.remove(file_path)
            return ""

# Shared instance for use across modules
pexels_client = PexelsClient()
