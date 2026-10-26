import httpx
from typing import List, Dict
from app.core.config import settings

ASTROVED_SYSTEM_PROMPT = """You are AstroVed AI, a warm, compassionate, and knowledgeable Vedic Astrology assistant representing AstroVed.
Your goal is to guide seekers regarding Vedic Astrology principles, planetary transits (Gochar), Nakshatras, Dasha cycles, Pooja remedies, Homa, and spiritual gemstone suggestions.
Always speak with reverence and positivity. Encourage spiritual remedies, mantras, and personalized birth chart consultations where appropriate.
Keep answers concise, insightful, and well-structured with clear bullet points when appropriate."""

MOCK_RESPONSES = [
    {
        "keywords": ["career", "job", "profession", "business"],
        "reply": "In Vedic Astrology, the 10th House (Karma Bhava) and its planetary ruler, along with Saturn (the Karaka of career) and the current Mahadasha, determine your professional trajectory. To bring clarity and overcome workplace hurdles, chanting the **Hanuman Chalisa** on Tuesdays or performing a **Ganesha Pooja** helps clear obstacles."
    },
    {
        "keywords": ["marriage", "relationship", "love", "spouse", "partner"],
        "reply": "Matters of relationships and marital harmony are illuminated by the 7th House, Venus (Shukra), and Jupiter (Guru). If you are experiencing delays or misunderstandings, strengthening Venus with Friday Lakshmi prayers and wearing clean, pastel shades fosters peace and mutual understanding."
    },
    {
        "keywords": ["health", "stress", "peace", "healing"],
        "reply": "Physical and mental well-being are governed by the 1st House (Lagna), Sun (Vitality), and Moon (Mind/Manas). Chanting the **Maha Mrityunjaya Mantra** 108 times and offering Arghya (water) to Surya Deva at sunrise instills prana and serenity."
    },
    {
        "keywords": ["wealth", "finance", "money", "debt"],
        "reply": "Wealth prosperity reflects the 2nd House (Dhana Bhava) and 11th House (Labha Bhava), energized by Lord Kubera and Goddess Mahalakshmi. Maintaining gratitude, lighting a ghee lamp in the North-East corner at twilight, and reciting **Sri Suktam** invites abundance."
    },
    {
        "keywords": ["sani", "saturn", "sade sati", "rahu", "ketu"],
        "reply": "Navagraha transits, particularly Sade Sati or Rahu-Ketu nodal shifts, are karmic cleansing periods designed for profound spiritual growth. Lighting sesame oil lamps on Saturdays for Lord Shani and feeding crows or the needy transforms karmic friction into spiritual resilience."
    }
]

DEFAULT_MOCK_REPLY = (
    "Namaste. According to Vedic principles, every cosmic movement in the celestial sphere corresponds with your inner consciousness. "
    "To look deeply into your planetary placements, Lagna, and current Vimshottari Dasha, our AstroVed Vedic Astrologers can evaluate your exact date, time, and birthplace. "
    "What specific area of life—Career, Relationship, Wealth, or Spiritual Growth—would you like to explore right now?"
)

class LLMService:
    @staticmethod
    async def get_response(user_message: str, history: List[Dict[str, str]] = None) -> tuple[str, bool]:
        """
        Returns (response_text, is_mock).
        Uses OpenAI if OPENAI_API_KEY is configured, else provides domain-rich Vedic mock responses.
        """
        api_key = settings.OPENAI_API_KEY.strip()
        
        if not api_key:
            # Deterministic domain mock response
            msg_lower = user_message.lower()
            for item in MOCK_RESPONSES:
                if any(kw in msg_lower for kw in item["keywords"]):
                    return item["reply"], True
            return DEFAULT_MOCK_REPLY, True

        try:
            messages = [{"role": "system", "content": ASTROVED_SYSTEM_PROMPT}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": user_message})

            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": settings.OPENAI_MODEL,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 500
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    answer = data["choices"][0]["message"]["content"]
                    return answer, False
                else:
                    return f"[AI Provider Notice: Status {res.status_code}]. " + DEFAULT_MOCK_REPLY, True
        except Exception:
            return DEFAULT_MOCK_REPLY, True

llm_service = LLMService()
