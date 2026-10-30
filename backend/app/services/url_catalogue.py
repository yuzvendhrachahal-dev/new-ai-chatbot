"""
AstroVed Intelligent URL Routing Service.
Authoritative, scalable intent-to-URL mapping system covering ALL AstroVed pages
listed in data/all_urls.txt (651 verified URLs).

Key Guarantees:
1. Indexes and extracts every available URL from data/all_urls.txt.
2. Identifies page title, category, 2-line description, and clear action button.
3. Uses semantic token matching, synonym expansion, and confidence scoring.
4. Always selects exact page-level matches whenever possible.
5. Never returns the domain homepage or Astropedia base URL (/astropedia/en/home) when specific matches exist.
6. Never returns the first URL as a fallback.
7. Never invents URLs.
8. If multiple pages are similarly relevant, offers clarification.
9. If no relevant page exists in all_urls.txt (e.g. Birth Chart, Panchang, Muhurta), provides a helpful
   response with human support / live advisor option without redirecting to an unrelated page.
10. Keeps product purchase queries separate (routed to Excel product catalog).
"""

import os
import re
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
ALL_URLS_PATH = DATA_DIR / "all_urls.txt"

# Canonical synonym dictionary for Vedic astrology concepts
ASTRO_SYNONYMS: Dict[str, List[str]] = {
    "kundli": ["horoscope", "kundali", "janam", "patri", "birth", "chart", "matching", "milan"],
    "kundali": ["kundli", "horoscope", "matching", "milan"],
    "horoscope": ["kundli", "rashi", "rasi", "forecast", "predictions", "daily"],
    "matching": ["milan", "gun", "compatibility", "marriage", "partner", "synastry"],
    "milan": ["matching", "compatibility", "marriage", "kundli"],
    "marriage": ["wedding", "marital", "matrimonial", "kalathra", "spouse", "partner", "matching"],
    "wedding": ["marriage", "marital", "matching"],
    "love": ["romance", "relationship", "partner", "compatibility", "affair"],
    "compatibility": ["matching", "affinity", "relationship", "signs", "pair"],
    "saturn": ["shani", "sani", "sade", "sati", "transit", "shaniware"],
    "shani": ["saturn", "sani", "sade", "sati"],
    "sani": ["saturn", "shani", "sade", "sati"],
    "sade": ["sati", "saturn", "shani"],
    "sati": ["sade", "saturn", "shani"],
    "jupiter": ["guru", "brihaspati", "chandal"],
    "guru": ["jupiter", "brihaspati", "chandal"],
    "mars": ["mangal", "chevvaai", "kuja", "angarak"],
    "mangal": ["mars", "kuja", "chevvaai"],
    "mercury": ["budha", "budh"],
    "budha": ["mercury"],
    "venus": ["sukra", "shukra"],
    "sukra": ["venus", "shukra"],
    "shukra": ["venus", "sukra"],
    "sun": ["surya", "ravi"],
    "surya": ["sun"],
    "moon": ["chandra", "soma"],
    "chandra": ["moon"],
    "rahu": ["north", "node", "dragon"],
    "ketu": ["south", "node", "dragon"],
    "kethu": ["ketu", "south", "node"],
    "dosha": ["dosh", "affliction", "pariharam", "remedy", "remedies", "curse"],
    "dosh": ["dosha", "pariharam", "remedy", "remedies"],
    "remedy": ["remedies", "pariharam"],
    "remedies": ["remedy", "pariharam"],
    "pariharam": ["remedies", "remedy", "dosha", "dosh"],
    "nadi": ["agastya", "destiny", "thumb"],
    "career": ["job", "profession", "business", "work", "employment", "promotion"],
    "job": ["career", "profession", "business"],
    "finance": ["wealth", "money", "prosperity", "financial", "income", "lakshmi"],
    "wealth": ["finance", "money", "prosperity", "lakshmi"],
    "money": ["wealth", "finance"],
    "numerology": ["number", "numbers", "name", "destiny"],
    "tarot": ["card", "cards", "reading", "reader"],
    "vastu": ["home", "house", "direction", "energy", "vaastu"],
    "baby": ["babynames", "names", "child", "naming"],
    "names": ["baby", "babynames", "name"],
    "pooja": ["puja", "worship", "archana"],
    "puja": ["pooja", "worship", "archana"],
    "homa": ["fire", "lab", "homam", "havan", "yajna"],
    "homam": ["homa", "fire", "lab", "havan"],
    "fire": ["lab", "homa", "homam"],
    "ancestor": ["ancestors", "pitru", "tarpanam", "amavasya"],
    "ancestors": ["ancestor", "pitru", "tarpanam", "amavasya"],
    "tarpanam": ["ancestors", "pitru", "amavasya"],
    "pradosham": ["fasting", "vrata", "shiva"],
}

DISTINCT_ENTITIES: Set[str] = {
    # Nakshatras
    "ashwini", "bharani", "krittika", "rohini", "mrigashirsha", "ardra", "punarvasu", "pushya", "ashlesha",
    "magha", "purvaphalguni", "uttaraphalguni", "hasta", "chitra", "swati", "vishakha", "anuradha",
    "jyeshtha", "moola", "purvashada", "uttarashada", "shravana", "dhanishta", "shatabhisha",
    "purvabhadrapada", "uttarabhadrapada", "revati",
    # Specific Doshas
    "chandal", "grahan", "kalathra", "shrapit", "gandmool", "kemadruma", "eka", "ghat",
    # Deities
    "ganesha", "ganesh", "ganapathi", "lakshmi", "kala", "bhairava", "hanuman", "durga", "muruga", "rudra", "saraswathi",
    # Planets
    "saturn", "shani", "sani", "jupiter", "guru", "mars", "mangal", "venus", "sukra", "shukra",
    "mercury", "budha", "sun", "surya", "moon", "chandra", "rahu", "ketu",
    # Astrologer Cities
    "delhi", "mumbai", "bangalore", "chennai", "kolkata", "hyderabad", "pune", "gurgaon", "noida", "lucknow", "chandigarh",
    # Signs
    "aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
    # Festivals & Rituals
    "pradosham", "diwali", "shivaratri", "navratri", "tarpanam"
}

ENTITY_CANONICAL_MAP: Dict[str, str] = {
    "sani": "saturn",
    "shani": "saturn",
    "saturn": "saturn",
    "guru": "jupiter",
    "brihaspati": "jupiter",
    "jupiter": "jupiter",
    "mangal": "mars",
    "kuja": "mars",
    "chevvaai": "mars",
    "mars": "mars",
    "sukra": "venus",
    "shukra": "venus",
    "venus": "venus",
    "budha": "mercury",
    "budh": "mercury",
    "mercury": "mercury",
    "surya": "sun",
    "ravi": "sun",
    "sun": "sun",
    "chandra": "moon",
    "soma": "moon",
    "moon": "moon",
    "ganesh": "ganesha",
    "ganapathi": "ganesha",
    "ganapati": "ganesha",
    "ganesha": "ganesha",
}

# Common transliterations & typos mapped to canonical terms
TYPO_CORRECTIONS: Dict[str, str] = {
    "horoscpe": "horoscope",
    "horoscop": "horoscope",
    "horoscope": "horoscope",
    "numrology": "numerology",
    "numerolgy": "numerology",
    "compatability": "compatibility",
    "compatibilty": "compatibility",
    "remdies": "remedies",
    "remidies": "remedies",
    "pariharam": "pariharam",
    "kundali": "kundli",
    "kundli": "kundli",
    "astrologr": "astrologer",
    "astrology": "astrology",
    "nakshatram": "nakshatra",
    "nakshathra": "nakshatra",
    "muhurat": "muhurta",
    "muhurtham": "muhurta",
    "panchanga": "panchang",
    "panchangam": "panchang",
}

ZODIAC_SIGNS = [
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"
]

# Explicit non-astrological keywords that indicate unrelated queries
OFF_TOPIC_TERMS = {
    # Tech / Devices / Audio / Hardware
    "bluetooth", "device", "pairing", "software", "hardware", "headset", "laptop", "code", "python",
    "programming", "script", "app", "router", "wifi", "gaming", "vr", "console", "server", "domain",
    # Automotive / Mechanical / Household
    "car", "mechanic", "tire", "engine", "brake", "oil", "bicycle", "extinguisher", "coat", "commute",
    "route", "stick", "box", "size",
    # Food / Recipes
    "recipe", "cake", "cook", "cooking", "bake", "pizza", "nutrition", "dish", "ingredient", "ingredients", "facts",
    # Weather / Meteorological
    "weather", "rain", "storm", "celsius", "fahrenheit", "monsoon",
    # Medical / Pharmaceuticals
    "paracetamol", "medication", "medicine", "pill", "headache", "fever", "pharmacy", "prescription",
    # Legal / Real Estate / Non-astrology consultations
    "legal", "lawyer", "attorney", "contract", "dispute", "litigation", "court", "tenancy", "lease",
    # Sports / Entertainment / Movies
    "football", "soccer", "cricket", "basketball", "nba", "fifa", "olympics", "movie", "movies",
    "cinema", "theater", "actor", "actress", "cast", "wars", "trailer",
    # Banking / Finance (Non-spiritual)
    "emi", "loan", "mortgage", "credit", "debit", "banking", "startup", "equity", "crypto", "bitcoin",
    "generator", "excel",
    # Travel / Non-Vedic Religion
    "flight", "hotel", "resort", "airline", "airport", "church", "catholic", "pastor", "mosque", "mass",
    "gardening", "gardener", "tree", "plant", "fertilizer", "film", "tickets", "glasses", "discount"
}

# Domain anchors required to confirm astrological / AstroVed relevance
ASTRO_ANCHORS = {
    "horoscope", "rashi", "rasi", "zodiac", "astrology", "kundli", "kundali", "astrologer",
    "astrologers", "prediction", "predictions", "forecast", "transits", "transit", "dasha", "bhukti",
    "lagna", "ascendant", "compatibility", "matching", "milan", "marriage", "wedding", "numerology",
    "sade", "sati", "nadi", "nakshatra", "nakshatras", "birthstar", "babynames", "tarpanam",
    "pitru", "amavasya", "pournami", "pariharam", "dosha", "dosh", "homa", "homam", "firelab",
    "fire", "lab", "pooja", "puja", "fasting", "vrata", "temple", "temples", "vortex",
    "archana", "havan", "yajna", "mantra", "remedy", "remedies", "consultation", "speaks",
    "aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra", "scorpio", "sagittarius",
    "capricorn", "aquarius", "pisces",
    "sun", "surya", "moon", "chandra", "mars", "mangal", "mercury", "budha", "jupiter", "guru",
    "venus", "sukra", "shukra", "saturn", "shani", "sani", "rahu", "ketu", "graha", "grahas", "navagraha",
    "ganesha", "ganesh", "ganapati", "lakshmi", "durga", "chandi", "muruga", "subrahmanya",
    "shiva", "rudra", "vishnu", "krishna", "rama", "hanuman", "bhairava", "kala", "saraswathi",
    "saraswati", "gayatri", "dhanvantari", "ayyappa", "pratyangira", "sudarsana", "sudarshana",
    "varahi", "kubera", "kuber", "shreem", "brzee",
    "chandal", "grahan", "kalathra", "shrapit", "gandmool", "kemadruma", "eka", "ghat",
    "pradosham", "diwali", "deepavali", "shivaratri", "navratri", "ekadasi", "sankranti",
    "astroved", "astrovedspeaks", "astropedia"
}


@dataclass
class URLCatalogEntry:
    url: str
    title: str
    category: str
    description: str
    button_text: str
    is_generic: bool
    keywords: List[str]


@dataclass
class URLMatchResult:
    entry: Optional[URLCatalogEntry]
    confidence: float
    is_ambiguous: bool
    candidate_options: List[URLCatalogEntry]
    clarification_prompt: Optional[str]
    missing_service_msg: Optional[str] = None


class URLCatalogueService:
    def __init__(self, urls_path: Optional[Path] = None):
        self.urls_path = urls_path or ALL_URLS_PATH
        self.entries: List[URLCatalogEntry] = []
        self._url_set: Set[str] = set()
        self._build_catalogue()

    def _load_raw_urls(self) -> List[str]:
        candidate_paths = [
            self.urls_path,
            Path("/opt/ai-chatbot/data/all_urls.txt"),
            Path("/opt/AI_Chat_Bot/all_urls.txt")
        ]
        chosen = next((p for p in candidate_paths if p.exists()), None)
        if not chosen:
            logger.warning("all_urls.txt not found in candidate paths.")
            return []

        urls = []
        try:
            with open(chosen, "r", encoding="utf-8") as f:
                for line in f:
                    u = line.strip()
                    if u and u.startswith("http"):
                        urls.append(u)
            logger.info("Loaded %d URLs from %s", len(urls), chosen)
        except Exception as err:
            logger.error("Error reading all_urls.txt: %s", err)
        return urls

    def _extract_metadata(self, url: str) -> URLCatalogEntry:
        p = urlparse(url).path
        parts = [x for x in p.split("/") if x]

        # 0. Root domain homepage
        if not parts:
            return URLCatalogEntry(
                url=url,
                title="AstroVed Official Portal",
                category="portal_home",
                description="Explore Vedic astrology services, remedies, and spiritual guidance on AstroVed.",
                button_text="Visit AstroVed",
                is_generic=True,
                keywords=["astroved", "portal", "homepage", "main"]
            )

        # 1. Free Tools & Calculators
        if "astropedia/en/freetools" in url:
            slug = parts[-1].lower()
            if "horoscope-matching" in slug:
                return URLCatalogEntry(
                    url=url,
                    title="Compatibility Match",
                    category="free_tool",
                    description="Assess marital compatibility, mental affinity, and planetary alignment between partners using Vedic Kundli matching.",
                    button_text="Check Compatibility",
                    is_generic=False,
                    keywords=["horoscope", "kundli", "matching", "marriage", "milan", "gun", "compatibility", "partner", "wedding", "matrimony"]
                )
            elif "sade-sati" in slug:
                return URLCatalogEntry(
                    url=url,
                    title="Sade Sati Calculator & Analysis",
                    category="free_tool",
                    description="Calculate your Saturn 7.5-year Sade Sati transit phase and discover tailored Vedic remedies to navigate its karmic effects.",
                    button_text="Calculate Sade Sati",
                    is_generic=False,
                    keywords=["sade", "sati", "saturn", "shani", "calculator", "transit", "analysis", "remedies", "7.5", "shaniware"]
                )
            elif "numerology" in slug:
                return URLCatalogEntry(
                    url=url,
                    title="Vedic Numerology Calculator & Report",
                    category="free_tool",
                    description="Uncover the vibrational power of your birth date and name numbers with precise Vedic numerology insights.",
                    button_text="Explore Numerology",
                    is_generic=False,
                    keywords=["numerology", "report", "calculator", "name", "birth", "number", "destiny", "life", "path", "numbers"]
                )

        # 2. Horoscope & Daily Predictions
        if url.startswith("https://www.astroved.com/horoscope"):
            if len(parts) == 1:
                return URLCatalogEntry(
                    url=url,
                    title="Today's Horoscope",
                    category="horoscope",
                    description="Explore your daily horoscope, planetary influences, and guidance for your zodiac or Moon sign (Rashi).",
                    button_text="View Today's Horoscope",
                    is_generic=False,
                    keywords=["today", "daily", "horoscope", "rashi", "rasi", "predictions", "forecast", "planetary"]
                )
            elif "daily-love-horoscope" in url:
                if len(parts) == 2:
                    return URLCatalogEntry(
                        url=url,
                        title="Daily Love Horoscope",
                        category="horoscope",
                        description="Check your daily romantic forecast, emotional harmony, and planetary energies influencing love and relationships.",
                        button_text="View Love Horoscope",
                        is_generic=False,
                        keywords=["love", "romance", "relationship", "daily", "horoscope", "partner", "couple"]
                    )
                sign = parts[-1].replace("-love-horoscope-today", "").replace("-love-horoscope-tomorrow", "").replace("-love-horoscope-yesterday", "").replace("-love-horoscope", "").title()
                timing = "Today" if "today" in parts[-1] else ("Tomorrow" if "tomorrow" in parts[-1] else "Yesterday")
                return URLCatalogEntry(
                    url=url,
                    title=f"{sign} Love Horoscope ({timing})",
                    category="horoscope",
                    description=f"Daily romantic transit predictions and planetary guidance for {sign} sun and moon signs.",
                    button_text=f"View {sign} Love Horoscope",
                    is_generic=False,
                    keywords=[sign.lower(), "love", "horoscope", timing.lower(), "romance", "relationship", "sign"]
                )
            elif "monthly" in url:
                return URLCatalogEntry(
                    url=url,
                    title="Monthly Horoscope Predictions",
                    category="horoscope",
                    description="Comprehensive monthly astrological forecasts covering career, finances, relationships, and health.",
                    button_text="View Monthly Horoscope",
                    is_generic=False,
                    keywords=["monthly", "horoscope", "month", "predictions", "forecast", "transits"]
                )

        # 3. Zodiac Compatibility
        if "zodiac-signs/compatibility" in url:
            if len(parts) == 2:
                return URLCatalogEntry(
                    url=url,
                    title="Zodiac Signs Love Compatibility",
                    category="compatibility",
                    description="Discover emotional, intellectual, and romantic compatibility between any two zodiac star signs.",
                    button_text="Check Compatibility",
                    is_generic=False,
                    keywords=["zodiac", "signs", "love", "compatibility", "relationship", "partner", "star", "match"]
                )
            pair = parts[-1].replace("-", " & ").title()
            sign_tokens = [x.lower() for x in parts[-1].split("-") if x.lower() in ZODIAC_SIGNS]
            return URLCatalogEntry(
                url=url,
                title=f"{pair} Compatibility Analysis",
                category="compatibility",
                description=f"In-depth astrological compatibility reading between {pair} covering emotional bond and relationship harmony.",
                button_text=f"Explore {pair}",
                is_generic=False,
                keywords=sign_tokens + ["compatibility", "love", "match", "relationship", "harmony", "zodiac"]
            )

        # 4. Zodiac Signs Overview
        if url == "https://www.astroved.com/zodiac-signs":
            return URLCatalogEntry(
                url=url,
                title="12 Zodiac Signs & Astrological Traits",
                category="zodiac",
                description="Explore personality traits, ruling planets, lucky elements, and cosmic characteristics for all 12 zodiac signs.",
                button_text="Explore Zodiac Signs",
                is_generic=True,
                keywords=["zodiac", "signs", "astrology", "traits", "personality", "rashi"]
            )

        # 5. Dosha Pariharam
        if "dosha-pariharam" in url:
            d_name = parts[-1].replace("-remedies", "").replace("-", " ").title()
            d_slug = parts[-1].replace("-remedies", "").replace("-", " ").lower()
            return URLCatalogEntry(
                url=url,
                title=f"{d_name} Remedies & Pariharam",
                category="dosha_remedy",
                description=f"Discover authentic Vedic rituals, poojas, and homams to alleviate the karmic effects of {d_name}.",
                button_text=f"View {d_name} Remedies",
                is_generic=False,
                keywords=d_slug.split() + ["dosha", "dosh", "remedies", "remedy", "pariharam", "affliction"]
            )

        # 6. Nadi Astrology
        if "/nadi/" in url:
            sub = parts[-1].replace("-", " ").title()
            sub_slug = parts[-1].replace("-", " ").lower().split()
            nadi_kw = list(sub_slug) + ["nadi"]
            if "leaf" in parts[-1]:
                nadi_kw += ["leaf", "reading", "palm", "leaf-reading"]
            elif parts[-1] == "nadi-astrology":
                nadi_kw += ["astrology", "overview", "consultation"]
            elif parts[-1] == "nadi-reading":
                nadi_kw += ["reading", "prediction"]
            elif "remedies" in parts[-1]:
                nadi_kw += ["remedies", "pariharam"]
            return URLCatalogEntry(
                url=url,
                title=f"{sub} - Nadi Astrology",
                category="nadi_astrology",
                description=f"Explore ancient Agastya palm leaf readings and authentic destiny insights through {sub}.",
                button_text=f"Explore {sub}",
                is_generic=False,
                keywords=nadi_kw
            )

        # 7. AstroVed Speaks Consultations
        if "/astrovedspeaks" in url:
            if len(parts) == 1 or url.endswith("/astrovedspeaks/"):
                return URLCatalogEntry(
                    url=url,
                    title="AstroVed Speaks - Live Astrologer Consultation",
                    category="consultation",
                    description="Connect directly with verified Vedic astrologers for personal horoscope consultations and remedies.",
                    button_text="Consult Astrologers",
                    is_generic=False,
                    keywords=["astrovedspeaks", "astrologer", "consultation", "talk", "chat", "live", "expert"]
                )
            if "astrologer/" in url:
                spec = parts[-1].replace("-", " ").title()
                spec_k = parts[-1].replace("-", " ").lower().split()
                return URLCatalogEntry(
                    url=url,
                    title=f"{spec} Astrology Consultation",
                    category="consultation",
                    description=f"Speak with expert Vedic {spec} specialists for personalized clarity, timing, and effective remedies.",
                    button_text=f"Consult {spec} Astrologer",
                    is_generic=False,
                    keywords=spec_k + ["astrologer", "astrology", "consultation", "expert", "specialist", "guidance"]
                )
            if "chat-with-astrologer" in url:
                return URLCatalogEntry(
                    url=url,
                    title="Live Chat with Astrologer Online",
                    category="consultation",
                    description="Instant private text chat with certified Vedic astrologers to answer your life questions.",
                    button_text="Start Live Chat",
                    is_generic=False,
                    keywords=["chat", "astrologer", "online", "live", "instant", "text", "consultation"]
                )
            if "talk-to-astrologer" in url:
                return URLCatalogEntry(
                    url=url,
                    title="Talk to Astrologer on Call",
                    category="consultation",
                    description="Direct one-on-one telephonic consultation with senior Vedic astrologers for in-depth guidance.",
                    button_text="Call Astrologer",
                    is_generic=False,
                    keywords=["talk", "astrologer", "call", "phone", "telephonic", "consultation", "speak"]
                )
            if "best-astrologers-in" in url:
                loc = parts[-1].replace("best-astrologers-in-", "").title()
                return URLCatalogEntry(
                    url=url,
                    title=f"Best Vedic Astrologers in {loc}",
                    category="consultation",
                    description=f"Consult top-rated, authentic Vedic astrology experts serving clients in {loc}.",
                    button_text=f"Find Astrologers in {loc}",
                    is_generic=False,
                    keywords=[loc.lower(), "astrologers", "astrologer", "best", "city", "consultation", "top"]
                )
            sub = parts[-1].replace("-", " ").title()
            return URLCatalogEntry(
                url=url,
                title=f"{sub} - AstroVed Speaks",
                category="consultation",
                description=f"Consult certified Vedic astrologers and spiritual advisors on {sub}.",
                button_text="Consult Now",
                is_generic=False,
                keywords=parts[-1].replace("-", " ").lower().split() + ["astrologer", "consultation"]
            )

        # 8. Nakshatras (Birth Stars)
        if "astropedia/en/nakshatra" in url:
            if len(parts) == 3:
                return URLCatalogEntry(
                    url=url,
                    title="27 Nakshatras (Birth Stars) Guide",
                    category="nakshatra",
                    description="Explore traits, ruling deities, planetary lords, and remedial mantras for the 27 Vedic birth stars.",
                    button_text="Explore Nakshatras",
                    is_generic=True,
                    keywords=["nakshatra", "nakshatras", "birth", "star", "stars", "27", "guide"]
                )
            star = parts[-1].replace("-nakshatra", "").title()
            return URLCatalogEntry(
                url=url,
                title=f"{star} Nakshatra Guide & Remedies",
                category="nakshatra",
                description=f"Personality traits, ruling planet, divine archetype, and auspicious remedies for {star} Nakshatra.",
                button_text=f"Explore {star}",
                is_generic=False,
                keywords=[star.lower(), "nakshatra", "birth", "star", "remedies", "deity", "affliction"]
            )

        # 9. Planets (Grahas)
        if "astropedia/en/planets" in url:
            p_name = parts[-1].title()
            sanskrit_map = {
                "Sukra": "Venus (Sukra)", "Ketu": "South Node (Ketu)", "Guru": "Jupiter (Guru)",
                "Sani": "Saturn (Shani)", "Surya": "Sun (Surya)", "Rahu": "North Node (Rahu)",
                "Mars": "Mars (Mangal)", "Chandra": "Moon (Chandra)", "Budha": "Mercury (Budha)"
            }
            title_p = sanskrit_map.get(p_name, p_name)
            return URLCatalogEntry(
                url=url,
                title=f"{title_p} Planetary Guide & Remedies",
                category="planets",
                description=f"Learn the significance, transit effects, signs, and Vedic pacification remedies for {title_p}.",
                button_text=f"Explore {p_name}",
                is_generic=False,
                keywords=[p_name.lower(), title_p.lower(), "planet", "graha", "astrology", "remedies", "transit"]
            )

        # 10. Virtual Pooja
        if "astropedia/en/virtual-pooja" in url:
            if len(parts) == 3:
                return URLCatalogEntry(
                    url=url,
                    title="AstroVed Virtual Poojas",
                    category="virtual_pooja",
                    description="Perform sacred interactive deity poojas online with authentic Vedic mantras and offerings.",
                    button_text="Explore Virtual Poojas",
                    is_generic=True,
                    keywords=["virtual", "pooja", "puja", "online", "worship"]
                )
            p_slug = parts[-1].replace("-", " ").title()
            return URLCatalogEntry(
                url=url,
                title=f"Virtual {p_slug}",
                category="virtual_pooja",
                description=f"Participate in interactive online {p_slug} with traditional mantras and sacred offerings.",
                button_text=f"Perform {p_slug}",
                is_generic=False,
                keywords=parts[-1].replace("-", " ").lower().split() + ["virtual", "pooja", "puja", "worship", "deity"]
            )

        # 11. Festivals & Power Timings
        if "astropedia/en/festivals" in url:
            f_name = parts[-1].replace("-", " ").title()
            return URLCatalogEntry(
                url=url,
                title=f"{f_name} - Timings & Rituals",
                category="festivals",
                description=f"Auspicious power timings, spiritual significance, fasting guidelines, and ritual remedies for {f_name}.",
                button_text=f"Explore {f_name}",
                is_generic=False,
                keywords=parts[-1].replace("-", " ").lower().split() + ["festival", "dates", "timings", "fasting", "vrata", "rituals"]
            )

        # 12. Baby Names
        if "astropedia/en/babynames" in url:
            bn = parts[-1].replace("-", " ").title()
            return URLCatalogEntry(
                url=url,
                title=f"Vedic Baby Names ({bn})",
                category="baby_names",
                description=f"Auspicious Vedic and Sanskrit baby names categorized by astrology, nakshatra sounds, and letters.",
                button_text="Find Baby Names",
                is_generic=False,
                keywords=parts[-1].replace("-", " ").lower().split() + ["baby", "names", "babynames", "vedic", "name"]
            )

        # 13. Temples & Energy Vortexes
        if "/temple/" in url:
            if len(parts) == 1:
                return URLCatalogEntry(
                    url=url,
                    title="Sacred Temples & Energy Vortexes",
                    category="temple",
                    description="Discover powerful Vedic vortexes, ancient deity shrines, and pilgrimage power spots.",
                    button_text="Explore Temples",
                    is_generic=True,
                    keywords=["temple", "temples", "vortex", "shrine", "powerspot"]
                )
            t_name = parts[-1].replace("-", " ").title()
            return URLCatalogEntry(
                url=url,
                title=f"{t_name} Sacred Temple Vortex",
                category="temple",
                description=f"Spiritual significance, history, and planetary remedy blessings of {t_name} temple.",
                button_text=f"Visit {t_name}",
                is_generic=False,
                keywords=parts[-1].replace("-", " ").lower().split() + ["temple", "shrine", "powerspot", "deity"]
            )

        # 14. Priest Services
        if "/priest-services" in url:
            if len(parts) == 1:
                return URLCatalogEntry(
                    url=url,
                    title="Vedic Priest Services & Homas",
                    category="priest_services",
                    description="Certified Vedic priests performing personalized homams, poojas, and rituals according to your birth chart.",
                    button_text="Book Priest Services",
                    is_generic=True,
                    keywords=["priest", "services", "homa", "homam", "pooja"]
                )
            ps = parts[-1].replace("-", " ").title()
            return URLCatalogEntry(
                url=url,
                title=f"{ps} - Priest Services",
                category="priest_services",
                description=f"Customized Vedic priest ceremonies and traditional homams for {ps}.",
                button_text=f"Book {ps}",
                is_generic=False,
                keywords=parts[-1].replace("-", " ").lower().split() + ["priest", "services", "homa"]
            )

        # 15. Fire Labs / Homas / Poojas / Tarpanam (Remedies)
        if any(k in url for k in ["fire-lab", "pooja", "homa", "tarpanam", "package"]):
            clean = parts[0].split("--")[0] if "--" in parts[0] else parts[0]
            clean = re.sub(r"-P\d+\.aspx", "", clean, flags=re.IGNORECASE)
            clean_title = clean.replace("-", " ").title()
            slug_words = re.findall(r"[a-zA-Z0-9]+", parts[0].lower())
            return URLCatalogEntry(
                url=url,
                title=clean_title,
                category="remedy_ritual",
                description=f"Perform sacred Vedic fire lab ceremony {clean_title} to invoke divine blessings and remove karmic obstacles.",
                button_text="Book Ritual",
                is_generic=False,
                keywords=slug_words + ["ritual", "homa", "fire", "lab", "pooja", "remedy", "homam"]
            )

        # 16. Astropedia Portal Hub
        if url == "https://www.astroved.com/astropedia/en/home":
            return URLCatalogEntry(
                url=url,
                title="Astropedia Portal Hub",
                category="portal_home",
                description="Educational astrological encyclopedia and resource hub on AstroVed.",
                button_text="Open Astropedia",
                is_generic=True,
                keywords=["astropedia", "hub", "home", "portal", "encyclopedia"]
            )

        # 17. Best Astrologer in Mumbai
        if "best-astrologer-in-mumbai" in url:
            return URLCatalogEntry(
                url=url,
                title="Best Astrologer in Mumbai",
                category="consultation",
                description="Consult verified top Vedic astrologers in Mumbai for accurate horoscope predictions and remedial advice.",
                button_text="Consult in Mumbai",
                is_generic=False,
                keywords=["mumbai", "astrologer", "best", "consultation"]
            )

        fallback_title = parts[-1].replace("-", " ").title()
        return URLCatalogEntry(
            url=url,
            title=fallback_title,
            category="other",
            description=f"Official AstroVed service: {fallback_title}.",
            button_text="Explore Service",
            is_generic=False,
            keywords=re.findall(r"[a-zA-Z0-9]+", parts[-1].lower())
        )

    def _build_catalogue(self):
        raw_urls = self._load_raw_urls()
        self.entries = [self._extract_metadata(u) for u in raw_urls]
        self._url_set = {e.url for e in self.entries}
        logger.info("URL Catalogue initialized with %d verified entries.", len(self.entries))

    def get_all_verified_urls(self) -> Set[str]:
        return self._url_set

    def _score_entry(self, query_tokens: Set[str], entry: URLCatalogEntry, raw_query: str, direct_tokens: Optional[Set[str]] = None) -> float:
        # Rule 1 & 5: Generic hub pages must never be returned when matching
        if entry.is_generic:
            return -100.0

        raw_lower = raw_query.lower()
        slug = urlparse(entry.url).path.lower()
        entry_title = entry.title.lower()

        title_tokens = set(re.findall(r"[a-zA-Z0-9]+", entry_title))
        keyword_tokens = set(entry.keywords)
        slug_tokens = set(re.findall(r"[a-zA-Z0-9]+", slug))

        all_entry_tokens = title_tokens | keyword_tokens | slug_tokens

        # Distinctive entity constraint (Nakshatras, Doshas, Deities, Planets, Cities, Festivals)
        # Must be checked against direct_tokens (what the user actually typed)
        check_tokens = direct_tokens if direct_tokens is not None else query_tokens
        raw_query_entities = DISTINCT_ENTITIES.intersection(check_tokens)
        if raw_query_entities:
            query_entities = {ENTITY_CANONICAL_MAP.get(e, e) for e in raw_query_entities}
            raw_entry_entities = DISTINCT_ENTITIES.intersection(all_entry_tokens)
            entry_entities = {ENTITY_CANONICAL_MAP.get(e, e) for e in raw_entry_entities}
            # If the entry does not contain ANY of the requested distinct entities, reject it
            if not query_entities.intersection(entry_entities):
                return 0.0
            # If entry contains a different distinct entity that was NOT in query (e.g. saturn when user asked for pure pradosham, or moola when user asked for ashwini), reject it
            extraneous_entities = entry_entities - query_entities
            if extraneous_entities:
                return 0.0

        intersection = query_tokens.intersection(all_entry_tokens)
        if not intersection:
            return 0.0

        # Base overlap score
        score = len(intersection) / len(query_tokens)

        # 1. Exact phrase matching in title or slug
        if entry_title in raw_lower:
            score += 0.50
        elif raw_lower in entry_title:
            score += 0.35

        # 2. Slug specific match (e.g. 'ashwini' in query and 'ashwini' in slug)
        for t in query_tokens:
            if t in slug_tokens:
                score += 0.15

        # 3. Specificity boost: penalize extra unmatched specific tokens in slug
        if "pradosham" in query_tokens and "sani" not in query_tokens and "sani" in slug_tokens:
            score -= 0.30
        if "pradosham" in query_tokens and "soma" not in query_tokens and "soma" in slug_tokens:
            score -= 0.30

        # 4. Zodiac Sign matching
        query_signs = [s for s in ZODIAC_SIGNS if s in query_tokens]
        if query_signs:
            entry_signs = [s for s in ZODIAC_SIGNS if s in slug_tokens or s in title_tokens]
            if set(query_signs).issubset(set(entry_signs)):
                score += 0.40
                # Preserve ordering for compatibility pairs: e.g. 'aquarius and gemini' -> 'aquarius-gemini'
                if len(query_signs) >= 2:
                    ordered_pair = f"{query_signs[0]}-{query_signs[1]}"
                    if ordered_pair in slug:
                        score += 0.30
            elif entry_signs:
                score -= 0.60

        # 5. Core service exact boosts
        if "matching" in query_tokens and "horoscope-matching" in entry.url:
            score += 0.40
        if "kundli" in query_tokens and "horoscope-matching" in entry.url and any(w in query_tokens for w in ["matching", "milan", "wedding", "marriage"]):
            score += 0.40
        if "sade" in query_tokens and "sade-sati" in entry.url:
            score += 0.40
        if "numerology" in query_tokens and "numerology" in entry.url:
            score += 0.40
        if "tarpanam" in query_tokens and "tarpanam" in entry.url:
            score += 0.40
        is_general_horoscope = any(w in query_tokens for w in ["horoscope", "prediction", "predictions", "forecast"])
        if is_general_horoscope and not query_signs and "monthly" not in query_tokens:
            has_love = any(w in check_tokens for w in ["love", "romance", "relationship", "couple", "partner"])
            if not has_love:
                if entry.url == "https://www.astroved.com/horoscope/":
                    score += 0.45
                elif "daily-love-horoscope" in entry.url:
                    score -= 0.50
        if "career" in query_tokens and "astrologer/career" in entry.url:
            score += 0.40

        # Nadi Leaf reading distinction
        if "leaf" in check_tokens and "nadi-leaf-reading" in entry.url:
            score += 0.50
        elif "leaf" not in check_tokens and "nadi-astrology" in entry.url:
            score += 0.35

        # Remedy / Homa distinction vs calculator
        is_homa_query = any(w in query_tokens for w in ["homa", "homam", "fire", "lab", "ritual"])
        if is_homa_query:
            if entry.category == "remedy_ritual":
                score += 0.35
            elif entry.category == "free_tool":
                score -= 0.30

        return min(max(score, 0.0), 1.0)

    def search(self, query: str, min_confidence: float = 0.40) -> URLMatchResult:
        """
        Generic, scalable intent-to-URL matching covering all AstroVed pages in all_urls.txt.
        """
        raw_clean = query.strip().lower()

        # Check for queries representing services known to be missing from all_urls.txt
        # Rule: Do not invent URLs, never redirect to generic Astropedia home, offer human support.
        is_birth_chart_query = any(k in raw_clean for k in [
            "birth chart", "birthchart", "generate kundli", "kundli generate",
            "make kundli", "calculate birth chart", "free birth chart", "kundli creation",
            "janam kundli", "janam patri", "create kundli", "my kundli"
        ])
        if is_birth_chart_query:
            # Check for multi-intent: does query also ask for an available indexed service (e.g. horoscope, numerology)?
            sub_query = re.sub(
                r"\b(?:birth\s*chart|kundli|kundali|birthchart|janam\s*kundli|free\s*birth\s*chart|generate\s*kundli|my\s*kundli)\b",
                "",
                raw_clean,
                flags=re.IGNORECASE
            ).strip()
            has_other_intent = any(k in sub_query for k in ["horoscope", "numerology", "matching", "compatibility", "sade", "nadi"])
            if has_other_intent:
                sub_res = self.search(sub_query, min_confidence=min_confidence)
                if sub_res.entry:
                    return URLMatchResult(
                        entry=sub_res.entry,
                        confidence=sub_res.confidence,
                        is_ambiguous=False,
                        candidate_options=[sub_res.entry],
                        clarification_prompt=None,
                        missing_service_msg=(
                            "A dedicated automated Free Birth Chart / Kundli calculation tool is not currently listed "
                            "in our direct online directory. To obtain your complete Vedic birth chart with planetary degrees, "
                            "Ascendant (Lagna), and Dasha analysis calculated by certified experts, please share your date of birth, "
                            "time of birth, and place of birth, or you can connect directly with our astrologers through "
                            "[AstroVed Speaks](https://www.astroved.com/astrovedspeaks/chat-with-astrologer) or our customer support team."
                        )
                    )

            return URLMatchResult(
                entry=None,
                confidence=0.0,
                is_ambiguous=False,
                candidate_options=[],
                clarification_prompt=None,
                missing_service_msg=(
                    "Namaste! A dedicated automated Free Birth Chart / Kundli calculation tool is not currently listed "
                    "in our direct online directory. To obtain your complete Vedic birth chart with planetary degrees, "
                    "Ascendant (Lagna), and Dasha analysis calculated by certified experts, please share your date of birth, "
                    "time of birth, and place of birth, or you can connect directly with our astrologers through "
                    "[AstroVed Speaks](https://www.astroved.com/astrovedspeaks/chat-with-astrologer) or our customer support team."
                )
            )

        if "panchang" in raw_clean:
            return URLMatchResult(
                entry=None,
                confidence=0.0,
                is_ambiguous=False,
                candidate_options=[],
                clarification_prompt=None,
                missing_service_msg=(
                    "Namaste! A dedicated daily Panchang calendar is not currently indexed in our service directory. "
                    "Our customer support team and live astrologers can assist you directly with today's Tithi, Nakshatra, "
                    "and Rahu Kalam timings."
                )
            )

        if "muhurta" in raw_clean or "muhurat" in raw_clean:
            return URLMatchResult(
                entry=None,
                confidence=0.0,
                is_ambiguous=False,
                candidate_options=[],
                clarification_prompt=None,
                missing_service_msg=(
                    "Namaste! A dedicated Muhurta calculation service is not directly listed in our service directory. "
                    "You can consult our senior Vedic astrologers on [AstroVed Speaks](https://www.astroved.com/astrovedspeaks/talk-to-astrologer) "
                    "to determine auspicious timings (Shubh Muhurat) for marriages, housewarmings, or business launches."
                )
            )

        # Normalize tokens with typo map & synonyms
        raw_tokens = [w for w in re.findall(r"[a-zA-Z0-9]+", raw_clean) if len(w) > 1]
        tokens = [TYPO_CORRECTIONS.get(t, t) for t in raw_tokens]

        # 1. Reject explicit off-topic terms (e.g. bluetooth, weather, laptop, loan, recipe, etc.)
        if any(t in OFF_TOPIC_TERMS for t in raw_tokens) or any(t in OFF_TOPIC_TERMS for t in tokens):
            return URLMatchResult(
                entry=None,
                confidence=0.0,
                is_ambiguous=False,
                candidate_options=[],
                clarification_prompt=None,
                missing_service_msg=None
            )

        # 2. Domain Anchor Check: Ensure query possesses astrological relevance
        has_anchor = any(t in ASTRO_ANCHORS for t in tokens) or any(t in ASTRO_ANCHORS for t in raw_tokens)
        if not has_anchor:
            return URLMatchResult(
                entry=None,
                confidence=0.0,
                is_ambiguous=False,
                candidate_options=[],
                clarification_prompt=None,
                missing_service_msg=None
            )

        expanded_tokens = set(tokens)
        for t in tokens:
            if t in ASTRO_SYNONYMS:
                expanded_tokens.update(ASTRO_SYNONYMS[t][:4])

        ranked: List[Tuple[float, URLCatalogEntry]] = []
        direct_tokens_set = set(tokens)
        for e in self.entries:
            score = self._score_entry(expanded_tokens, e, query, direct_tokens=direct_tokens_set)
            if score >= min_confidence:
                ranked.append((score, e))

        ranked.sort(key=lambda x: x[0], reverse=True)

        if not ranked:
            return URLMatchResult(
                entry=None,
                confidence=0.0,
                is_ambiguous=False,
                candidate_options=[],
                clarification_prompt=None,
                missing_service_msg=None
            )

        top_score, top_entry = ranked[0]

        # Explicit ambiguity trigger for broad queries (e.g. 'dosha analysis', 'dosha remedies')
        is_broad_dosha_query = "dosha" in tokens and not any(
            d in raw_clean for d in ["chandal", "grahan", "kalathra", "shrapit", "gandmool", "kemadruma", "amavasya", "eka", "ghat"]
        )

        if is_broad_dosha_query:
            dosha_candidates = [e for s, e in ranked if e.category == "dosha_remedy"][:3]
            if len(dosha_candidates) >= 2:
                clarification_text = (
                    "Namaste! We offer remedies for several specific Vedic doshas:\n\n"
                    + "\n".join(f"{i+1}. **{c.title}**" for i, c in enumerate(dosha_candidates))
                    + "\n\nWhich one would you like to explore?"
                )
                return URLMatchResult(
                    entry=None,
                    confidence=top_score,
                    is_ambiguous=True,
                    candidate_options=dosha_candidates,
                    clarification_prompt=clarification_text
                )

        # Ambiguity check for other queries: only if top 2 have close scores and distinct categories/services
        if len(ranked) > 1 and (top_score - ranked[1][0]) < 0.02 and ranked[1][1].url != top_entry.url:
            alt_score, alt_entry = ranked[1]
            if not alt_entry.is_generic and alt_entry.category != top_entry.category:
                clarification_text = (
                    f"Namaste! We found multiple relevant AstroVed services for your request:\n\n"
                    f"1. **{top_entry.title}**\n"
                    f"2. **{alt_entry.title}**\n\n"
                    f"Which one would you like to explore?"
                )
                return URLMatchResult(
                    entry=None,
                    confidence=top_score,
                    is_ambiguous=True,
                    candidate_options=[top_entry, alt_entry],
                    clarification_prompt=clarification_text
                )

        return URLMatchResult(
            entry=top_entry,
            confidence=top_score,
            is_ambiguous=False,
            candidate_options=[top_entry],
            clarification_prompt=None
        )

    def format_feature_card(self, entry: URLCatalogEntry) -> str:
        """
        Formats a feature card strictly meeting the response UI requirements:
        - Page/service name as normal text (not a separate heading)
        - Relevant two-line description
        - One clear action button
        - Card and button both open the exact URL in a new tab
        """
        return (
            ":::feature_card\n"
            f"title: {entry.title}\n"
            f"description: {entry.description}\n"
            f"button: {entry.button_text}\n"
            f"url: {entry.url}\n"
            ":::"
        )


# Singleton instance
url_catalogue_service = URLCatalogueService()
