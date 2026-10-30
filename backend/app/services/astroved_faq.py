"""
AstroVed Starter FAQ and Reference Knowledge Module (Test Fixture / Reference Only).
Retained for automated test suites and educational reference.
Decoupled from runtime RAG retrieval: not used as an active RAG knowledge source.
"""

import re
from typing import List, Dict, Any, Optional

# Curated starter reference entries based on AstroVed educational articles
STARTER_ASTROVED_FAQS: List[Dict[str, Any]] = [
    {
        "id": "faq_jyotish_intro",
        "title": "What is Vedic Astrology (Jyotish)?",
        "source": "https://www.astroved.com/articles/what-is-vedic-astrology",
        "tags": ["vedic astrology", "jyotish", "science of light", "vedas", "karma", "astrology definition", "sidereal"],
        "content": (
            "Vedic Astrology, traditionally named Jyotish ('the science of celestial light'), "
            "is an ancient spiritual discipline originating in India's sacred Vedic scriptures. "
            "It maps the precise positions of celestial bodies at the moment of an individual's birth "
            "to illuminate their karmic patterns, innate potential, life lessons, and spiritual growth. "
            "Unlike Western astrology which utilizes the tropical zodiac, Vedic astrology employs the "
            "sidereal (fixed-star) zodiac, aligning with visible astronomical constellations, and places "
            "primary emphasis on planetary cycles (Dashas) and lunar constellations (Nakshatras)."
        )
    },
    {
        "id": "faq_birth_chart",
        "title": "What is a Horoscope or Birth Chart (Kundli)?",
        "source": "https://www.astroved.com/articles/basic-components-of-vedic-astrology",
        "tags": ["horoscope", "birth chart", "kundli", "janam kundali", "natal chart", "kundali", "map of heavens"],
        "content": (
            "In Vedic tradition, a horoscope or birth chart (Janam Kundli) is a celestial diagram representing "
            "the cosmic arrangement across 12 signs and 12 houses at the exact minute and coordinates of birth. "
            "Serving as an individual's unique karmic blueprint, the chart reveals personality strengths, "
            "psychological tendencies, health inclinations, professional potential, and relationship dynamics. "
            "It operates as a diagnostic guide to help seekers harmonize with cosmic rhythms through conscious "
            "action and spiritual remedies."
        )
    },
    {
        "id": "faq_birth_details",
        "title": "What Birth Details Are Needed for a Chart?",
        "source": "https://www.astroved.com/articles/how-to-read-kundli",
        "tags": ["birth details", "date of birth", "time of birth", "place of birth", "coordinates", "chart details", "accurate time"],
        "content": (
            "Generating an accurate Vedic birth chart requires three essential details: "
            "(1) Exact Date of Birth (day, month, year); "
            "(2) Exact Time of Birth (ideally to the minute); and "
            "(3) Exact Place of Birth (city, state, country) to determine geographical latitude and longitude. "
            "Accurate time is especially vital because the rising sign (Lagna) shifts approximately every two hours, "
            "and an inaccuracy can alter the entire house layout and divisional chart calculations."
        )
    },
    {
        "id": "faq_nine_grahas",
        "title": "What Are the Nine Grahas (Navagrahas)?",
        "source": "https://www.astroved.com/articles/basic-components-of-vedic-astrology",
        "tags": ["nine grahas", "navagrahas", "planets", "surya", "chandra", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"],
        "content": (
            "Vedic astrology centers upon the nine planetary energies known as the Navagrahas: "
            "Surya (Sun - soul, life vitality, leadership), Chandra (Moon - mind, emotions, mother), "
            "Mangala (Mars - courage, physical energy, determination), Budha (Mercury - intellect, communication, trade), "
            "Guru/Brihaspati (Jupiter - wisdom, spirituality, dharma, benevolence), Shukra (Venus - love, beauty, creativity, luxury), "
            "Shani (Saturn - discipline, perseverance, karmic lessons), and the two lunar shadow nodes: "
            "Rahu (North Node - material drive, innovation, worldly ambition) and Ketu (South Node - spiritual liberation, intuition, detachment)."
        )
    },
    {
        "id": "faq_12_zodiac_signs",
        "title": "What Are the 12 Zodiac Signs (Rashis)?",
        "source": "https://www.astroved.com/articles/horoscope-zodiac-signs",
        "tags": ["12 zodiac signs", "rashis", "mesha", "vrishabha", "mithuna", "karka", "simha", "kanya", "tula", "vrishchika", "dhanu", "makara", "kumbha", "meena"],
        "content": (
            "The 360-degree celestial sphere is segmented into 12 equal 30-degree sections called Rashis (signs): "
            "Mesha (Aries - fire, initiative), Vrishabha (Taurus - earth, grounded stability), "
            "Mithuna (Gemini - air, communication and agility), Karka (Cancer - water, empathy and intuition), "
            "Simha (Leo - fire, sovereignty and self-expression), Kanya (Virgo - earth, analytical precision and service), "
            "Tula (Libra - air, balance and harmony), Vrishchika (Scorpio - water, transformation and depth), "
            "Dhanu (Sagittarius - fire, philosophy and optimism), Makara (Capricorn - earth, endurance and structure), "
            "Kumbha (Aquarius - air, innovation and collective welfare), and Meena (Pisces - water, devotion and transcendence)."
        )
    },
    {
        "id": "faq_12_houses",
        "title": "What Are the 12 Houses (Bhavas)?",
        "source": "https://www.astroved.com/articles/basic-components-of-vedic-astrology",
        "tags": ["12 houses", "bhavas", "lagna bhava", "dhana bhava", "sukha bhava", "kalatra bhava", "karma bhava", "labha bhava"],
        "content": (
            "A Vedic chart is divided into 12 houses (Bhavas), each governing specific areas of human experience: "
            "1st House (Tanu) - physical body, self, temperament, vitality; "
            "2nd House (Dhana) - accumulated wealth, family assets, speech, values; "
            "3rd House (Sahaja) - courage, siblings, short journeys, communication; "
            "4th House (Sukha) - home, mother, inner peace, vehicles, land; "
            "5th House (Putra) - intelligence, creativity, romance, children, poorva punya (past merit); "
            "6th House (Ari) - health challenges, debts, daily service, overcoming obstacles; "
            "7th House (Kalatra) - marriage, life partner, business partnerships; "
            "8th House (Ayur) - longevity, transformation, mysticism, sudden events; "
            "9th House (Bhagya) - higher wisdom, dharma, guru, father, fortune; "
            "10th House (Karma) - career, public standing, authority, leadership; "
            "11th House (Labha) - prosperity, ambitions, friends, financial gains; "
            "12th House (Vyaya) - spiritual liberation (Moksha), foreign residence, expenditures, solitude."
        )
    },
    {
        "id": "faq_lagna_ascendant",
        "title": "What is Lagna (Ascendant)?",
        "source": "https://www.astroved.com/articles/basic-components-of-vedic-astrology",
        "tags": ["lagna", "ascendant", "rising sign", "first house", "physical body", "lagna chart", "chart", "birth chart"],
        "content": (
            "Lagna, or the Ascendant, is the specific zodiac constellation rising on the eastern horizon "
            "at the exact moment and location of an individual's birth. "
            "It forms the 1st house of the birth chart and anchors the perspective from which the entire "
            "horoscope is evaluated. In Vedic astrology, Lagna signifies one's physical constitution, "
            "vitality, overall life orientation, and the lens through which one interacts with the world."
        )
    },
    {
        "id": "faq_moon_sign",
        "title": "What is a Moon Sign (Janma Rasi)?",
        "source": "https://www.astroved.com/articles/horoscope-zodiac-signs",
        "tags": ["moon sign", "rasi", "janma rasi", "chandra rasi", "mind", "emotions", "manas"],
        "content": (
            "Your Janma Rasi (Moon Sign) is the zodiac sign the Moon was transiting at your time of birth. "
            "In Vedic Jyotish, the Moon represents Manas (the mind, emotions, memory, and instinctual nature). "
            "Because our felt experience of life is filtered through our emotional mindset, the Moon sign is "
            "considered central in Indian astrology. It also forms the foundation for daily transits (Gochar), "
            "compatibility matching, and the Vimshottari Dasha planetary timeline."
        )
    },
    {
        "id": "faq_nakshatra",
        "title": "What is a Nakshatra (Birth Star)?",
        "source": "https://www.astroved.com/articles/basic-components-of-vedic-astrology",
        "tags": ["nakshatra", "birth star", "lunar mansions", "27 nakshatras", "janma nakshatra", "padas"],
        "content": (
            "The 360-degree zodiac is subdivided into 27 lunar mansions called Nakshatras, each measuring "
            "13 degrees and 20 minutes of celestial arc (further split into four 3-degree-20-minute Padas). "
            "The Nakshatra occupied by the Moon at birth is your Janma Nakshatra. Nakshatras offer profound "
            "insights into innate instincts, spiritual destiny, and behavioral tendencies, and they determine "
            "the starting point of an individual's operating Dasha cycle."
        )
    },
    {
        "id": "faq_dashas",
        "title": "What Are Planetary Dashas?",
        "source": "https://www.astroved.com/articles/basic-components-of-vedic-astrology",
        "tags": ["dashas", "planetary dashas", "vimshottari dasha", "mahadasha", "antardasha", "timing of events"],
        "content": (
            "Dashas are planetary time periods that govern the chronological unfolding of life events in Vedic astrology. "
            "The most revered system, Vimshottari Dasha, spans 120 years across all nine Grahas in fixed sequence "
            "(e.g., Ketu 7 yrs, Venus 20 yrs, Sun 6 yrs, Moon 10 yrs, Mars 7 yrs, Rahu 18 yrs, Jupiter 16 yrs, Saturn 19 yrs, Mercury 17 yrs). "
            "During a particular planet's major period (Mahadasha) and sub-period (Antardasha), the life areas and houses "
            "governed by that planet become intensely activated."
        )
    },
    {
        "id": "faq_kundli_dosha",
        "title": "What is a Kundli Dosha?",
        "source": "https://www.astroved.com/articles/what-is-kundli-dosha",
        "tags": ["kundli dosha", "dosha", "mangal dosha", "kaal sarp dosha", "pitru dosha", "affliction", "remedies"],
        "content": (
            "A Kundli Dosha refers to an astrological affliction or challenging planetary combination in a birth chart, "
            "arising from unresolved past karmic influences. Common examples include Mangal Dosha (Mars affecting partnership harmony), "
            "Kaal Sarp Dosha (planets hemmed between Rahu and Ketu), and Pitru Dosha. "
            "In Vedic philosophy, a dosha is not a fixed curse, but an invitation for spiritual awareness and remedy. "
            "Traditional Vedic remedial practices—such as specific pujas, homas, mantra chanting, charity, and ethical living—"
            "are prescribed to soften harsh planetary vibrations."
        )
    },
    {
        "id": "faq_astrology_vs_horoscope",
        "title": "What is the Difference Between Astrology and a Horoscope?",
        "source": "https://www.astroved.com/articles/what-is-vedic-astrology",
        "tags": ["difference between astrology and horoscope", "astrology vs horoscope", "horoscope definition", "astrology definition"],
        "content": (
            "Astrology (Jyotish) is the comprehensive discipline, philosophical system, and mathematical calculation "
            "of planetary motions and their correlation with human consciousness and earthly events. "
            "A horoscope (Kundli), on the other hand, is a specific astronomical chart or visual diagram cast for a single "
            "moment and location in time—such as an individual's birth. "
            "In short, astrology is the body of science and wisdom, while a horoscope is the personalized snapshot produced using that science."
        )
    },
    {
        "id": "faq_traditional_use",
        "title": "How Are Astrology Interpretations Traditionally Used for Career, Relationships, and Personal Reflection?",
        "source": "https://www.astroved.com/articles/how-to-read-kundli",
        "tags": ["career guidance", "relationship compatibility", "personal reflection", "traditional use", "10th house career", "7th house marriage", "self awareness"],
        "content": (
            "Vedic astrology is traditionally approached not as rigid determinism, but as a navigational compass for conscious living: "
            "(1) Career: The 10th house (Karma Bhava), Sun, Saturn, Mercury, and current Dasha indicate vocational talents, leadership timing, and suitable industries; "
            "(2) Relationships: The 7th house (Kalatra Bhava), Venus, Jupiter, and Ashtakoota compatibility analysis evaluate emotional harmony and marital endurance; "
            "(3) Personal Reflection: By unveiling sub-conscious traits, innate blind spots, and karmic strengths, the chart fosters self-acceptance and empowers "
            "responsible action (Purushartha) supported by timely spiritual remedies."
        )
    }
]

# Stopwords to filter out when tokenizing queries for reference matching
QUERY_STOPWORDS = {
    "what", "is", "the", "a", "an", "of", "and", "in", "for", "to", "how", "are",
    "does", "do", "can", "tell", "me", "about", "with", "my", "your", "by", "on",
    "or", "from", "at", "as", "explain", "please", "meaning", "define", "know"
}

class AstroVedFAQService:
    """
    Dedicated service for AstroVed starter FAQs and reference materials.
    Provides keyword- and tag-based matching to extract verified background context
    for the conversational LLM while remaining modular for future RAG integrations.
    """

    def __init__(self, faqs: Optional[List[Dict[str, Any]]] = None):
        self._faqs = faqs or STARTER_ASTROVED_FAQS

    def get_all_faqs(self) -> List[Dict[str, Any]]:
        """Returns all curated starter FAQs."""
        return self._faqs

    def get_faq_by_id(self, faq_id: str) -> Optional[Dict[str, Any]]:
        """Finds a specific FAQ entry by unique identifier."""
        for faq in self._faqs:
            if faq["id"] == faq_id:
                return faq
        return None

    def find_matching_references(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
        Finds matching starter reference entries for a customer astrology query.
        Returns entries ordered by relevance score, or [] if no strong match exists.
        """
        if not query or not query.strip():
            return []

        cleaned_query = query.lower()
        # Extract meaningful alphanumeric tokens
        raw_tokens = re.findall(r"\b[a-z0-9]{2,}\b", cleaned_query)
        tokens = [t for t in raw_tokens if t not in QUERY_STOPWORDS]

        if not tokens:
            return []

        scored_results = []

        for faq in self._faqs:
            score = 0
            title_lower = faq["title"].lower()
            content_lower = faq["content"].lower()
            tags = [t.lower() for t in faq.get("tags", [])]

            # 1. Exact phrase matches in title or tags
            clean_phrase = " ".join(tokens)
            if clean_phrase in title_lower:
                score += 25
            for tag in tags:
                if clean_phrase == tag:
                    score += 20
                elif clean_phrase in tag:
                    score += 10

            # 2. Token-level matches
            matched_tokens = 0
            for token in tokens:
                token_matched = False
                if token in title_lower.split() or f"({token})" in title_lower or f" {token} " in f" {title_lower} ":
                    score += 14
                    token_matched = True
                elif token in title_lower:
                    score += 8
                    token_matched = True

                if any(token == tag or token in tag.split() for tag in tags):
                    score += 10
                    token_matched = True
                elif any(token in tag for tag in tags):
                    score += 4
                    token_matched = True

                if token in content_lower:
                    score += 1
                    token_matched = True

                if token_matched:
                    matched_tokens += 1

            # Multi-token synergy bonus
            if matched_tokens > 1:
                score += matched_tokens * 4

            # Relevance threshold: only return entries with meaningful relevance
            if score >= 8:
                scored_results.append((score, faq))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [faq for score, faq in scored_results[:top_k]]

# Singleton instance
astroved_faq_service = AstroVedFAQService()
