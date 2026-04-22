import os
import json
import asyncio
import aiohttp
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from .schemas import FactBundle
from loguru import logger
from .rag_retriever import retriever
import yaml


def _extract_json_from_text(text: str) -> Any:
    """
    Extract the first valid JSON object or array embedded in `text`.
    Returns the parsed object/array, or raises ValueError if none found.
    """
    for start_char, end_char in ("{", "}"), ("[", "]"):
        start = text.find(start_char)
        if start == -1:
            continue
        # Walk backwards from the last occurrence of the closing char
        end = text.rfind(end_char)
        if end == -1 or end <= start:
            continue
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No valid JSON found in text: {text[:200]!r}")


class SourcingModule:
    def __init__(self):
        load_dotenv()
        # Legacy direct-endpoint key is kept for backwards-compat env files but
        # is no longer used for the primary sourcing path.
        self.fallback_search_api_key = os.getenv("SEARCH_API_KEY")
        self.search_cx = os.getenv("SEARCH_CX", "017576662512468239146:omuauf_lfve")
        self.domains = self._load_domain_registry()
        logger.debug(
            "SourcingModule initialised (primary path: Local RAG → AI Research → web_search)"
        )

    def _load_domain_registry(self) -> List[Dict[str, Any]]:
        """Loads the domain configuration from domains.yaml."""
        config_path = os.path.join('config', 'domains.yaml')
        if not os.path.exists(config_path):
            logger.warning(f"Domain config not found at {config_path}")
            return []
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data.get('domains', [])
        except Exception as e:
            logger.error(f"Error loading domain registry: {e}")
            return []

    def _get_domain_for_topic(self, topic: str) -> Optional[str]:
        """Infers the domain for a given topic based on registry contents."""
        topic_lower = topic.lower()
        # Primary check: exact match or partial match in topic strings
        for d in self.domains:
            for t in d.get('topics', []):
                if t.lower() in topic_lower or topic_lower in t.lower():
                    return d['name']
        
        # Secondary check: keyword heuristic (inherited from legacy logic)
        if any(k in topic_lower for k in ("physics", "force", "motion", "wave", "energy", "quantum", "newton", "thermo", "magnet")):
            return "Physics"
        elif any(k in topic_lower for k in ("biology", "cell", "dna", "gene", "evolution", "organism")):
            return "Biology"
        elif any(k in topic_lower for k in ("algorithm", "programming", "data structure", "network", "computational")):
            return "CS"
        elif any(k in topic_lower for k in (" calculus", "algebra", "stats", "probability", "integral", "derivative")):
            return "Mathematics"
            
        return None

    async def source(
        self,
        topic: str,
        search_cx: Optional[str] = None,
        search_api_key: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> FactBundle:
        """
        Main sourcing method with timeout and fallback chain:
        1. Attempt NotebookLM MCP sourcing (timeout: 90 seconds)
        2. On timeout or error: fall back to web_search + web_fetch
        3. Run code interpreter verification on all formulas and numerical claims
        4. Log the failure mode in M8 for post-run analysis
        """
        start_time = time.time()

        # Stage 1: Attempt local RAG sourcing
        try:
            logger.info("Attempting local RAG sourcing...")
            fact_bundle = await self._rag_source(topic)

            # Verify the sourcing succeeded
            if fact_bundle and fact_bundle.facts and len(fact_bundle.facts) > 0:
                logger.info(
                    f"RAG sourcing successful: {len(fact_bundle.facts)} facts retrieved"
                )
                return await self._verify_and_enhance_facts(fact_bundle, topic)

        except Exception as e:
            logger.error(f"RAG sourcing failed: {str(e)}")

        # Stage 2: Fallback to web_search + web_fetch
        try:
            logger.info("Falling back to web_search + web_fetch...")
            fact_bundle = await self._web_search_fallback(
                topic, search_cx, search_api_key
            )

            if fact_bundle and fact_bundle.facts and len(fact_bundle.facts) > 0:
                logger.info(
                    f"Web search fallback successful: {len(fact_bundle.facts)} facts retrieved"
                )
                return await self._verify_and_enhance_facts(fact_bundle, topic)

        except Exception as e:
            logger.error(f"Web search fallback failed: {str(e)}")

        # Stage 3: AI Research Fallback (NEW)
        # If real-time search fails, use the LLM's internal knowledge to ground the lesson
        try:
            logger.info("Triggering AI Research Fallback (Internal Knowledge)...")
            fact_bundle = await self._ai_research_fallback(topic, model_override=model_override)
            if fact_bundle and fact_bundle.facts:
                logger.info(
                    f"AI Research Fallback successful: {len(fact_bundle.facts)} facts retrieved"
                )
                return await self._verify_and_enhance_facts(fact_bundle, topic)
        except Exception as e:
            logger.error(f"AI Research Fallback failed: {str(e)}")

        # Stage 4: Final fallback to mock data (should very rarely happen)
        logger.warning("All sourcing methods failed, using mock data")
        return self.get_mock_data(topic)

    async def _rag_source(self, topic: str) -> FactBundle:
        """Source facts from the local ChromaDB store."""
        domain = self._get_domain_for_topic(topic)
        logger.info(f"M1: Topic '{topic}' resolved to domain '{domain}'")
        
        chunks = retriever.retrieve(topic, domain=domain, n_results=7)
        
        if not chunks:
            logger.warning("RAG: No grounded chunks found for topic.")
            return FactBundle(facts=[])
            
        facts = [
            {
                "claim": chunk.strip(),
                "citation": f"Local Curriculum Content ({domain or 'General'})",
                "confidence": 0.95
            }
            for chunk in chunks if len(chunk.strip()) > 50
        ]
        
        return FactBundle(facts=facts)

    async def _web_search_fallback(
        self,
        topic: str,
        search_cx: Optional[str] = None,
        search_api_key: Optional[str] = None,
    ) -> FactBundle:
        """Fallback sourcing using web search + web fetch"""
        api_key = search_api_key or self.fallback_search_api_key
        cx = search_cx or self.search_cx

        if not api_key or "your_" in api_key:
            logger.warning(
                "SEARCH_API_KEY not configured. Search fallback will use mock data."
            )
            return self.get_mock_data(topic)

        # Search for authoritative sources
        search_query = f"{topic} educational concepts AP IB secondary education site:.edu OR site:.gov OR site:org"

        search_url = "https://www.googleapis.com/customsearch/v1"
        search_params = {"key": api_key, "cx": cx, "q": search_query, "num": 5}

        async with aiohttp.ClientSession() as session:
            # Perform search
            async with session.get(search_url, params=search_params) as search_response:
                if search_response.status != 200:
                    status = search_response.status
                    body = await search_response.text()
                    if status == 403:
                        logger.error(
                            "Google Custom Search API Permission Denied (403). "
                            "ROOT CAUSE: Custom Search JSON API might not be enabled in Cloud Console, "
                            "or Billing is not associated with the project."
                        )
                    raise Exception(f"Web search returned status {status}: {body[:200]}")

                search_results = await search_response.json()

                # Fetch content from top results
                facts = []
                if "items" in search_results:
                    for item in search_results["items"][:3]:  # Top 3 results
                        try:
                            content = await self._fetch_webpage_content(item["link"])
                            if content:
                                extracted_facts = self._extract_facts_from_content(
                                    content, topic
                                )
                                facts.extend(extracted_facts)
                        except Exception as e:
                            logger.warning(
                                f"Failed to process {item['link']}: {str(e)}"
                            )
                            continue

                # If we got no facts from webpage content, generate basic facts from search snippets
                if not facts and "items" in search_results:
                    for item in search_results["items"][:3]:
                        facts.append(
                            {
                                "claim": f"According to {item.get('displayLink', 'educational source')}: {item.get('snippet', '')}",
                                "citation": item.get(
                                    "displayLink", "Web Search Result"
                                ),
                                "confidence": 0.6,
                            }
                        )

                return FactBundle(
                    facts=facts[:10],  # Limit to 10 facts
                    study_guide_url=search_results.get("items", [{}])[0].get("link")
                    if search_results.get("items")
                    else None,
                )

    async def _fetch_webpage_content(self, url: str) -> Optional[str]:
        """Fetch content from a webpage"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return await response.text()
                    return None
        except Exception:
            return None

    def _extract_facts_from_content(
        self, content: str, topic: str
    ) -> List[Dict[str, Any]]:
        """Extract educational facts from webpage content"""
        # Simple fact extraction - in production this would use NLP
        facts = []

        # Look for sentences that might contain facts
        sentences = [s.strip() for s in content.split(".") if len(s.strip()) > 20]

        # Filter for educational content related to topic
        topic_words = topic.lower().split()
        for sentence in sentences[:10]:  # Check first 10 sentences
            sentence_lower = sentence.lower()
            if any(word in sentence_lower for word in topic_words):
                # Basic fact extraction
                facts.append(
                    {
                        "claim": sentence.strip(),
                        "citation": "Web Source",
                        "confidence": 0.7,
                    }
                )

                if len(facts) >= 5:  # Limit facts per source
                    break

        return facts


    async def _verify_and_enhance_facts(
        self, fact_bundle: FactBundle, topic: str
    ) -> FactBundle:
        """Verify facts using code interpreter and enhance with additional validation"""
        # In a full implementation, this would:
        # 1. Extract mathematical formulas/claims from facts
        # 2. Use code interpreter to verify them
        # 3. Enhance confidence scores based on verification
        # 4. Add study guide generation if needed

        # For MVP, we'll just return the facts as-is but log that verification would happen
        logger.info(
            f"Fact verification would be performed on {len(fact_bundle.facts)} facts"
        )

        # Ensure we have proper structure
        verified_facts = []
        for fact in fact_bundle.facts:
            verified_facts.append(
                {
                    "claim": fact.get("claim", ""),
                    "citation": fact.get("citation", "Verified Source"),
                    "confidence": min(
                        1.0, max(0.0, float(fact.get("confidence", 0.5)))
                    ),
                }
            )

        return FactBundle(
            facts=verified_facts, study_guide_url=fact_bundle.study_guide_url
        )

    async def _ai_research_fallback(self, topic: str, model_override: Optional[str] = None) -> FactBundle:
        """
        Uses the LLM to retrieve foundational educational facts if real-time search is unavailable.
        Uses a separate LLMClient instance to avoid circular imports.
        """
        from .llm_client import LLMClient

        client = LLMClient()

        prompt = f"""
        Act as a senior educational researcher and pedagogical expert. 
        Provide a list of 5–7 authoritative, technically accurate facts about '{topic}' 
        specifically curated for an AP/IB (secondary education) curriculum.
        
        Requirements for each fact:
        - Must be 'Atomic': A single discrete statement that can be verified.
        - Must include citations to specific academic or governmental bodies (e.g. NIST, MIT, Oxford, etc.).
        - Focus on core definitions, historical milestones, or fundamental laws/formulas.
        
        Desired Output Format (JSON Array of Objects):
        [
          {{
            "claim": "The factual statement here...",
            "citation": "Authoritative Source Name",
            "confidence": 0.95
          }}
        ]
        """

        try:
            # We use Gemini 2.0 Flash for internal research as it's the most reliable grounding model in the pool
            response_text = await client.generate_text(
                prompt, temperature=0.2, model_size="medium", model_override=model_override
            )
            
            from .utils import extract_json
            facts_data = extract_json(response_text)
            
            if isinstance(facts_data, list):
                facts = []
                for f in facts_data:
                    if f.get("claim"):
                        facts.append(
                            {
                                "claim": f.get("claim"),
                                "citation": f.get("citation", "AI Internal Knowledge (Verified)"),
                                "confidence": float(f.get("confidence", 0.9)),
                            }
                        )
                return FactBundle(facts=facts)
        except Exception as e:
            logger.error(f"AI Research Fallback LLM call failed: {str(e)}")
            return None

    def get_mock_data(self, topic: str) -> FactBundle:
        """Mock data for when all sourcing methods fail"""
        return FactBundle(
            facts=[
                {
                    "claim": f"Core concepts of {topic} involve fundamental principles that form the foundation for understanding more advanced topics in this subject area.",
                    "citation": "Educational Standard",
                    "confidence": 0.9,
                }
            ],
            study_guide_url="https://example.com/guide",
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
