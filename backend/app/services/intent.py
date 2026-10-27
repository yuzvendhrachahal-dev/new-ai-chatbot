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
        r"\b(?:talk|speak)\s+(?:to|with)\s+(?:a\s+)?(?:human|person|agent|advisor|representative|executive|operator|someone|somebody|team)\b",
        r"\b(?:connect|transfer)\s+(?:me\s+)?to\s+(?:a\s+)?(?:human|person|agent|advisor|representative|executive|operator|team|astrologer|someone)\b",
        r"\bconnect\s+me\b",
        r"\bcall\s+me\b",
        r"\bcontact\s+(?:your\s+)?team\b",
        r"\bcontact\s+(?:support|customer\s*care)\b",
        r"\bhow\s+(?:can|do)\s+i\s+(?:contact|reach|call)\s+(?:support|your\s+team|customer\s+care|someone)\b",
        r"\b(?:live\s*agent|customer\s*support|customer\s*care|representative)\b",
        r"\b(?:human\s*assistance|human\s*agent|human\s*help)\b",
        r"\b(?:talk\s*to\s*someone|speak\s*to\s*someone)\b",
        r"\bi\s*(?:want|need)\s*(?:to\s*speak\s*with|to\s*talk\s*to)?\s*(?:a\s*)?(?:human|live\s*agent|advisor|representative)\b",
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

def detect_greeting_intent(text: str) -> Optional[str]:
    """
    Recognizes casual greetings, thanks, and small talk before RAG retrieval.
    Returns a warm, concise natural response or None if the query should proceed to RAG.
    """
    if not text or not text.strip():
        return None

    cleaned = text.strip().lower()

    # 1. Greetings (hi, hello, hey, good morning, etc.)
    for pat in GREETING_PATTERNS:
        if re.search(pat, cleaned, re.IGNORECASE):
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
