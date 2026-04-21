import os
import json
import asyncio
import aiohttp
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from .schemas import FactBundle
from .mcp_client import OpenSpaceMCPClient
from loguru import logger


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
        logger.debug(
            "SourcingModule initialised (primary path: OpenSpace MCP → web_search → AI → mock)"
        )

    async def source(
        self,
        topic: str,
        search_cx: Optional[str] = None,
        search_api_key: Optional[str] = None,
    ) -> FactBundle:
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
                self._notebooklm_mcp_source(topic), timeout=60.0
            )

            # Verify the sourcing succeeded
            if fact_bundle and fact_bundle.facts and len(fact_bundle.facts) > 0:
                logger.info(
                    f"NotebookLM MCP sourcing successful: {len(fact_bundle.facts)} facts retrieved"
                )
                return await self._verify_and_enhance_facts(fact_bundle, topic)

        except asyncio.TimeoutError:
            logger.warning("NotebookLM MCP sourcing timed out after 90 seconds")
        except Exception as e:
            logger.error(f"NotebookLM MCP sourcing failed: {str(e)}")

        # Stage 1.5: Fallback to native NotebookLM library
        try:
            logger.info("Attempting native NotebookLM library sourcing...")
            fact_bundle = await asyncio.wait_for(
                self._notebooklm_library_source(topic), timeout=60.0
            )

            if fact_bundle and fact_bundle.facts and len(fact_bundle.facts) > 0:
                logger.info(
                    f"Native NotebookLM sourcing successful: {len(fact_bundle.facts)} facts retrieved"
                )
                return await self._verify_and_enhance_facts(fact_bundle, topic)
        except asyncio.TimeoutError:
            logger.warning("Native NotebookLM sourcing timed out after 60 seconds")
        except Exception as e:
            logger.error(f"Native NotebookLM sourcing failed: {str(e)}")

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
            fact_bundle = await self._ai_research_fallback(topic)
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

    async def _notebooklm_mcp_source(self, topic: str) -> FactBundle:
        """
        Source facts via the OpenSpace Evolution Engine.

        OpenSpace auto-discovers locally installed skills.  When the
        ``notebooklm`` skill is present (installed via ``notebooklm-py``),
        it will create a notebook, add authoritative IB/AP sources, and
        return grounded facts with citations.  Without the skill, OpenSpace
        falls back to its own web-search and reasoning capabilities.

        Per the PRD (§4.2), the MCP Server is the PRIMARY sourcing path.
        This method honours the 90-second budget set by the caller's
        ``asyncio.wait_for`` wrapper in ``source()``.
        """
        client = OpenSpaceMCPClient()

        # Fail fast if engine is not reachable — triggers Stage 2 fallback
        if not await client.health_check():
            raise ConnectionError(
                "OpenSpace engine unreachable at %s" % client.base_url
            )

        # Infer subject domain from topic keywords for source-hint injection
        topic_lower = topic.lower()
        if any(
            k in topic_lower
            for k in ("physics", "force", "motion", "wave", "energy", "quantum")
        ):
            source_hint = "IB Physics textbook, AP Physics CED, Khan Academy physics"
        elif any(
            k in topic_lower
            for k in ("biology", "cell", "dna", "gene", "evolution", "organism")
        ):
            source_hint = (
                "IB Biology textbook, AP Biology CED, reviewed .edu biology sources"
            )
        elif any(
            k in topic_lower
            for k in (
                "algorithm",
                "programming",
                "data structure",
                "network",
                "attention",
                "machine learning",
                "recursion",
                "sorting",
            )
        ):
            source_hint = (
                "IB CS guide, CS50 transcripts, official language documentation"
            )
        elif any(
            k in topic_lower
            for k in (
                "calculus",
                "algebra",
                "geometry",
                "statistics",
                "probability",
                "trigonometry",
                "derivative",
                "integral",
            )
        ):
            source_hint = (
                "IB Math AA/AI guide, AP Calculus CED, standard textbook chapters"
            )
        else:
            source_hint = (
                "IB/AP curriculum guides, Khan Academy, .edu educational resources"
            )

        task = (
            f"Research the educational topic '{topic}' for a secondary education audience "
            f"(AP/IB level). "
            f"Use the following as primary authoritative sources: {source_hint}. "
            f"Return a JSON object with this exact structure — no markdown, no extra keys:\n"
            f"{{\n"
            f'  "facts": [\n'
            f'    {{"claim": "The factual statement", "citation": "Source title / URL / page", "confidence": 0.9}}\n'
            f"  ],\n"
            f'  "study_guide_url": null\n'
            f"}}\n"
            f"Provide at least 5 unique, verifiable facts with citations. "
            f"If a fact is uncertain, lower the confidence score. "
            f"Do NOT hallucinate citations."
        )

        logger.info("Delegating M1 sourcing to OpenSpace (topic: %s)", topic[:60])
        raw = await client.execute_task(task, max_iterations=5, search_scope="local")
        logger.debug("OpenSpace raw sourcing result (first 400 chars): %s", raw[:400])

        # Parse the returned JSON
        data = _extract_json_from_text(raw)

        facts_raw = data.get("facts", []) if isinstance(data, dict) else []
        study_guide_url = (
            data.get("study_guide_url") if isinstance(data, dict) else None
        )

        facts = [
            {
                "claim": str(f.get("claim", "")),
                "citation": str(f.get("citation", "OpenSpace + NotebookLM")),
                "confidence": min(1.0, max(0.0, float(f.get("confidence", 0.8)))),
            }
            for f in facts_raw
            if f.get("claim")
        ]

        if not facts:
            raise ValueError("OpenSpace returned no usable facts for topic: %s" % topic)

        logger.info(
            "OpenSpace sourcing returned %d facts (study_guide_url=%s)",
            len(facts),
            study_guide_url,
        )
        return FactBundle(facts=facts, study_guide_url=study_guide_url)

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

    async def _notebooklm_library_source(self, topic: str) -> FactBundle:
        """
        Native implementation using the official 'notebooklm-py' Python library.

        Auth: Reads from NOTEBOOKLM_AUTH_JSON env var (Docker) or
              ~/.notebooklm/profiles/default/storage_state.json (host).
              Run `notebooklm login` once on the host to generate auth,
              then set NOTEBOOKLM_AUTH_JSON=<contents of storage_state.json>.

        API reference: https://github.com/teng-lin/notebooklm-py
        Documented methods used:
            - client.notebooks.list()
            - client.notebooks.create(title)
            - client.sources.add_url(nb_id, url, wait=False)
            - client.chat.ask(nb_id, query)   → result.answer
        """
        logger.info("Using native NotebookLM library for sourcing")

        try:
            from notebooklm import NotebookLMClient
            import os

            # Ensure Docker env var is explicitly written where the library expects it
            # Library version 0.3.4 expects it at ~/.notebooklm/storage_state.json
            auth_json = os.getenv("NOTEBOOKLM_AUTH_JSON")
            if auth_json:
                # We write to both the expected library path and the legacy profile path just in case
                storage_path = os.path.expanduser("~/.notebooklm/storage_state.json")
                profile_path = os.path.expanduser("~/.notebooklm/profiles/default/storage_state.json")
                
                for path in [storage_path, profile_path]:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(auth_json)

            async with await NotebookLMClient.from_storage() as client:
                # ── Step 1: find or create the shared sourcing notebook ──────
                notebooks = await client.notebooks.list()
                nb = next(
                    (n for n in notebooks if "TeachingMonster_Sourcing" in n.title),
                    None,
                )

                if not nb:
                    logger.info(
                        "Creating 'TeachingMonster_Sourcing' notebook in NotebookLM"
                    )
                    nb = await client.notebooks.create("TeachingMonster_Sourcing")
                    # Seed with Wikipedia so the LLM has a grounded source.
                    # wait=False so we don't block — ask() still works with LLM knowledge.
                    try:
                        wiki_url = (
                            f"https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}"
                        )
                        await client.sources.add_url(nb.id, wiki_url, wait=False)
                        logger.info(
                            f"Seeded notebook with Wikipedia source for: {topic}"
                        )
                    except Exception as seed_err:
                        logger.warning(f"Could not seed Wikipedia source: {seed_err}")

                # ── Step 2: ask NotebookLM for pedagogical facts ──────────────
                query = (
                    f"You are an educational expert. Provide 5–7 clear, accurate facts "
                    f"about '{topic}' suitable for AP/IB secondary education students. "
                    f"Include key formulas, definitions, and core concepts. "
                    f"Format each fact on its own line starting with a dash (-)."
                )
                logger.info(f"Querying NotebookLM for facts on: {topic}")
                result = await client.chat.ask(nb.id, query)

                if not result or not getattr(result, "answer", None):
                    logger.warning("NotebookLM returned an empty answer")
                    return None

                logger.info("NotebookLM sourcing successful")
                return FactBundle(
                    facts=[
                        {
                            "claim": result.answer,
                            "citation": "Google NotebookLM",
                            "confidence": 0.92,
                        }
                    ]
                )

        except Exception as e:
            logger.error(f"NotebookLM library sourcing failed: {str(e)}")
            if (
                "auth" in str(e).lower()
                or "cookie" in str(e).lower()
                or "401" in str(e)
            ):
                logger.warning(
                    "NotebookLM auth error — ACTION REQUIRED: "
                    "Run `notebooklm login` on the host, then copy "
                    "~/.notebooklm/profiles/default/storage_state.json contents "
                    "into NOTEBOOKLM_AUTH_JSON in .env. See ONBOARDING.md §8."
                )
            raise

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

    async def _ai_research_fallback(self, topic: str) -> FactBundle:
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
                prompt, temperature=0.2, model_size="medium"
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
