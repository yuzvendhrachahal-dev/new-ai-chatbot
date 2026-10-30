import re
import uuid
import math
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Tuple
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.database import get_knowledge_collection, init_db_indexes
from app.core.config import settings

logger = logging.getLogger(__name__)

# Approved curated AstroVed Vedic Astrology Reference Knowledge Base
# Used strictly when approved AstroVed reference material is ingested
APPROVED_KNOWLEDGE_FIXTURES = [
    {
        "title": "Vedic Astrology Principles and the 12 Houses (Bhavas)",
        "source": "https://www.astroved.com/articles/12-houses-in-vedic-astrology",
        "category": "houses_bhavas",
        "tags": ["houses", "bhavas", "lagna", "career", "relationships", "dharma", "tanu", "karma"],
        "content": (
            "In Vedic Astrology (Jyotish), the horoscope (Kundli) is divided into 12 Bhavas (Houses). "
            "1st House (Tanu Bhava/Lagna) represents personality, vitality, and physical constitution. "
            "2nd House (Dhana Bhava) governs accumulated wealth, speech, and family lineage. "
            "4th House (Sukha Bhava) governs mother, inner contentment, vehicles, and real estate. "
            "7th House (Kalatra Bhava) governs marriage, partnerships, and legal unions. "
            "9th House (Bhagya Bhava) represents fortune, dharma, guru, and father. "
            "10th House (Karma Bhava) rules professional career, reputation, authority, and public accomplishments. "
            "11th House (Labha Bhava) determines gains, cash flow, ambitions, and elder siblings."
        )
    },
    {
        "title": "Vimshottari Dasha Cycles and Planetary Periods",
        "source": "https://www.astroved.com/articles/vimshottari-dasha-system",
        "category": "planetary_dashas",
        "tags": ["dasha", "mahadasha", "antardasha", "timing", "ketu", "saturn", "jupiter", "vimshottari"],
        "content": (
            "The Vimshottari Dasha cycle spans 120 years across all nine planetary rulers (Navagrahas). "
            "The cycle sequence is Sun (6 yrs), Moon (10 yrs), Mars (7 yrs), Rahu (18 yrs), Jupiter (16 yrs), "
            "Saturn (19 yrs), Mercury (17 yrs), Ketu (7 yrs), and Venus (20 yrs). "
            "The operating Mahadasha and Antardasha determine which life events and houses manifest. "
            "Ketu Mahadasha often brings spiritual introspection and sudden detachment, "
            "while Rahu Mahadasha triggers material ambition and unconventional pursuits. "
            "Planetary mantras and temple poojas align planetary vibrations during challenging periods."
        )
    },
    {
        "title": "Sade Sati and Saturn (Shani) Remedial Practices",
        "source": "https://www.astroved.com/articles/shani-sade-sati-remedies",
        "category": "saturn_shani",
        "tags": ["saturn", "shani", "sani", "sade sati", "karma", "remedies", "pooja", "hanuman"],
        "content": (
            "Sade Sati is the 7.5-year transit of Saturn (Lord Shani) traversing the 12th, 1st, and 2nd houses "
            "relative to one's natal Moon sign (Janma Rashi). "
            "Rather than punishment, Sade Sati is regarded in Vedic philosophy as profound karmic cleansing, discipline, and maturity. "
            "Effective traditional remedies include lighting sesame oil (til oil) lamps on Saturdays, "
            "reciting the Hanuman Chalisa or Dasaratha Shani Stotram, "
            "and offering compassionate service, such as feeding crows and supporting underprivileged elders."
        )
    },
    {
        "title": "Kundli Matching and Ashtakoota Milan (36 Gunas)",
        "source": "https://www.astroved.com/articles/kundli-matching-for-marriage",
        "category": "marriage_compatibility",
        "tags": ["marriage", "compatibility", "kundli", "ashtakoota", "gunas", "nadi dosha", "relationship"],
        "content": (
            "Vedic compatibility analysis evaluates 8 fundamental factors (Ashtakoota) totaling 36 points (Gunas): "
            "Varna (1 pt), Vashya (2 pts), Tara (3 pts), Yoni (4 pts), Graha Maitri (5 pts), "
            "Gana (6 pts), Bhakoot (7 pts), and Nadi (8 pts). "
            "A score of 18 or higher is traditionally required for marital harmony. "
            "Nadi Dosha is examined closely; however, specific exceptions such as identical Nakshatras with "
            "different Padas, or beneficial Jupiter aspects, provide classical Nadi Dosha cancellation."
        )
    },
    {
        "title": "Rahu and Ketu Lunar Nodes and Kaal Sarp Dosha",
        "source": "https://www.astroved.com/articles/rahu-ketu-kaal-sarp-remedies",
        "category": "lunar_nodes_dosha",
        "tags": ["rahu", "ketu", "kaal sarp", "serpent dosha", "remedies", "durga", "shiva"],
        "content": (
            "Rahu (North Node) and Ketu (South Node) represent shadowy karmic axes in Vedic Jyotish. "
            "Kaal Sarp Dosha occurs when all seven classical planets are hemmed between Rahu and Ketu in the birth chart. "
            "To alleviate nodal afflictions, classical scriptures prescribe worshipping Lord Shiva via Rudra Abhishekam, "
            "chanting the Maha Mrityunjaya Mantra, and offering prayers to Goddess Durga during Rahu Kaal."
        )
    },
    {
        "title": "Gemstone (Ratna) Science According to Lagna and Rasi",
        "source": "https://www.astroved.com/articles/gemstones-in-vedic-astrology",
        "category": "gemstones_ratna",
        "tags": ["gemstones", "ratna", "ruby", "yellow sapphire", "emerald", "blue sapphire", "remedies"],
        "content": (
            "Vedic Ratna Shastra recommends gemstones exclusively for functional benefic planets in the birth chart. "
            "Yellow Sapphire (Pukhraj) enhances Jupiter (wisdom and fortune). "
            "Ruby (Manikya) strengthens the Sun (leadership and vitality). "
            "Emerald (Panna) boosts Mercury (intellect and commerce). "
            "Blue Sapphire (Neelam) must only be worn after thorough astrological testing due to Saturn's swift potency. "
            "Gemstones should be consecrated (Prana Pratishtha) with specific planetary mantras before wearing."
        )
    }
]

def clean_and_normalize(text: str) -> str:
    """Cleans and normalizes raw text for knowledge chunking."""
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", text)
    cleaned = re.sub(r"\r\n|\r", "\n", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculates cosine similarity between two vector embeddings."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = 0.0
    norm1 = 0.0
    norm2 = 0.0
    for a, b in zip(v1, v2):
        dot += a * b
        norm1 += a * a
        norm2 += b * b
    if norm1 <= 0.0 or norm2 <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm1) * math.sqrt(norm2))

class KnowledgeService:
    """
    LangChain-based RAG Knowledge Service for AstroVed Chatbot.
    Implements:
    - Text chunking with source & category metadata using RecursiveCharacterTextSplitter
    - OpenAI 1536-dim embeddings generation (text-embedding-3-small)
    - Semantic vector search with cosine similarity & relevance score filtering
    - Grounded answer generation strictly from verified reference context
    - Honest no-match fallback when evidence is insufficient
    """

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=400,
            chunk_overlap=50,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    def _ensure_fixtures_seeded(self):
        """
        Helper for test suites and offline verification.
        Does not auto-seed on runtime startup.
        """
        if not getattr(settings, "RAG_ENABLED", False):
            return
        try:
            col = get_knowledge_collection()
            if col.count_documents({}) == 0:
                self.ingest_documents(APPROVED_KNOWLEDGE_FIXTURES)
                logger.info("Seeded %d approved AstroVed knowledge documents.", len(APPROVED_KNOWLEDGE_FIXTURES))
        except Exception as err:
            logger.warning("Knowledge fixtures check note: %s", err)

    def generate_embedding(self, text: str) -> List[float]:
        """Generates 1536-dimensional embedding using OpenAI text-embedding-3-small."""
        api_key = getattr(settings, "OPENAI_API_KEY", "").strip()
        if not api_key or not text:
            return []
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            cleaned = text.replace("\n", " ").strip()
            res = client.embeddings.create(
                input=cleaned,
                model=getattr(settings, "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            )
            return res.data[0].embedding
        except Exception as err:
            logger.warning("Error generating embedding: %s", err)
            return []

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates batch embeddings efficiently."""
        api_key = getattr(settings, "OPENAI_API_KEY", "").strip()
        if not api_key or not texts:
            return [[] for _ in texts]
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            cleaned = [t.replace("\n", " ").strip() for t in texts]
            res = client.embeddings.create(
                input=cleaned,
                model=getattr(settings, "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            )
            return [item.embedding for item in res.data]
        except Exception as err:
            logger.warning("Error generating batch embeddings: %s", err)
            return [[] for _ in texts]

    def ingest_documents(self, documents: List[Dict[str, Any]], clear_existing: bool = False) -> int:
        """
        Cleans, normalizes, chunks, embeds, and indexes approved documents into MongoDB.
        Stores source metadata and category metadata on every chunk.
        """
        col = get_knowledge_collection()
        if clear_existing:
            col.delete_many({"provenance": "approved_astroved_knowledge_base"})

        now = datetime.now(timezone.utc)
        chunk_records = []
        texts_to_embed = []

        for doc in documents:
            title = doc["title"]
            source = doc["source"]
            category = doc.get("category", "general_astrology")
            tags = doc.get("tags", [])
            raw_content = clean_and_normalize(doc["content"])

            chunks = self.splitter.split_text(raw_content)
            total_chunks = len(chunks)

            for i, chunk in enumerate(chunks):
                doc_id = f"doc_{uuid.uuid4().hex[:12]}"
                chunk_id = f"{doc_id}_c{i+1}"
                record = {
                    "document_id": doc_id,
                    "chunk_id": chunk_id,
                    "title": f"{title} (Part {i+1})" if total_chunks > 1 else title,
                    "document_title": title,
                    "source": source,
                    "category": category,
                    "tags": tags,
                    "content": chunk,
                    "chunk_index": i + 1,
                    "total_chunks": total_chunks,
                    "is_public": True,
                    "provenance": "approved_astroved_knowledge_base",
                    "created_at": now
                }
                chunk_records.append(record)
                texts_to_embed.append(f"{title}: {chunk}")

        # Batch compute embeddings if OpenAI API is configured
        embeddings = self.generate_embeddings_batch(texts_to_embed)
        for rec, emb in zip(chunk_records, embeddings):
            rec["embedding"] = emb

        if chunk_records:
            col.insert_many(chunk_records)
            logger.info("Ingested %d knowledge chunks into MongoDB.", len(chunk_records))

        return len(chunk_records)

    def semantic_search(
        self,
        query: str,
        top_k: int = 2,
        category: Optional[str] = None,
        min_similarity: float = 0.38
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic vector search with cosine similarity and relevance filtering.
        Returns empty list if evidence is insufficient (similarity < min_similarity).
        """
        if not getattr(settings, "RAG_ENABLED", False) or not query or not query.strip():
            return []

        query_emb = self.generate_embedding(query.strip())
        if not query_emb:
            return self._keyword_search(query, top_k=top_k, category=category)

        col = get_knowledge_collection()
        mongo_filter: Dict[str, Any] = {"is_public": True, "embedding": {"$exists": True, "$ne": []}}
        if category and category not in ("all", "general", "general_astrology"):
            mongo_filter["category"] = category

        cursor = list(col.find(mongo_filter, {"_id": 0}))
        if not cursor and category:
            cursor = list(col.find({"is_public": True, "embedding": {"$exists": True, "$ne": []}}, {"_id": 0}))

        scored = []
        for doc in cursor:
            doc_emb = doc.get("embedding", [])
            if not doc_emb:
                continue
            sim = cosine_similarity(query_emb, doc_emb)
            if sim >= min_similarity:
                doc_copy = dict(doc)
                doc_copy["similarity_score"] = round(sim, 4)
                scored.append((sim, doc_copy))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    def _keyword_search(
        self,
        query: str,
        top_k: int = 2,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Keyword/tag fallback for test suites or offline operation."""
        col = get_knowledge_collection()
        terms = [t.lower() for t in query.strip().split() if len(t) > 2]

        # 1. MongoDB full-text index
        try:
            text_query: Dict[str, Any] = {"$text": {"$search": query}, "is_public": True}
            if category and category not in ("all", "general", "general_astrology"):
                text_query["category"] = category
            cursor = col.find(
                text_query,
                {"score": {"$meta": "textScore"}, "_id": 0}
            ).sort([("score", {"$meta": "textScore"})]).limit(top_k)
            results = list(cursor)
            if results:
                return results
        except Exception:
            pass

        # 2. Term scoring
        mongo_filter: Dict[str, Any] = {"is_public": True}
        if category and category not in ("all", "general", "general_astrology"):
            mongo_filter["category"] = category
        all_docs = list(col.find(mongo_filter, {"_id": 0}))
        if not all_docs and category:
            all_docs = list(col.find({"is_public": True}, {"_id": 0}))

        scored = []
        for d in all_docs:
            score = 0
            title_lower = d.get("title", "").lower()
            content_lower = d.get("content", "").lower()
            tags = [t.lower() for t in d.get("tags", [])]

            for term in terms:
                if term in title_lower:
                    score += 5
                if any(term in t for t in tags):
                    score += 4
                if term in content_lower:
                    score += 2

            if score >= 4:
                scored.append((score, d))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    def retrieve(self, query: str, top_k: int = 2, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves relevant approved knowledge documents for a query when RAG is enabled.
        Applies semantic similarity search and relevance thresholding.
        Returns empty list when evidence is insufficient or RAG is disabled.
        """
        if not getattr(settings, "RAG_ENABLED", False):
            return []

        if not query or not query.strip():
            return []

        # Semantic vector search with relevance filtering (falls back to keyword only if offline/no embeddings)
        return self.semantic_search(query, top_k=top_k, category=category, min_similarity=0.38)

    async def generate_grounded_answer(
        self,
        query: str,
        retrieved_docs: List[Dict[str, Any]],
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ) -> Tuple[str, bool, List[Dict[str, Any]]]:
        """
        Generates a concise answer grounded ONLY in retrieved information.
        Returns an honest no-match response when evidence is insufficient.
        """
        sources = [
            {
                "title": doc.get("document_title") or doc.get("title"),
                "source": doc.get("source"),
                "document_id": doc.get("document_id")
            }
            for doc in retrieved_docs
        ]

        # 10. Honest no-match response when evidence is insufficient
        if not retrieved_docs:
            no_match_text = (
                "Namaste. I do not have verified AstroVed reference information regarding this query in our knowledge base. "
                "For personalized Vedic guidance and authentic planetary remedies, our live astrology advisors or customer "
                "support team at support@astroved.com would be glad to assist you."
            )
            return no_match_text, True, []

        key = (api_key or getattr(settings, "OPENAI_API_KEY", "")).strip()
        target_model = model or getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

        if not key:
            doc = retrieved_docs[0]
            source_links = "\n".join([f"- [{d['title']} | AstroVed.com]({d['source']})" for d in sources if d.get('source')])
            return f"{doc['content']}\n\nSource:\n{source_links}", True, sources

        try:
            import httpx
            context_blocks = []
            for i, d in enumerate(retrieved_docs, 1):
                context_blocks.append(
                    f"Document #{i}: {d.get('title')}\n"
                    f"Source: {d.get('source')}\n"
                    f"Content: {d.get('content')}"
                )
            context_str = "\n\n".join(context_blocks)

            system_prompt = (
                "You are AstroVed AI, a warm, reverent Vedic Astrology guide.\n"
                "Answer the seeker's query grounded ONLY in the verified AstroVed reference material provided below.\n"
                "Strict Rules:\n"
                "1. Answer concisely in 2–4 sentences using ONLY the verified facts from the reference text.\n"
                "2. NEVER invent details, benefits, planetary remedies, pooja procedures, prices, or policies not in the text.\n"
                "3. Distinguish traditional spiritual beliefs from empirical claims.\n"
                "4. Do NOT mention internal technical terms like 'knowledge base', 'context', 'chunk', or 'RAG'.\n"
                "5. At the end of your response, always cite the verified source(s) as:\n"
                "Source:\n"
                "- [Document Title](source_url)"
            )

            user_prompt = (
                f"Seeker's Question: \"{query}\"\n\n"
                f"=== VERIFIED REFERENCE MATERIAL ===\n"
                f"{context_str}\n"
                f"=== END VERIFIED REFERENCE MATERIAL ==="
            )

            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={
                        "model": target_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.2,
                        "max_tokens": 400
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    answer = data["choices"][0]["message"]["content"]
                    return answer, False, sources
                else:
                    return (
                        "Namaste. Our AI astrological guide is temporarily unavailable at the moment. "
                        "Please try again in a few moments, or connect with our support team or a live advisor for assistance.",
                        True,
                        sources
                    )
        except Exception as err:
            logger.warning("Error in RAG generation: %s", err)
            return (
                "Namaste. Our AI astrological guide is temporarily unavailable at the moment. "
                "Please try again in a few moments, or connect with our support team or a live advisor for assistance.",
                True,
                sources
            )

knowledge_service = KnowledgeService()
