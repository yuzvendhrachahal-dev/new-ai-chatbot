"""
AstroVed Product Catalog Service.
Imports, normalizes, caches, and searches AstroVed-only products/services from
the official catalog spreadsheet (Product_List_Astroved.xlsx).
Provides canonical URL generation and customer-facing description synthesis.
"""

import os
import re
import json
import logging
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Base canonical URL pattern for AstroVed products
ASTROVED_BASE_URL = "https://www.astroved.com"

# Common stopwords to exclude when tokenizing search queries
SEARCH_STOPWORDS = {
    "a", "about", "all", "am", "an", "and", "any", "are", "as", "at",
    "be", "been", "being", "both", "but", "by", "can", "could", "did",
    "do", "does", "doing", "for", "from", "had", "has", "have", "having",
    "he", "her", "here", "him", "his", "how", "i", "if", "in", "into",
    "is", "it", "its", "just", "me", "more", "most", "my", "no", "nor",
    "not", "now", "of", "off", "on", "once", "only", "or", "other",
    "our", "ours", "out", "over", "own", "same", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them",
    "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "will",
    "with", "would", "you", "your", "yours", "yourself", "yourselves",
    # Chat conversational fillers
    "please", "tell", "give", "show", "details", "info", "information",
    "looking", "want", "need", "know", "much", "cost", "price", "rate",
    "buy", "purchase", "order", "book", "astroved", "available", "service", "product",
    "non", "none", "suggest", "suggests", "suggestion", "suggestions",
    "recommend", "recommends", "recommendation", "recommendations", "find", "options"
}

# Common spelling mistakes normalization
SPELLING_CORRECTIONS = {
    "poja": "pooja",
    "puja": "pooja",
    "pujaa": "pooja",
    "poojaa": "pooja",
    "poojai": "pooja",
    "pujai": "pooja",
    "rituel": "ritual",
    "rituels": "rituals",
    "ritul": "ritual",
    "rituls": "rituals",
    "homam": "homam",
    "homa": "homam",
    "gemston": "gemstone",
    "gemstons": "gemstone",
    "gemestone": "gemstone",
    "gemestones": "gemstone",
    "rudraksh": "rudraksha",
    "rudrakshas": "rudraksha",
    "rudraksham": "rudraksha",
    "yantram": "yantra",
    "shani": "saturn",
    "sani": "saturn",
    "saniswaran": "saturn",
    "shaniswara": "saturn",
    "shanidev": "saturn",
    "guru": "jupiter",
    "brihaspati": "jupiter",
    "mangal": "mars",
    "chevvai": "mars",
    "shukra": "venus",
    "budha": "mercury",
    "surya": "sun",
    "chandra": "moon",
    "ganapathi": "ganesha",
    "vinayaka": "ganesha",
    "recomended": "recommend",
    "recomend": "recommend",
    "suggests": "suggest",
    "sugest": "suggest",
}

def normalize_spelling(text: str) -> str:
    """Normalizes spelling mistakes and maps common typos to canonical terms."""
    if not text:
        return ""
    words = re.findall(r"\b[a-zA-Z0-9']+\b|[^\w\s]", text)
    corrected = []
    for w in words:
        low = w.lower()
        if low in SPELLING_CORRECTIONS:
            corrected.append(SPELLING_CORRECTIONS[low])
        else:
            corrected.append(w)
    return " ".join(corrected)

# Planet, deity, and category terms for detecting specific ritual/pooja requests
PLANET_DEITY_TERMS = (
    r"(?:saturn|shani|sani|jupiter|guru|brihaspati|mars|mangal|chevvai|venus|shukra|"
    r"mercury|budha|sun|surya|moon|chandra|rahu|ketu|navagraha|ganesha|ganapathi|"
    r"lakshmi|ashtalakshmi|shiva|muruga|subrahmanya|hanuman|dhanvantari|ayush|mrityunjaya|"
    r"love|relationship|relationships|marriage|wealth|career|health)"
)
RITUAL_TERMS = r"(?:rituals?|poojas?|pujas?|homams?|homas?|archanas?|abhishekams?|fire\s*labs?)"

# Commercial/product intent indicators to identify product/service questions
PRODUCT_INTENT_KEYWORDS = [
    r"\b(?:cost|price|how\s+much|rate|fee|fees|charges?|pricing|inr)\b",
    r"\b(?:buy|purchase|order|book|booking|subscribe|hire|schedule)\b",
    r"\b(?:products?|services?|packages?|programs?|reports?)\b",
    r"\b(?:pooja|poojas|puja|pujas|homam|homams|homa|fire\s*labs?|archana|abhishekam?)\b",
    r"\b(?:yantra|yantras|gemstones?|rudraksha|malas?|statues?|idols?|bracelets?|pendants?|rings?)\b",
    r"\b(?:online\s+consultation|astrologer\s+consultation|book\s+consultation)\b",
    r"\b(?:do\s+you\s+have|do\s+you\s+offer|is\s+there\s+any|can\s+i\s+(?:buy|get|book))\b",
    r"\b(?:available\s+(?:rituals?|remedies|poojas?|services?)|(?:rituals?|remedies|poojas?|services?)\s+(?:are\s+)?available)\b",
    r"\b(?:suggest|recommend|find|show|give|get)\s+(?:me\s+)?(?:a\s+|some\s+)?(?:[\w\s]+\s+)?(?:rituals?|poojas?|pujas?|homams?|services?|packages?|remedies|products?|offerings?|gemstones?)\b",
    r"\b(?:suggest|recommend)\s+(?:me\s+)?(?:a\s+)?(?:love|saturn|shani|wealth|gemstone|relationship)\s+(?:pooja|ritual|homam|gemstone)?\b",
    r"\b(?:love\s+pooja|love\s+ritual|saturn\s+ritual|saturn\s+pooja|shani\s+ritual|recommend\s+a\s+gemstone)\b",
    r"\b(?:lost\s+my\s+job|lost\s+job|job\s+loss|jobless|unemployed|unemployment)\b",
    r"\b(?:career|job|profession)\s+(?:pooja|ritual|homam|remedy|remedies|offerings?)\b",
    rf"\b{PLANET_DEITY_TERMS}\s+{RITUAL_TERMS}\b",
    rf"\b{RITUAL_TERMS}\s+(?:for|to|of)\s+{PLANET_DEITY_TERMS}\b",
]

# Informational astrology queries that should NOT trigger catalog search
GENERAL_ASTROLOGY_PATTERNS = [
    r"^(?:what\s+is|what\s+does|meaning\s+of|significance\s+of|tell\s+me\s+about|explain)\s+(?:the\s+)?(?:role\s+of\s+)?(?:love|saturn|venus|jupiter|mars|mercury|sun|moon|rahu|ketu|dosha|karma)\s+(?:in\s+(?:vedic\s+)?astrology|in\s+horoscope|in\s+kundli|in\s+my\s+life)?\??$",
    r"^(?:what\s+is\s+love|what\s+is\s+saturn|what\s+is\s+jupiter|what\s+is\s+venus|what\s+is\s+mars|what\s+is\s+mercury|what\s+is\s+sun|what\s+is\s+moon|what\s+is\s+rahu|what\s+is\s+ketu)\b.*",
    r"^(?:what\s+is\s+(?:a\s+)?(?:dasha|nakshatra|lagna|ascendant|rashi|bhava|house|sade\s+sati))\b.*",
]

# Quick action queries that have dedicated flows and should NOT trigger catalog search
QUICK_ACTION_PATTERNS = [
    r"^(?:🌙\s*)?(?:today'?s?\s+)?horoscope\b",
    r"^(?:📊\s*)?(?:free\s+)?birth\s*chart\b",
    r"^(?:💑\s*)?compatibility\s*(?:match(?:ing)?)?\b",
    r"^(?:🌿\s*)?remedies\b",
    r"\bdaily\s+horoscope\b",
    r"\bhoroscope\s+today\b",
    r"\b(?:my\s+)?daily\s+prediction\b",
    r"\bkundli\b",
    r"\bjanam\s*patri\b",
]

# Synonyms for token matching in catalog search
SYNONYMS = {
    "shani": "saturn",
    "sani": "saturn",
    "saniswaran": "saturn",
    "shaniswara": "saturn",
    "shanidev": "saturn",
    "guru": "jupiter",
    "brihaspati": "jupiter",
    "mangal": "mars",
    "chevvai": "mars",
    "shukra": "venus",
    "budha": "mercury",
    "surya": "sun",
    "chandra": "moon",
    "ganapathi": "ganesha",
    "vinayaka": "ganesha",
    "puja": "pooja",
    "poja": "pooja",
    "homa": "homam",
    "gemston": "gemstone",
    "gemstons": "gemstone",
    # Love / relationship mappings
    "valentine": "love",
    "valentines": "love",
    "romance": "love",
    "relationship": "love",
    "relationships": "love",
    "marriage": "love",
    # Career / job mappings
    "job": "career",
    "jobs": "career",
    "employment": "career",
    "profession": "career",
    "work": "career",
    "unemployed": "career",
    "business": "career",
}


def canonical_token(t: str) -> str:
    """Normalizes token to base canonical form and removes plurals."""
    t = t.lower()
    t = SYNONYMS.get(t, t)
    if t.endswith("ies") and len(t) > 4:
        t = t[:-3] + "y"
    elif t.endswith("s") and not t.endswith("ss") and len(t) > 3:
        t = t[:-1]
    return t


def strip_dates(text: str) -> str:
    """Removes calendar dates, day names, and years from text to satisfy 'do not show dates'."""
    if not text:
        return ""
    # Strip months and days (e.g. "on March 25th (IST)", "on May 11th", "July 21st")
    cleaned = re.sub(
        r"\b(?:on\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*\([^)]*\)|\s*IST)?\b",
        "",
        text,
        flags=re.IGNORECASE
    )
    # Strip years (e.g. 2014, 2015, 2016)
    cleaned = re.sub(r"\b\d{4}\b", "", cleaned)
    # Strip timezones
    cleaned = re.sub(r"\b(?:IST|PST|EST|GMT|UTC)\b", "", cleaned)
    # Collapse multiple spaces and clean punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([,.:;])", r"\1", cleaned)
    cleaned = re.sub(r"([(\[])\s*([)\]])", "", cleaned)
    return cleaned.strip(" -:,")


class NormalizedProduct(BaseModel):
    """
    Normalized AstroVed product or service record.
    Preserves core catalog fields while stripping long descriptions and dates.
    """
    product_id: str
    product_name: str
    short_description: str
    manufacturer_name: str
    available_shops: str
    price_inr: Optional[float] = None
    formatted_price: Optional[str] = None
    product_status: str
    url: str

    def to_reference_dict(self) -> Dict[str, Any]:
        """Converts product to a reference context dictionary for the LLM."""
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "short_description": self.short_description,
            "manufacturer_name": self.manufacturer_name,
            "formatted_price": self.formatted_price or "Price not listed",
            "url": self.url,
            "status": self.product_status
        }


def generate_product_slug(product_name: str) -> str:
    """
    Generates a URL slug from the product name according to AstroVed requirements:
    - lowercase
    - replace spaces with hyphens
    - remove punctuation and unsupported characters (keeps a-z, 0-9, and -)
    - collapse repeated hyphens
    - strip leading/trailing hyphens
    """
    if not product_name:
        return ""
    slug = product_name.lower().strip()
    # Replace whitespace, underscores, slashes, and ampersands with hyphens
    slug = re.sub(r"[\s_/\\&]+", "-", slug)
    # Remove punctuation and unsupported characters (allow letters, digits, and hyphens)
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    # Collapse repeated hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading and trailing hyphens
    return slug.strip("-")


def generate_product_url(product_id: Union[str, int], product_name: str) -> str:
    """
    Generates a product URL using the canonical pattern:
    https://www.astroved.com/{slug}-P{ProductId}.aspx
    Preserves the product ID in the required P{ProductId} suffix.
    Kept in one centralized helper so it can be adjusted if the .NET team provides a canonical URL API.
    """
    pid = str(product_id).strip()
    slug = generate_product_slug(product_name)
    if slug:
        return f"{ASTROVED_BASE_URL}/{slug}-P{pid}.aspx"
    return f"{ASTROVED_BASE_URL}/product-P{pid}.aspx"


def parse_inr_price(price_val: Any) -> Tuple[Optional[float], Optional[str]]:
    """
    Parses and formats INR price:
    - Format valid positive prices as '₹' amounts (e.g. ₹225, ₹3,330).
    - If INR price is missing, empty, 0, negative, or invalid, returns (None, None)
      rather than inventing a price.
    """
    if price_val is None:
        return None, None
    raw = str(price_val).strip()
    if not raw:
        return None, None
    try:
        clean = raw.replace(",", "").replace("₹", "").replace("Rs.", "").strip()
        num = float(clean)
        if num <= 0:
            return None, None
        if num.is_integer():
            return int(num), f"₹{int(num):,}"
        return num, f"₹{num:,.2f}"
    except (ValueError, TypeError):
        return None, None


def is_astroved_only(available_shops: str) -> bool:
    """
    Distinguishes AstroVed-only records from PillaiCenter records:
    - Include AstroVed-only records.
    - Exclude records associated with PillaiCenter; do not expose PillaiCenter products.
    - If a record is shared between AstroVed and PillaiCenter (e.g. 'AstroVed | PillaiCenter'),
      exclude it for now.
    """
    if not available_shops:
        return False
    shops = [s.strip() for s in available_shops.split("|") if s.strip()]
    if not shops:
        return False

    # Exclude if PillaiCenter is present anywhere in shops
    if any("pillaicenter" in s.lower() or "pillai" in s.lower() for s in shops):
        return False

    # Exclude if not AstroVed
    if not any("astroved" in s.lower() for s in shops):
        return False

    # Only include records where shop is exclusively AstroVed
    return all(s.lower() == "astroved" for s in shops)


def is_product_query(text: str) -> bool:
    """
    Evaluates whether the user's message is asking about AstroVed products,
    services, rituals, poojas, remedies, consultations, or pricing.
    - Normalizes common spelling mistakes before checking.
    - Ordinary questions such as "What is love in Vedic astrology?" or "What is Saturn in Vedic astrology?"
      return False to preserve conversational AI.
    - Quick actions (Horoscope, Birth Chart, Compatibility, Remedies) return False.
    - Greetings, gratitude, and small talk return False.
    """
    if not text or not text.strip():
        return False
    cleaned = text.strip().lower()

    # 1. Quick action prompt chips should not trigger product catalog search
    for qa_pat in QUICK_ACTION_PATTERNS:
        if re.search(qa_pat, cleaned, re.IGNORECASE):
            return False

    # 2. General astrology conceptual questions (e.g. "What is love in Vedic astrology?")
    # should route to conversational AI, unless commercial terms are present
    has_commercial = any(
        re.search(pat, cleaned, re.IGNORECASE) for pat in [
            r"\b(?:cost|price|buy|purchase|order|book|fee|inr|charges?)\b",
            r"\b(?:pooja|poojas|puja|pujas|homam|homams|ritual|rituals|package|service|gemstone|gemstones)\b",
            r"\b(?:suggest|recommend)\b"
        ]
    )
    if not has_commercial:
        for gen_pat in GENERAL_ASTROLOGY_PATTERNS:
            if re.search(gen_pat, cleaned, re.IGNORECASE):
                return False

    # 3. Normalize common spelling mistakes (e.g. "love poja" -> "love pooja", "gemston" -> "gemstone")
    normalized = normalize_spelling(cleaned)

    # 4. Check against product intent keyword patterns
    for pattern in PRODUCT_INTENT_KEYWORDS:
        if re.search(pattern, cleaned, re.IGNORECASE) or re.search(pattern, normalized, re.IGNORECASE):
            return True

    return False


def load_and_normalize_catalog(
    excel_path: Optional[Path] = None,
    cache_path: Optional[Path] = None
) -> List[NormalizedProduct]:
    """
    Streams and normalizes product records from the Excel file:
    - Uses Python zipfile + xml.etree.ElementTree streaming (zero extra dependencies).
    - Filters for AstroVed-only records (excludes PillaiCenter).
    - Includes both Active and Disabled records.
    - Ignores Start Date, End Date, and all other dates.
    - Formats valid INR prices with '₹' and omits invalid/missing prices.
    - Ignores Long Description (HTML).
    - Caches normalized JSON for instant reload.
    """
    # Locate excel file
    candidates = []
    if excel_path:
        candidates.append(Path(excel_path))

    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    candidates.extend([
        root_dir / "data" / "Product_List_Astroved.xlsx",
        root_dir / "data" / "Product_List_AStroved.xlsx",
        root_dir / "Product_List_Astroved.xlsx",
        root_dir / "Product_List_AStroved.xlsx",
    ])

    resolved_excel: Optional[Path] = None
    for cand in candidates:
        if cand.is_file():
            resolved_excel = cand
            break

    if not resolved_excel:
        logger.warning("Product catalog Excel file not found in candidate paths.")
        return []

    # Check cached JSON
    resolved_cache = cache_path or (root_dir / "data" / "astroved_products_normalized.json")
    resolved_cache = Path(resolved_cache)

    if resolved_cache.is_file():
        try:
            excel_mtime = resolved_excel.stat().st_mtime
            cache_mtime = resolved_cache.stat().st_mtime
            if cache_mtime >= excel_mtime:
                with open(resolved_cache, "r", encoding="utf-8") as f:
                    data = json.load(f)
                products = [NormalizedProduct(**item) for item in data]
                logger.info("Loaded %d normalized AstroVed products from cache.", len(products))
                return products
        except Exception as err:
            logger.warning("Failed to load normalized catalog cache: %s", err)

    # Stream parse from Excel
    logger.info("Streaming and normalizing catalog from %s...", resolved_excel)
    normalized: List[NormalizedProduct] = []

    try:
        with zipfile.ZipFile(resolved_excel, "r") as z:
            # 1. Parse shared strings with iterparse
            shared_strings: List[str] = []
            if "xl/sharedStrings.xml" in z.namelist():
                for _, elem in ET.iterparse(z.open("xl/sharedStrings.xml"), events=("end",)):
                    if elem.tag.endswith("si"):
                        text = "".join(elem.itertext())
                        shared_strings.append(text)
                        elem.clear()

            # 2. Parse sheet1.xml row by row
            col_idx: Dict[str, str] = {}
            row_count = 0

            for _, elem in ET.iterparse(z.open("xl/worksheets/sheet1.xml"), events=("end",)):
                if elem.tag.endswith("row"):
                    row_count += 1
                    row_dict: Dict[str, str] = {}
                    for c in elem:
                        r = c.get("r")
                        if not r:
                            continue
                        col = "".join(ch for ch in r if ch.isalpha())
                        t = c.get("t")
                        v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                        val = v.text if v is not None else ""
                        if t == "s" and val.isdigit():
                            idx = int(val)
                            if idx < len(shared_strings):
                                val = shared_strings[idx]
                        row_dict[col] = val
                    elem.clear()

                    # Header row
                    if row_count == 1:
                        col_idx = {v.strip(): k for k, v in row_dict.items() if v}
                        continue

                    shop = row_dict.get(col_idx.get("Available Shops", "O"), "").strip()
                    if not is_astroved_only(shop):
                        continue

                    pid = row_dict.get(col_idx.get("Product Id", "A"), "").strip()
                    name = row_dict.get(col_idx.get("Product Name", "B"), "").strip()
                    if not pid or not name:
                        continue

                    desc = row_dict.get(col_idx.get("Short Description", "C"), "").strip()
                    mfg = row_dict.get(col_idx.get("Manufacturer Name", "F"), "").strip()
                    status = row_dict.get(col_idx.get("Product Status", "K"), "").strip()
                    raw_price = row_dict.get(col_idx.get("Price INR", "I"), "").strip()

                    num_price, fmt_price = parse_inr_price(raw_price)
                    url = generate_product_url(pid, name)

                    normalized.append(NormalizedProduct(
                        product_id=pid,
                        product_name=name,
                        short_description=desc,
                        manufacturer_name=mfg,
                        available_shops=shop,
                        price_inr=num_price,
                        formatted_price=fmt_price,
                        product_status=status,
                        url=url
                    ))

        # Save to JSON cache for fast future startup
        try:
            resolved_cache.parent.mkdir(parents=True, exist_ok=True)
            with open(resolved_cache, "w", encoding="utf-8") as f:
                json.dump([p.model_dump() for p in normalized], f, ensure_ascii=False)
            logger.info("Saved %d normalized AstroVed products to cache (%s).", len(normalized), resolved_cache)
        except Exception as err:
            logger.warning("Could not write catalog cache: %s", err)

    except Exception as err:
        logger.error("Failed to parse Excel file %s: %s", resolved_excel, err)

    return normalized

def apply_result_rules(products: List[NormalizedProduct]) -> List[NormalizedProduct]:
    """
    Applies AstroVed product recommendation result rules:
    - 1 relevant match: show 1.
    - 2–4 relevant matches: show all.
    - More than 4 relevant matches: show the top 3.
    """
    n = len(products)
    if n <= 1:
        return products
    elif 2 <= n <= 4:
        return products
    else:
        return products[:3]


class CatalogService:
    """
    In-memory singleton catalog service providing search, lookup, and description generation.
    """
    def __init__(self):
        self._products: List[NormalizedProduct] = []
        self._product_by_id: Dict[str, NormalizedProduct] = {}
        self._initialized: bool = False

    def initialize(self):
        """Loads and indexes the catalog."""
        if self._initialized:
            return
        self._products = load_and_normalize_catalog()
        self._product_by_id = {p.product_id: p for p in self._products}
        self._initialized = True
        logger.info("CatalogService initialized with %d products.", len(self._products))

    @property
    def products(self) -> List[NormalizedProduct]:
        if not self._initialized:
            self.initialize()
        return self._products

    def get_by_id(self, product_id: str) -> Optional[NormalizedProduct]:
        if not self._initialized:
            self.initialize()
        return self._product_by_id.get(str(product_id).strip())

    def search(
        self,
        query: str,
        top_k: Optional[int] = 3,
        category: Optional[str] = None
    ) -> List[NormalizedProduct]:
        """
        Searches the catalog for query matches using tokenized relevance scoring and category awareness.
        Normalizes spelling mistakes and maps relevant synonyms to catalog terms.
        Applies AstroVed recommendation result rules:
        - 1 match: show 1
        - 2-4 matches: show all
        - >4 matches: show top 3 (or top_k if explicitly passed)
        """
        if not self._initialized:
            self.initialize()
        if not query or not query.strip():
            return []

        # Normalize spelling of query
        normalized_query = normalize_spelling(query.lower().strip())
        raw_tokens = [
            t for t in re.findall(r"\b[a-z0-9]+\b", normalized_query)
            if t not in SEARCH_STOPWORDS and len(t) >= 2
        ]
        if not raw_tokens:
            return []

        tokens = [canonical_token(t) for t in raw_tokens]

        generic_ritual_terms = {
            "pooja", "puja", "homam", "homa", "ritual", "rituals",
            "service", "services", "package", "packages", "remedy",
            "remedies", "consultation", "consult", "archana"
        }
        generic_tokens = [t for t in tokens if t in generic_ritual_terms]
        specific_tokens = [t for t in tokens if t not in generic_ritual_terms]

        # Determine target category keywords if category is provided or inferred
        category_cue_map = {
            "career": {"career", "job", "employment", "profession", "business", "work", "unemployed", "karuppasamy", "vishnupati"},
            "love": {"love", "relationship", "marriage", "partner", "romance", "spouse", "muruga", "valli"},
            "love_relationship": {"love", "relationship", "marriage", "partner", "romance", "spouse", "muruga", "valli"},
            "saturn": {"saturn", "shani", "sani", "sade sati", "saniswaran", "shaniswara"},
            "saturn_shani": {"saturn", "shani", "sani", "sade sati", "saniswaran", "shaniswara"},
            "wealth": {"wealth", "money", "financial", "prosperity", "lakshmi", "kubera"},
            "health": {"health", "ayush", "mrityunjaya", "dhanvantari", "longevity"},
            "gemstone": {"gemstone", "ruby", "emerald", "sapphire", "citrine", "mala", "rudraksha"},
        }
        active_cat_keywords = category_cue_map.get(category or "", set())
        for tok in specific_tokens:
            if tok in category_cue_map:
                active_cat_keywords.update(category_cue_map[tok])

        scored: List[Tuple[float, NormalizedProduct]] = []

        for p in self._products:
            name_words = {canonical_token(w) for w in re.findall(r"\b[a-z0-9]+\b", p.product_name.lower())}
            desc_words = {canonical_token(w) for w in re.findall(r"\b[a-z0-9]+\b", p.short_description.lower())}

            # If specific intent terms were asked (e.g. 'love', 'saturn', 'gemstone'),
            # require at least one specific term or category keyword to match
            combined_specific = set(specific_tokens).union(active_cat_keywords)
            if combined_specific and not any(st in name_words or st in desc_words for st in combined_specific):
                continue

            score = 0.0
            matched_tokens = 0
            all_matched = True

            # Exact phrase match bonus
            if len(tokens) > 1 and normalized_query in p.product_name.lower():
                score += 35.0

            matched_specific = sum(1 for st in combined_specific if st in name_words or st in desc_words)
            matched_ritual = sum(1 for rt in generic_tokens if rt in name_words or rt in desc_words or any(gr in name_words for gr in generic_ritual_terms))

            for token in tokens:
                is_specific = token in specific_tokens
                weight = 8.0 if is_specific else 2.0
                if token in name_words:
                    score += weight * 5.0
                    matched_tokens += 1
                elif token in desc_words:
                    score += weight * 1.5
                    matched_tokens += 1
                else:
                    all_matched = False

            # Category synergy bonus (e.g. career keyword + ritual term)
            if active_cat_keywords:
                cat_in_name = any(ck in name_words for ck in active_cat_keywords)
                cat_in_desc = any(ck in desc_words for ck in active_cat_keywords)
                if cat_in_name:
                    score += 55.0
                    matched_tokens += 1
                elif cat_in_desc:
                    score += 25.0
                    matched_tokens += 1

            if matched_tokens == 0 and score == 0.0:
                continue

            # Multi-token bonus if all query tokens matched
            if all_matched and len(tokens) > 1:
                score += 40.0

            # Boost when both specific intent/planet AND ritual terms match
            if matched_specific > 0 and matched_ritual > 0:
                score += 50.0

            # Boost when ritual/package appears in product title
            if any(rt in name_words for rt in ["ritual", "package", "pooja", "homam"]):
                score += 25.0

            # Slight tie-breaker preference for products with valid listed INR prices
            if p.price_inr is not None:
                score += 2.0

            # Require minimum matched ratio for multi-word queries unless category + ritual matched
            has_cat_ritual_synergy = matched_specific > 0 and matched_ritual > 0
            if len(tokens) >= 3 and not has_cat_ritual_synergy and (matched_tokens / len(tokens)) < 0.4:
                continue

            if score >= 10.0:
                scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        raw_results = [p for _, p in scored]

        if top_k is not None:
            return raw_results[:top_k]
        return apply_result_rules(raw_results)

    def format_offline_response(self, query: str, products: List[NormalizedProduct]) -> str:
        """
        Generates a concise, grounded offline response when the OpenAI LLM is not configured or unavailable.
        Uses the Excel Short Description column as the source, formatted into 2-3 lines.
        Never uses Long Description HTML or fabricates inclusions, benefits, dates, or pricing.
        Applies result rules: 1 match -> show 1, 2-4 matches -> show all, >4 -> show top 3.
        """
        if not products:
            return (
                "Namaste. I could not find a matching AstroVed catalog item for your request. "
                "For customized remedial recommendations, temple rituals, or personalized chart analysis, "
                "our live astrology advisors would be glad to assist you. Would you like me to connect you with an advisor?"
            )

        target_products = apply_result_rules(products)
        items_formatted = []
        for p in target_products:
            raw_desc = (p.short_description or "").strip()
            clean_desc = re.sub(r"<[^>]+>", "", raw_desc)
            clean_desc = strip_dates(clean_desc)
            if clean_desc:
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_desc) if s.strip()]
                # Format into 2-3 concise lines from Excel Short Description only
                if len(sentences) >= 3:
                    short_desc = " ".join(sentences[:3])
                elif len(sentences) == 2:
                    short_desc = " ".join(sentences[:2])
                elif sentences:
                    short_desc = sentences[0]
                if not short_desc.endswith("."):
                    short_desc += "."
            else:
                short_desc = f"Official Vedic spiritual offering for {p.product_name}."

            if p.product_status == "Disabled":
                short_desc += " Remedial reference item (not currently available for direct purchase)."

            card_lines = [
                ":::product_card",
                f"name: {p.product_name}",
            ]
            if p.formatted_price:
                card_lines.append(f"price: {p.formatted_price}")
            card_lines.append(f"description: {short_desc}")
            card_lines.append(f"url: {p.url}")
            card_lines.append(":::")
            items_formatted.append("\n".join(card_lines))

        result = (
            "Namaste! Here are relevant offerings from the AstroVed catalog:\n\n" +
            "\n\n".join(items_formatted)
        )
        return result

    async def generate_customer_description(
        self,
        query: str,
        products: List[NormalizedProduct],
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ) -> Tuple[str, bool, List[Dict[str, Any]]]:
        """
        Uses product name and short description as input for the configured OpenAI LLM
        to generate a concise, grounded customer-facing recommendation of exactly 2-3 lines.
        Guarantees:
        - Result rules: 1 match -> show 1; 2-4 matches -> show all; >4 matches -> show top 3.
        - Uses the Excel Short Description column as the source for each product description.
        - Generates a concise, user-friendly description of exactly 2–3 lines using the LLM, grounded only in that short description.
        - Each result has: product name, short description, valid INR price, and product URL.
        - Formats as clickable product cards without raw URLs or status.
        - Never uses Long Description HTML or invents benefits, rituals, or product details.
        - If source short description is missing, keeps description minimal and factual rather than hallucinating.
        - Never shows dates or non-INR prices. Never claims purchasability.
        - Returns (response_text, is_mock, sources)
        """
        if not products:
            no_match_text = (
                "Namaste. I could not find a matching AstroVed catalog item for your request. "
                "For customized remedial recommendations, temple rituals, or personalized chart analysis, "
                "our live astrology advisors would be glad to assist you. Would you like me to connect you with an advisor?"
            )
            return no_match_text, True, []

        target_products = apply_result_rules(products)

        sources = [
            {
                "title": p.product_name,
                "source": p.url,
                "document_id": p.product_id,
                "price": p.formatted_price
            }
            for p in target_products
        ]

        key = (api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")).strip()
        target_model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        # If OpenAI is offline / not configured, use graceful offline template
        if not key:
            return self.format_offline_response(query, target_products), True, sources

        try:
            import httpx

            # Treat spreadsheet content as strictly untrusted reference data
            products_context = []
            for i, p in enumerate(target_products, 1):
                clean_desc = re.sub(r"<[^>]+>", "", p.short_description or "").strip()
                clean_desc = strip_dates(clean_desc)
                desc_line = (
                    f"Short Description (Source): {clean_desc}"
                    if clean_desc
                    else "Short Description (Source): (Missing in catalog - keep description minimal and factual)"
                )
                price_line = f"Price: {p.formatted_price}" if p.formatted_price else "Price: (Omit price - not listed)"
                status_line = f"Status: {p.product_status}"
                products_context.append(
                    f"Product #{i}:\n"
                    f"Product Name: {p.product_name}\n"
                    f"{desc_line}\n"
                    f"{price_line}\n"
                    f"{status_line}\n"
                    f"Product URL: {p.url}"
                )

            context_str = "\n\n".join(products_context)

            system_prompt = (
                "You are AstroVed AI, presenting AstroVed catalog product recommendations to a seeker.\n"
                "You must present the catalog products provided under CATALOG PRODUCTS below according to these rules:\n"
                "1. Present the catalog products provided under CATALOG PRODUCTS below in the order listed (these items are verified matches from the AstroVed catalog).\n"
                "2. For each product, output EXACTLY this clean card format:\n"
                ":::product_card\n"
                "name: <Exact product name from catalog>\n"
                "price: <Valid INR price ONLY if provided in context, e.g. ₹530; omit line if not listed>\n"
                "description: <Concise, user-friendly description of exactly 2–3 lines, grounded ONLY in that product's provided Short Description from the Excel catalog>\n"
                "url: <Product URL provided>\n"
                ":::\n"
                "3. CRITICAL: Do NOT include product headings (like ###), labels like 'Product Name:', or raw URLs outside the card.\n"
                "4. Do NOT show product status (Active/Disabled).\n"
                "5. Absolutely NO generic ritual steps, DIY instructions, ritual materials/items, mantra lists, gemstone advice, or lengthy astrology explanations.\n"
                "6. DO NOT show dates (such as calendar dates or years) or non-INR prices.\n"
                "7. Never claim any product is currently purchasable, in stock, or that links are verified.\n"
                "8. Do not invent products, prices, inclusions, or availability."
            )

            user_prompt = (
                f"Seeker's question: \"{query}\"\n\n"
                f"=== CATALOG PRODUCTS ===\n"
                f"{context_str}\n"
                f"=== END CATALOG PRODUCTS ==="
            )

            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": target_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 500
                    }
                )

                if res.status_code == 200:
                    data = res.json()
                    answer = data["choices"][0]["message"]["content"]
                    return answer, False, sources
                else:
                    logger.warning("OpenAI returned status %d for catalog description; falling back gracefully.", res.status_code)
                    return self.format_offline_response(query, products[:3]), True, sources

        except Exception as err:
            logger.warning("Error generating LLM catalog description: %s; falling back gracefully.", err)
            return self.format_offline_response(query, products[:3]), True, sources


# Global singleton instance
catalog_service = CatalogService()
