import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.database import get_knowledge_collection, init_db_indexes
from app.core.config import settings

logger = logging.getLogger(__name__)

# Approved curated AstroVed Vedic Astrology Reference Knowledge Base
APPROVED_KNOWLEDGE_FIXTURES = [
    {
        "title": "Vedic Astrology Principles and the 12 Houses (Bhavas)",
        "source": "https://www.astroved.com/articles/12-houses-in-vedic-astrology",
        "tags": ["houses", "bhavas", "lagna", "career", "relationships", "dharma"],
        "content": (
            "In Vedic Astrology (Jyotish), the horoscope (Kundli) is divided into 12 Bhavas (Houses). "
            "1st House (Tanu Bhava/Lagna) represents personality, vitality, and health. "
            "2nd House (Dhana Bhava) governs accumulated wealth, speech, and family lineage. "
            "4th House (Sukha Bhava) governs mother, inner contentment, vehicles, and real estate. "
            "7th House (Kalatra Bhava) governs marriage, partnerships, and legal unions. "
            "9th House (Bhagya Bhava) represents fortune, dharma, guru, and father. "
            "10th House (Karma Bhava) rules professional career, reputation, and public accomplishments. "
            "11th House (Labha Bhava) determines gains, cash flow, and elder siblings."
        )
    },
    {
        "title": "Vimshottari Dasha Cycles and Planetary Periods",
        "source": "https://www.astroved.com/articles/vimshottari-dasha-system",
        "tags": ["dasha", "mahadasha", "antardasha", "timing", "ketu", "saturn", "jupiter"],
        "content": (
            "The Vimshottari Dasha cycle spans 120 years across all nine planetary rulers (Navagrahas). "
            "The cycle order is Sun (6 yrs), Moon (10 yrs), Mars (7 yrs), Rahu (18 yrs), Jupiter (16 yrs), "
            "Saturn (19 yrs), Mercury (17 yrs), Ketu (7 yrs), and Venus (20 yrs). "
            "The operating Mahadasha and Antardasha determine which life events manifest. "
            "Ketu Mahadasha often brings spiritual introspection and sudden detachment, "
            "while Rahu Mahadasha triggers material ambition and unconventional pursuits. "
            "Planetary mantras and temple poojas align planetary vibrations during challenging periods."
        )
    },
    {
        "title": "Sade Sati and Saturn (Shani) Remedial Practices",
        "source": "https://www.astroved.com/articles/shani-sade-sati-remedies",
        "tags": ["saturn", "sani", "sade sati", "karma", "remedies", "pooja"],
        "content": (
            "Sade Sati is the 7.5-year transit of Saturn (Lord Shani) traversing the 12th, 1st, and 2nd houses "
            "relative to one's natal Moon sign (Janma Rashi). "
            "Rather than punishment, Sade Sati is regarded as profound karmic cleansing, discipline, and maturity. "
            "Effective traditional remedies include lighting sesame oil (til oil) lamps on Saturdays, "
            "reciting the Hanuman Chalisa or Dasaratha Shani Stotram, "
            "and offering compassionate service, such as feeding crows and supporting underprivileged elders."
        )
    },
    {
        "title": "Kundli Matching and Ashtakoota Milan (36 Gunas)",
        "source": "https://www.astroved.com/articles/kundli-matching-for-marriage",
        "tags": ["marriage", "compatibility", "kundli", "ashtakoota", "gunas", "nadi dosha"],
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
        "tags": ["rahu", "ketu", "kaal sarp", "serpent dosha", "remedies", "durga"],
        "content": (
            "Rahu (North Node) and Ketu (South Node) represent shadowy karmic axes. "
            "Kaal Sarp Dosha occurs when all seven classical planets are hemmed between Rahu and Ketu in the chart. "
            "To alleviate nodal afflictions, classical scriptures prescribe worshipping Lord Shiva via Rudra Abhishekam, "
            "chanting the Maha Mrityunjaya Mantra, and offering prayers to Goddess Durga on Rahu Kaal."
        )
    },
    {
        "title": "Gemstone (Ratna) Science According to Lagna and Rasi",
        "source": "https://www.astroved.com/articles/gemstones-in-vedic-astrology",
        "tags": ["gemstones", "ratna", "ruby", "yellow sapphire", "emerald", "blue sapphire"],
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

class KnowledgeService:
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=400,
            chunk_overlap=50,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        self._ensure_fixtures_seeded()

    def _ensure_fixtures_seeded(self):
        """
        Seeds approved reference documents if collection is empty and RAG is enabled.
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

    def ingest_documents(self, documents: List[Dict[str, Any]]) -> int:
        """
        Chunks and stores approved documents in MongoDB knowledge_documents collection.
        """
        col = get_knowledge_collection()
        now = datetime.now(timezone.utc)
        count = 0

        for doc in documents:
            title = doc["title"]
            source = doc["source"]
            tags = doc.get("tags", [])
            raw_content = doc["content"]

            chunks = self.splitter.split_text(raw_content)
            for i, chunk in enumerate(chunks):
                doc_id = f"doc_{uuid.uuid4().hex[:12]}"
                record = {
                    "document_id": doc_id,
                    "title": f"{title} (Part {i+1})" if len(chunks) > 1 else title,
                    "source": source,
                    "tags": tags,
                    "content": chunk,
                    "is_public": True,
                    "provenance": "approved_astroved_knowledge_base",
                    "created_at": now
                }
                col.insert_one(record)
                count += 1
        return count

    def retrieve(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
        Retrieves relevant approved knowledge documents for a query when RAG is enabled.
        Uses MongoDB text search and tag/keyword matching.
        Returns empty list if RAG is disabled or if no approved documents match.
        """
        if not getattr(settings, "RAG_ENABLED", False):
            return []

        if not query or not query.strip():
            return []

        col = get_knowledge_collection()
        terms = [t.lower() for t in query.strip().split() if len(t) > 2]
        
        # 1. Try MongoDB text search first
        try:
            cursor = col.find(
                {"$text": {"$search": query}, "is_public": True},
                {"score": {"$meta": "textScore"}, "_id": 0}
            ).sort([("score", {"$meta": "textScore"})]).limit(top_k)

            results = list(cursor)
            if results:
                return results
        except Exception as err:
            logger.debug("MongoDB text search unavailable or query not indexed: %s", err)

        # 2. Keyword/tag relevance fallback
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

            if score >= 4:  # Meaningful match threshold
                scored.append((score, d))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored[:top_k]]

knowledge_service = KnowledgeService()
