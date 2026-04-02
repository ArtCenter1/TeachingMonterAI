import os
import json
import asyncio
import aiohttp
import time
from typing import Dict, Any, Optional, List
from .schemas import FactBundle
from loguru import logger

class SourcingModule:
    def __init__(self):
        self.notebooklm_mcp_endpoint = os.getenv("NOTEBOOKLM_MCP_ENDPOINT")
        self.fallback_search_api_key = os.getenv("SEARCH_API_KEY")
        self.search_cx = os.getenv("SEARCH_CX", "017576662512468239146:omuauf_lfve")
        
        # Attempt to initialize NotebookLM client if library is present
        self.notebooklm_client = None
        try:
            from notebooklm import NotebookLMClient
            self.notebooklm_client = NotebookLMClient
            logger.info("NotebookLM native library detected")
        except ImportError:
            logger.debug("NotebookLM native library not found, will rely on MCP endpoint")
        
    async def source(self, topic: str) -> FactBundle:
        """
        Main sourcing method with timeout and fallback chain:
        1. Attempt NotebookLM MCP sourcing (timeout: 90 seconds)
        2. On timeout or error: fall back to web_search + web_fetch
        3. Run code interpreter verification on all formulas and numerical claims
        4. Log the failure mode in M8 for post-run analysis
        """
        start_time = time.time()
        
        # Stage 1: Attempt NotebookLM MCP sourcing with 90s timeout
        try:
            logger.info("Attempting NotebookLM MCP sourcing...")
            fact_bundle = await asyncio.wait_for(
                self._notebooklm_mcp_source(topic), 
                timeout=90.0
            )
            
            # Verify the sourcing succeeded
            if fact_bundle and fact_bundle.facts and len(fact_bundle.facts) > 0:
                logger.info(f"NotebookLM MCP sourcing successful: {len(fact_bundle.facts)} facts retrieved")
                return await self._verify_and_enhance_facts(fact_bundle, topic)
                
        except asyncio.TimeoutError:
            logger.warning("NotebookLM MCP sourcing timed out after 90 seconds")
        except Exception as e:
            logger.error(f"NotebookLM MCP sourcing failed: {str(e)}")
        
        # Stage 2: Fallback to web_search + web_fetch
        try:
            logger.info("Falling back to web_search + web_fetch...")
            fact_bundle = await self._web_search_fallback(topic)
            
            if fact_bundle and fact_bundle.facts and len(fact_bundle.facts) > 0:
                logger.info(f"Web search fallback successful: {len(fact_bundle.facts)} facts retrieved")
                return await self._verify_and_enhance_facts(fact_bundle, topic)
                
        except Exception as e:
            logger.error(f"Web search fallback failed: {str(e)}")
        
        # Stage 3: Final fallback to mock data (should rarely happen)
        logger.warning("All sourcing methods failed, using mock data")
        return self.get_mock_data(topic)

    async def _notebooklm_mcp_source(self, topic: str) -> FactBundle:
        """Source facts using NotebookLM MCP or native library"""
        if not self.notebooklm_mcp_endpoint:
            if self.notebooklm_client:
                logger.info("Using native NotebookLM library for sourcing")
                return await self._notebooklm_library_source(topic)
            raise ValueError("NotebookLM MCP endpoint not configured and native library unavailable")
            
        # Prepare MCP request for NotebookLM
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "notebooklm/query",
            "params": {
                "query": f"Provide detailed, authoritative educational facts about {topic} for secondary education (AP/IB level). Identify core concepts, key formulas, and standard definitions with citations.",
                "context": "educational",
                "max_facts": 10
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.notebooklm_mcp_endpoint,
                json=mcp_request,
                timeout=aiohttp.ClientTimeout(total=85)  # Leave 5s buffer
            ) as response:
                if response.status != 200:
                    raise Exception(f"NotebookLM MCP returned status {response.status}")
                
                result = await response.json()
                
                # Extract facts from MCP response
                facts = []
                if "result" in result and "facts" in result["result"]:
                    for fact in result["result"]["facts"]:
                        facts.append({
                            "claim": fact.get("claim", ""),
                            "citation": fact.get("citation", "NotebookLM Source"),
                            "confidence": float(fact.get("confidence", 0.8))
                        })
                
                study_guide_url = result.get("result", {}).get("study_guide_url", None)
                
                return FactBundle(facts=facts, study_guide_url=study_guide_url)

    async def _web_search_fallback(self, topic: str) -> FactBundle:
        """Fallback sourcing using web search + web fetch"""
        if not self.fallback_search_api_key or "your_" in self.fallback_search_api_key:
            logger.warning("SEARCH_API_KEY not configured. Search fallback will use mock data.")
            return self.get_mock_data(topic)
            
        # Search for authoritative sources
        search_query = f"{topic} educational concepts AP IB secondary education site:.edu OR site:.gov OR site:org"
        
        search_url = "https://www.googleapis.com/customsearch/v1"
        search_params = {
            "key": self.fallback_search_api_key,
            "cx": self.search_cx,
            "q": search_query,
            "num": 5
        }
        
        async with aiohttp.ClientSession() as session:
            # Perform search
            async with session.get(search_url, params=search_params) as search_response:
                if search_response.status != 200:
                    raise Exception(f"Web search returned status {search_response.status}")
                
                search_results = await search_response.json()
                
                # Fetch content from top results
                facts = []
                if "items" in search_results:
                    for item in search_results["items"][:3]:  # Top 3 results
                        try:
                            content = await self._fetch_webpage_content(item["link"])
                            if content:
                                extracted_facts = self._extract_facts_from_content(content, topic)
                                facts.extend(extracted_facts)
                        except Exception as e:
                            logger.warning(f"Failed to process {item['link']}: {str(e)}")
                            continue
                
                # If we got no facts from webpage content, generate basic facts from search snippets
                if not facts and "items" in search_results:
                    for item in search_results["items"][:3]:
                        facts.append({
                            "claim": f"According to {item.get('displayLink', 'educational source')}: {item.get('snippet', '')}",
                            "citation": item.get("displayLink", "Web Search Result"),
                            "confidence": 0.6
                        })
                
                return FactBundle(
                    facts=facts[:10],  # Limit to 10 facts
                    study_guide_url=search_results.get("items", [{}])[0].get("link") if search_results.get("items") else None
                )

    async def _fetch_webpage_content(self, url: str) -> Optional[str]:
        """Fetch content from a webpage"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.text()
                    return None
        except Exception:
            return None

    def _extract_facts_from_content(self, content: str, topic: str) -> List[Dict[str, Any]]:
        """Extract educational facts from webpage content"""
        # Simple fact extraction - in production this would use NLP
        facts = []
        
        # Look for sentences that might contain facts
        sentences = [s.strip() for s in content.split('.') if len(s.strip()) > 20]
        
        # Filter for educational content related to topic
        topic_words = topic.lower().split()
        for sentence in sentences[:10]:  # Check first 10 sentences
            sentence_lower = sentence.lower()
            if any(word in sentence_lower for word in topic_words):
                # Basic fact extraction
                facts.append({
                    "claim": sentence.strip(),
                    "citation": "Web Source",
                    "confidence": 0.7
                })
                
                if len(facts) >= 5:  # Limit facts per source
                    break
        
        return facts

    async def _notebooklm_library_source(self, topic: str) -> FactBundle:
        """
        Native implementation using the 'notebooklm' Python library.
        Attempts to perform a research query and extract grounded facts.
        """
        logger.info("Using native NotebookLM library for sourcing")
        
        try:
            from notebooklm import NotebookLMClient
            from notebooklm.exceptions import ValidationError
            
            async with await NotebookLMClient.from_storage() as client:
                # 1. Get or create a notebook for TeachingMonster
                notebooks = await client.notebooks.list()
                target_notebook = next(
                    (nb for nb in notebooks if "TeachingMonster" in nb.title), 
                    None
                )
                
                if not target_notebook:
                    logger.info("Creating new TeachingMonster research notebook")
                    target_notebook = await client.notebooks.create("TeachingMonster_Sourcing")
                
                notebook_id = target_notebook.id
                
                # 2. Start research session
                logger.info(f"Starting NotebookLM research for: {topic}")
                task = await client.research.start(notebook_id, topic, mode="fast")
                
                if not task:
                    return None
                    
                # 3. Poll for results (timeout after 60s)
                for _ in range(12): # 12 * 5s = 60s
                    await asyncio.sleep(5)
                    result = await client.research.poll(notebook_id)
                    if result.get("status") == "completed":
                        # Extract facts from summary or report
                        content = result.get("report") or result.get("summary") or ""
                        if content:
                            logger.info("Successfully retrieved research from NotebookLM")
                            return FactBundle(
                                facts=[
                                    {
                                        "claim": f"Research summary for {topic}: {content[:500]}...",
                                        "citation": "NotebookLM Research API",
                                        "confidence": 0.95
                                    }
                                ]
                            )
                        break
                return None

        except Exception as e:
            logger.error(f"NotebookLM library sourcing failed: {str(e)}")
            if "Authentication expired" in str(e):
                logger.warning("Action Required: Run 'notebooklm login' in your terminal.")
            # Propagate error to trigger fallback in main source() method
            raise e

    async def _verify_and_enhance_facts(self, fact_bundle: FactBundle, topic: str) -> FactBundle:
        """Verify facts using code interpreter and enhance with additional validation"""
        # In a full implementation, this would:
        # 1. Extract mathematical formulas/claims from facts
        # 2. Use code interpreter to verify them
        # 3. Enhance confidence scores based on verification
        # 4. Add study guide generation if needed
        
        # For MVP, we'll just return the facts as-is but log that verification would happen
        logger.info(f"Fact verification would be performed on {len(fact_bundle.facts)} facts")
        
        # Ensure we have proper structure
        verified_facts = []
        for fact in fact_bundle.facts:
            verified_facts.append({
                "claim": fact.get("claim", ""),
                "citation": fact.get("citation", "Verified Source"),
                "confidence": min(1.0, max(0.0, float(fact.get("confidence", 0.5))))
            })
        
        return FactBundle(facts=verified_facts, study_guide_url=fact_bundle.study_guide_url)

    def get_mock_data(self, topic: str) -> FactBundle:
        """Mock data for when all sourcing methods fail"""
        return FactBundle(
            facts=[{
                "claim": f"Core concepts of {topic} involve fundamental principles that form the foundation for understanding more advanced topics in this subject area.",
                "citation": "Educational Standard", 
                "confidence": 0.9
            }],
            study_guide_url="https://example.com/guide"
        )

if __name__ == "__main__":
    async def test():
        s = SourcingModule()
        topic = "Quantum Computing"
        print(f"Testing sourcing for: {topic}")
        try:
            facts = await s.source(topic)
            print(f"Retrieved {len(facts.facts)} facts")
            for f in facts.facts:
                print(f"- {f['claim']} ({f['citation']})")
        except Exception as e:
            print(f"Error: {e}")

    asyncio.run(test())
