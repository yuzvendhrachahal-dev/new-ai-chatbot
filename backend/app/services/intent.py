"""
AstroVed Chatbot Handoff Intent Detection Service.
Detects customer requests for human assistance, payments, refunds, bookings,
puja services, complaints, and technical support while guarding against
astrological false positives.
"""

import re
from typing import Tuple, Optional, Dict, List

# Standardized Issue Categories
CATEGORY_HUMAN = "Live Advisor Request"
CATEGORY_PAYMENT = "Payment & Billing Issue"
CATEGORY_ORDER = "Order & Booking Support"
CATEGORY_REFUND = "Refund & Cancellation"
CATEGORY_PUJA = "Puja & Service Issue"
CATEGORY_COMPLAINT = "Complaint & Escalation"
CATEGORY_TECH = "Technical Support"

# Astrological context patterns that should NOT trigger support handoffs
ASTRO_CONTEXT_PATTERNS = [
    r"\bcancel(?:s|ing|led)?\s+(?:the\s+)?(?:dosha|debility|curse|effect|affliction|neecha)\b",
    r"\bneecha\s+bhanga\b",
    r"\bcancellation\s+of\s+debilitation\b",
    r"\bhuman\s+(?:birth|life|body|form|existence|soul|incarnation)\b",
    r"\bpayment\s+of\s+karmic\s+debt\b",
    r"\bkarmic\s+debt\b",
    r"\bkarma\b"
]

HANDOFF_RULES: Dict[str, List[str]] = {
    CATEGORY_PAYMENT: [
        r"^(?:💳\s*)?payment(?:\s+(?:issue|problem|failed|support))?[\s!.]*$",
        r"\bpayment\s*(?:failed|issue|error|problem|declined|not\s+working|stuck|pending|dispute)\b",
        r"\b(?:pay|pymnt|paymnt)\s*(?:failed|issue|error|declined)\b",
        r"\bmoney\s*(?:deducted|debited|lost|cut|taken)\b",
        r"\bcharged\s*(?:twice|double|again|extra|incorrectly|2\s*times)\b",
        r"\btransaction\s*(?:failed|declined|timed?\s*out|error|pending)\b",
        r"\brefund\s+payment\b",
        r"\b(?:card|credit\s*card|debit\s*card)\s*declined\b",
        r"\b(?:card|credit\s*card|debit\s*card)\s*(?:not\s*working|error|failed)\b",
        r"\b(?:upi|netbanking|gateway)\s*(?:error|failed|issue|declined|not\s*working|deducted)\b",
        r"\bupi\b",
        r"\bdouble\s*charge\b",
        r"\bpay(?:ment)?\s+deducted\s+but\s+not\s+(?:confirmed|booked|received)\b",
        r"\binvoice\b",
        r"\bbilling\b",
    ],
    CATEGORY_ORDER: [
        r"\border\s*(?:not\s*received|status|tracking|delay|problem|issue|pending)\b",
        r"\bbooking\s*(?:failed|confirmation|status|problem|issue|not\s*received|cancelled|canceled)\b",
        r"\bwhere\s+is\s+my\s*(?:order|booking|report|prasadam|product|delivery)\b",
        r"\btrack\s*(?:my\s*)?(?:order|booking|shipment)\b",
        r"\breschedule\b",
        r"\bcancel\s*booking\b",
        r"\bservice\s*(?:not\s*delivered|not\s*received)\b",
        r"\breport\s*not\s*received\b"
    ],
    CATEGORY_REFUND: [
        r"\b(?:want|need|request|claim|get)\s*(?:my\s*)?(?:a\s*)?refund\b",
        r"\brefund\b",
        r"\bmoney\s*back\b",
        r"\b(?:reversal|chargeback)\b",
        r"\bcancellation\b",
        r"\bcancel\s*(?:my\s*)?(?:order|booking|service|subscription|pooja|puja|homam|consultation|membership)\b",
        r"\bplease\s+cancel\b"
    ],
    CATEGORY_PUJA: [
        r"\bpuja\s*(?:not\s*performed|not\s*done|issue|delayed|problem)\b",
        r"\bpooja\s*(?:not\s*performed|not\s*done|issue|delayed|problem)\b",
        r"\bhomam\s*(?:issue|problem|not\s*performed|not\s*done|delayed)\b",
        r"\bservice\s*delayed\b",
        r"\bwrong\s*(?:service|puja|pooja|homam|report)\b",
        r"\b(?:priest|pandit|vadhyar|purohit)\s*(?:didn't|did\s*not|hasn't|has\s*not|never)\s*(?:arrive|come|join|call)\b",
        r"\bprasadam\s*(?:not\s*received|missing|delayed|damaged)\b",
        r"\bsankalpam\s*not\s*taken\b",
        r"\bpuja\s*video\s*not\s*received\b"
    ],
    CATEGORY_COMPLAINT: [
        r"\bcomplaint\b",
        r"\bgrievance\b",
        r"\bunresolved\b",
        r"\bnot\s+satisfied\b",
        r"\bproblem\s*(?:is\s*)?not\s*solved\b",
        r"\b(?:speak|talk)\s+to\s*(?:a\s*)?(?:manager|supervisor)\b",
        r"\bescalat(?:e|ion)\b",
        r"\bvery\s*bad\s*service\b",
        r"\bunhappy\s+with\s+(?:service|support|response)\b"
    ],
    CATEGORY_TECH: [
        r"\blogin\s*(?:issue|problem|error|failed|can't|cannot|unable)\b",
        r"\b(?:can't|cannot|unable\s+to)\s+log\s*in\b",
        r"\botp\s*(?:not\s*received|issue|problem|error|failed|delayed|missing)\b",
        r"\bwebsite\s*(?:error|crash|not\s*working|bug|down|issue)\b",
        r"\bapp\s*(?:not\s*working|crash(?:ing)?|bug|error|down)\b",
        r"\b(?:can't|cannot|unable\s+to)\s+book\b",
        r"\baccount\s*(?:locked|blocked|suspended|disabled)\b",
        r"\bpassword\s*reset\s*(?:failed|not\s*working)\b"
    ],
    CATEGORY_HUMAN: [
        r"^(?:🤝\s*)?(?:talk\s+to\s+human|talk\s+to\s+agent|talk\s+to\s+advisor|human\s+support)\b",
        r"\b(?:talk|speak)\s+(?:to|with)\s+(?:an?\s+)?(?:human|person|agent|advisor|representative|executive|operator|astrologer|someone|somebody|team)\b",
        r"\b(?:connect|transfer)\s+(?:me\s+)?to\s+(?:an?\s+)?(?:human|person|agent|advisor|representative|executive|operator|team|astrologer|someone)\b",
        r"\bconnect\s+me\b",
        r"\bcall\s+me\b",
        r"\bcontact\s+(?:your\s+)?team\b",
        r"\bcontact\s+(?:support|customer\s*care)\b",
        r"\bhow\s+(?:can|do)\s+i\s+(?:contact|reach|call)\s+(?:support|your\s+team|customer\s+care|someone)\b",
        r"\b(?:live\s*agent|customer\s*support|customer\s*care|representative)\b",
        r"\b(?:human\s*assistance|human\s*agent|human\s*help)\b",
        r"\b(?:talk\s*to\s*someone|speak\s*to\s*someone)\b",
        r"\bi\s*(?:want|need)\s*(?:to\s*speak\s*with|to\s*talk\s*to)?\s*(?:an?\s+)?(?:human|live\s*agent|advisor|representative|astrologer)\b",
        r"^(?:human|live\s*agent|advisor|representative|customer\s*support|customer\s*care)\b",
        r"\b(?:agent|human|representative|advisor)\s+please\b",
        r"\bplease\s+(?:connect|transfer)\s+me\b"
    ]
}

def detect_support_handoff_intent(text: str) -> Tuple[bool, Optional[str]]:
    """
    Evaluates customer input against support handoff rules.
    Returns (is_handoff_requested, issue_category).
    Guards against common astrological false positives.
    """
    if not text or not text.strip():
        return False, None

    cleaned = text.strip().lower()

    # Check for astrological context false positives
    for astro_pat in ASTRO_CONTEXT_PATTERNS:
        if re.search(astro_pat, cleaned, re.IGNORECASE):
            # If the user also explicitly asked to talk to a human/support, still allow it
            human_explicit = any(
                re.search(pat, cleaned, re.IGNORECASE) for pat in HANDOFF_RULES[CATEGORY_HUMAN]
            )
            if not human_explicit:
                return False, None

    # Check each category rules in priority order
    for category in [
        CATEGORY_PAYMENT,
        CATEGORY_ORDER,
        CATEGORY_REFUND,
        CATEGORY_PUJA,
        CATEGORY_COMPLAINT,
        CATEGORY_TECH,
        CATEGORY_HUMAN
    ]:
        patterns = HANDOFF_RULES[category]
        for pat in patterns:
            if re.search(pat, cleaned, re.IGNORECASE):
                return True, category

    return False, None


# Greeting, Thanks, and Casual Small Talk Patterns
GREETING_PATTERNS = [
    r"^(?:hi|hello|hey|hiya|howdy|namaste|namaskar|namaskaram|vanakkam|pranam)(?:[\s,]+(?:there|astroved|ai|guide|advisor|team|bot))?[\s!.]*$",
    r"^(?:good\s+(?:morning|afternoon|evening|day))(?:\s+(?:there|astroved|ai|team|all))?[\s!.]*$",
    r"^(?:greetings)(?:\s+(?:everyone|there|astroved))?[\s!.]*$",
    r"^(?:what'?s\s+up|sup|yo)[\s!.]*$",
]

THANKS_PATTERNS = [
    r"^(?:thanks|thank\s+you|thank\s+u|many\s+thanks|thx|ty)(?:[\s,]+(?:so\s+much|a\s+lot|very\s+much|astroved|team))?[\s!.]*$",
    r"^(?:dhanyavad(?:ah)?|shukriya|nandri)[\s!.]*$",
]

SMALL_TALK_PATTERNS = [
    r"^(?:(?:hi|hello|hey|namaste)[\s,]+)?(?:how\s+are\s+you(?:\s+doing)?|how'?s\s+it\s+going|how\s+do\s+you\s+do)[\s?.]*$",
    r"^(?:(?:hi|hello|hey|namaste)[\s,]+)?(?:who\s+are\s+you|what\s+can\s+you\s+do|what\s+is\s+your\s+name)[\s?.]*$",
]

def detect_greeting_intent(text: str, has_history: bool = False) -> Optional[str]:
    """
    Recognizes casual greetings, thanks, and small talk before RAG retrieval.
    Prevents repeating 'Welcome to AstroVed' on subsequent turns when has_history is True.
    Returns a warm, concise natural response or None if the query should proceed to RAG.
    """
    if not text or not text.strip():
        return None

    cleaned = text.strip().lower()

    # 1. Greetings (hi, hello, hey, good morning, etc.)
    for pat in GREETING_PATTERNS:
        if re.search(pat, cleaned, re.IGNORECASE):
            if has_history:
                if "morning" in cleaned:
                    return "Namaste! Good morning. How may I assist your Vedic astrology journey today?"
                if "evening" in cleaned:
                    return "Namaste! Good evening. How may I assist your Vedic astrology journey today?"
                if "afternoon" in cleaned:
                    return "Namaste! Good afternoon. How may I assist your Vedic astrology journey today?"
                return "Namaste! How may I assist your Vedic astrology journey today?"
            else:
                if "morning" in cleaned:
                    return "Namaste! Good morning and welcome to AstroVed. How can I help you today?"
                if "evening" in cleaned:
                    return "Namaste! Good evening and welcome to AstroVed. How can I help you today?"
                if "afternoon" in cleaned:
                    return "Namaste! Good afternoon and welcome to AstroVed. How can I help you today?"
                return "Namaste! Welcome to AstroVed. How can I help you today?"

    # 2. Gratitude (thanks, thank you, etc.)
    for pat in THANKS_PATTERNS:
        if re.search(pat, cleaned, re.IGNORECASE):
            return "You are most welcome! May cosmic blessings illuminate your path. How else can I assist you today?"

    # 3. Small talk (how are you, who are you, etc.)
    for pat in SMALL_TALK_PATTERNS:
        if re.search(pat, cleaned, re.IGNORECASE):
            if any(w in cleaned for w in ["who", "what can you do", "name"]):
                return "Namaste! I am AstroVed AI, your Vedic Astrology guide. I can help answer queries about your birth chart, planetary transits, dasha periods, and remedial pujas. How can I assist you today?"
            return "Namaste! I am doing well, guided by the cosmic rhythm. How can I assist your Vedic astrology journey today?"

    return None


def detect_birth_details_submission(text: str) -> bool:
    """
    Detects when a user is providing their birth coordinates (date, time, place)
    for chart calculation.
    """
    if not text or not text.strip():
        return False
    cleaned = text.strip().lower()

    has_dob_keyword = bool(re.search(r"\b(?:dob|date of birth|birth date|born on|birth details|my details|birth info|birth coordinates)\b", cleaned))
    has_tob_keyword = bool(re.search(r"\b(?:tob|time of birth|birth time|born at)\b", cleaned))
    has_pob_keyword = bool(re.search(r"\b(?:pob|place of birth|birth place|born in|birthplace)\b", cleaned))

    has_date_pattern = bool(
        re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", cleaned) or
        re.search(r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}\b", cleaned)
    )
    has_time_pattern = bool(re.search(r"\b\d{1,2}[:.]\d{2}\s*(?:am|pm)?\b", cleaned))

    if has_dob_keyword:
        return True
    if has_date_pattern and (has_time_pattern or has_tob_keyword or has_pob_keyword):
        return True

    return False


def is_horoscope_intent(text: str) -> bool:
    """
    Detects questions inquiring about horoscope or daily predictions:
    - Today's horoscope
    - Daily horoscope
    - Horoscope today
    - My daily prediction
    - Horoscope for my zodiac sign
    """
    if not text or not text.strip():
        return False
    cleaned = text.strip().lower()
    patterns = [
        r"\b(?:today'?s?\s+)?horoscope\b",
        r"\bhoroscope\s+today\b",
        r"\bdaily\s+horoscope\b",
        r"\b(?:my\s+)?daily\s+prediction\b",
        r"\bhoroscope\s+for\s+(?:my\s+)?(?:zodiac\s+)?sign\b",
        r"\b(?:aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|sagittarius|capricorn|aquarius|pisces)\s+horoscope\b"
    ]
    return any(re.search(pat, cleaned) for pat in patterns)


def detect_quick_action_intent(text: str) -> Optional[str]:
    """
    Intelligent routing using the complete URL catalogue (url_catalogue_service).
    Detects user intent and returns a clickable feature card or helpful response.
    Never returns Astropedia home or domain root for specific tool requests.
    Does not intercept ordinary informational astrology questions.
    """
    if not text or not text.strip():
        return None

    cleaned = text.strip()
    cleaned_lower = cleaned.lower()

    # Product recommendation queries (e.g. "suggest me a pooja", "recommend a gemstone", "lost my job, suggest a pooja")
    # must go to the product catalog service (Excel catalog) rather than static URL navigation.
    is_product_recommendation = any(
        w in cleaned_lower for w in ["suggest", "recommend", "show me offerings", "buy", "purchase", "order"]
    ) or "lost my job" in cleaned_lower
    if is_product_recommendation:
        return None

    # Rule 5: Do not let URL routing intercept ordinary informational questions
    informational_prefixes = (
        "what is", "what are", "what does", "what do", "what can", "what will", "what would",
        "why is", "why are", "why does", "why do", "why would",
        "explain", "tell me about", "meaning of", "can you explain", "could you explain",
        "how does", "how do", "how is", "how can", "how will", "difference between",
        "which house", "which planet", "which rashi", "which sign",
        "who is", "when does", "when will", "where is"
    )
    if any(cleaned_lower.startswith(p) for p in informational_prefixes):
        # Allow pure knowledge/conversational flow to handle
        return None

    if any(k in cleaned_lower for k in ["10th house", "karma bhava", "7th house", "1st house", "12th house", "exalted venus"]):
        return None

    # Remedies overview query
    if re.search(r"^(?:🌿\s*)?remedies\b", cleaned_lower) or cleaned_lower in ["remedies", "vedic remedies"]:
        return (
            "Namaste! Vedic remedies (Upayas) harmonize planetary energies and alleviate karmic doshas. Here are key remedy categories:\n\n"
            "1. **Planetary & Dosha Remedies:** Offerings for Saturn (Sade Sati/Shani), Rahu-Ketu, and Kuja/Manglik doshas.\n"
            "2. **Career & Financial Remedies:** Pujas and homams dedicated to Ganesha and Lakshmi for success and prosperity.\n"
            "3. **Love & Relationship Remedies:** Sacred rituals to resolve conflicts, overcome delays, and restore harmony.\n"
            "4. **Health & Longevity Remedies:** Ayush and Mrityunjaya homams for vitality and healing.\n\n"
            "You can also ask directly for specific offerings, such as *'suggest me a saturn ritual'*, *'suggest me love pooja'*, or *'recommend a gemstone'*."
        )

    # Check complete URL catalogue for service/tool intent
    from app.services.url_catalogue import url_catalogue_service

    match = url_catalogue_service.search(cleaned)

    # Multi-intent: user requested both an available feature and a missing service (e.g. horoscope + birth chart)
    if match.entry and match.missing_service_msg:
        partner_context = ""
        if "horoscope-matching" in match.entry.url:
            partner_context = "For Vedic Kundli matching to assess marital harmony between Partner 1 and Partner 2:\n\n"
        return (
            f"Namaste! {partner_context}Here is the official AstroVed destination for your request:\n\n"
            f"{url_catalogue_service.format_feature_card(match.entry)}\n\n"
            f"**Regarding your Free Birth Chart request:**\n"
            f"{match.missing_service_msg}"
        )

    if match.missing_service_msg:
        return match.missing_service_msg

    if match.is_ambiguous and match.clarification_prompt:
        return match.clarification_prompt

    if match.entry and match.confidence >= 0.40:
        entry = match.entry
        # If user explicitly asks for compatibility matching, mention partner 1 & 2 context
        partner_context = ""
        if "horoscope-matching" in entry.url:
            partner_context = "For Vedic Kundli matching to assess marital harmony between Partner 1 and Partner 2:\n\n"

        return (
            f"Namaste! {partner_context}Here is the official AstroVed destination for your request:\n\n"
            f"{url_catalogue_service.format_feature_card(entry)}"
        )

    return None


# Category Keywords Map for Intent & Category Classification
CATEGORY_PATTERNS = {
    "career": [
        r"\b(?:career|job|jobs|employment|profession|business|workplace|promotion|unemployed|unemployment)\b",
        r"\b(?:lost\s+my\s+job|lost\s+job|job\s+loss|fired|laid\s+off|jobless)\b",
        r"\b(?:work|profession|vocation|office|corporate)\b",
    ],
    "love_relationship": [
        r"\b(?:love|romance|relationship|relationships|marriage|marital|partner|spouse|husband|wife|dating)\b",
        r"\b(?:breakup|divorce|separation|kundli\s*milan|gun\s*milan|soulmate)\b",
    ],
    "saturn_shani": [
        r"\b(?:saturn|shani|sani|sade\s*sati|saniswaran|shaniswara|shanidev|kantaka\s*shani|ashtama\s*shani)\b",
    ],
    "wealth": [
        r"\b(?:wealth|money|financial|finances|prosperity|debt|loans|poverty|cash\s*flow|rich|income)\b",
        r"\b(?:lakshmi|kubera)\b",
    ],
    "health": [
        r"\b(?:health|illness|disease|vitality|healing|longevity|recovery|ayush|mrityunjaya|dhanvantari)\b",
    ],
    "dosha": [
        r"\b(?:dosha|doshas|mangal\s*dosha|kuja\s*dosha|kaal\s*sarp|rahu|ketu|pitru\s*dosha|nadi\s*dosha)\b",
    ],
    "gemstone": [
        r"\b(?:gemstones?|ratna|ruby|emerald|yellow\s*sapphire|blue\s*sapphire|pukhraj|neelam|manikya|panna)\b",
    ]
}

OFF_TOPIC_PATTERNS = [
    r"\b(?:code|python|javascript|java|c\+\+|programming|software|debug|script|compile)\b",
    r"\b(?:car\s+repair|mechanic|flat\s+tire|bicycle|engine|oil\s+change|brake\s+pads)\b",
    r"\b(?:football|soccer|basketball|cricket\s+score|nba|fifa|olympics)\b",
    r"\b(?:pizza\s+recipe|bake\s+cake|cooking\s+recipe|cocktail|ingredients)\b",
    r"\b(?:geopolitics|election\s+poll|presidential\s+debate|war\s+news|stock\s+market\s+ticker)\b",
    r"\b(?:solve\s+math|calculus|algebra|physics\s+homework)\b",
]

def classify_user_intent_and_category(query: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Classifies user message into intent, category, and concern:
    - Intent: 'greeting' | 'support_handoff' | 'quick_action' | 'product_recommendation' | 'astrology_knowledge' | 'off_topic'
    - Category: 'career' | 'love_relationship' | 'saturn_shani' | 'wealth' | 'health' | 'dosha' | 'gemstone' | 'general_astrology' | 'off_topic'
    - Concern: summary of seeker's underlying concern
    """
    if not query or not query.strip():
        return {"intent": "greeting", "category": "conversational", "concern": ""}

    cleaned = query.strip().lower()

    # 1. Support Handoff Check
    is_handoff, handoff_category = detect_support_handoff_intent(query)
    if is_handoff:
        return {
            "intent": "support_handoff",
            "category": handoff_category or CATEGORY_HUMAN,
            "concern": handoff_category or "Support Request"
        }

    # 2. Greeting / Gratitude / Small Talk Check
    greeting = detect_greeting_intent(query)
    if greeting is not None:
        return {
            "intent": "greeting",
            "category": "conversational",
            "concern": ""
        }

    # 3. Quick Action Check
    quick_action = detect_quick_action_intent(query)
    if quick_action is not None:
        return {
            "intent": "quick_action",
            "category": "quick_action",
            "concern": cleaned
        }

    # 4. Off-topic check (guards against software, car repair, sports, recipes, etc.)
    for off_pat in OFF_TOPIC_PATTERNS:
        if re.search(off_pat, cleaned, re.IGNORECASE):
            return {
                "intent": "off_topic",
                "category": "off_topic",
                "concern": cleaned
            }

    # 5. Extract category
    detected_category = "general_astrology"
    for cat_name, patterns in CATEGORY_PATTERNS.items():
        if any(re.search(p, cleaned, re.IGNORECASE) for p in patterns):
            detected_category = cat_name
            break

    # 6. Extract recommendation intent vs astrology knowledge
    recommendation_cues = [
        r"\b(?:suggest|recommend|recommendation|suggestion|find|show\s+me|give\s+me|options\s+for)\b",
        r"\b(?:buy|purchase|order|book|booking|cost|price|fee|inr)\b",
        r"\b(?:which\s+pooja|what\s+pooja|which\s+ritual|what\s+ritual|which\s+gemstone)\b",
        r"\b(?:love\s+pooja|saturn\s+ritual|saturn\s+pooja|shani\s+ritual)\b",
        r"\b(?:lost\s+my\s+job|lost\s+job|unemployed)\b"
    ]
    is_recommendation = any(re.search(cue, cleaned, re.IGNORECASE) for cue in recommendation_cues)

    # Conceptual astrology queries should remain 'astrology_knowledge'
    is_conceptual = any(
        cleaned.startswith(p) for p in [
            "what is ", "what are ", "what does ", "explain ", "meaning of ", "who is ", "difference between ", "tell me about "
        ]
    ) and not any(w in cleaned for w in ["suggest", "recommend", "buy", "book", "cost", "price", "show me"])

    if is_recommendation and not is_conceptual:
        intent = "product_recommendation"
    else:
        intent = "astrology_knowledge"

    # Extract concern
    concern = cleaned
    if "lost my job" in cleaned or "lost job" in cleaned:
        concern = "job loss and career obstacles"
    elif "love" in cleaned or "relationship" in cleaned:
        concern = "love and relationship harmony"
    elif "saturn" in cleaned or "shani" in cleaned or "sade sati" in cleaned:
        concern = "Saturn transit and Sade Sati relief"

    return {
        "intent": intent,
        "category": detected_category,
        "concern": concern
    }

