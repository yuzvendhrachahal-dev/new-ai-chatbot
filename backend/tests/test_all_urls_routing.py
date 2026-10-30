"""
Comprehensive test suite verifying intelligent URL mapping covering ALL AstroVed services in data/all_urls.txt.
Verifies:
1. Intent detection accuracy across diverse categories.
2. Exact page-level match selection (never domain homepage or Astropedia home base URL).
3. Returned URLs exist in data/all_urls.txt.
4. Handling of paraphrased queries, common spelling mistakes/transliterations.
5. Detection of ambiguous requests with polite clarification prompts.
6. Graceful handling of queries for services not in all_urls.txt (e.g. Free Birth Chart, Panchang, Muhurta)
   offering human support / live astrologer consultation without redirecting to unrelated pages.
7. Informational queries are not hijacked by URL routing (Rule 5).
"""

import pytest
from app.services.url_catalogue import url_catalogue_service, URLMatchResult
from app.services.intent import detect_quick_action_intent
from app.services.llm import llm_service


@pytest.fixture(scope="module")
def verified_urls():
    """Set of all verified URLs in data/all_urls.txt."""
    return url_catalogue_service.get_all_verified_urls()


# Test set of >= 25 distinct queries across categories available in all_urls.txt
CORE_CATEGORY_TESTS = [
    # 1. Horoscope
    ("Today's horoscope", "https://www.astroved.com/horoscope/", "horoscope"),
    ("Daily horoscope prediction", "https://www.astroved.com/horoscope/", "horoscope"),
    ("Monthly horoscope predictions", "https://www.astroved.com/horoscope/monthly/", "horoscope"),
    ("Aries love horoscope today", "https://www.astroved.com/horoscope/daily-love-horoscope/aries-love-horoscope-today", "horoscope"),
    
    # 2. Free Tools
    ("Marriage matching", "https://www.astroved.com/astropedia/en/freetools/horoscope-matching", "free_tool"),
    ("Kundli matching for marriage", "https://www.astroved.com/astropedia/en/freetools/horoscope-matching", "free_tool"),
    ("Numerology report", "https://www.astroved.com/astropedia/en/freetools/numerology", "free_tool"),
    ("Name numerology calculator", "https://www.astroved.com/astropedia/en/freetools/numerology", "free_tool"),
    ("Sade Sati calculator", "https://www.astroved.com/astropedia/en/freetools/sade-sati", "free_tool"),
    
    # 3. Compatibility
    ("Love compatibility", "https://www.astroved.com/zodiac-signs/compatibility", "compatibility"),
    ("Aquarius and Gemini compatibility", "https://www.astroved.com/zodiac-signs/compatibility/aquarius-gemini", "compatibility"),
    
    # 4. Dosha Remedies
    ("Guru Chandal dosh remedies", "https://www.astroved.com/dosha-pariharam/chandal-dosh-remedies", "dosha_remedy"),
    ("Grahan dosh remedies", "https://www.astroved.com/dosha-pariharam/grahan-dosh-remedies", "dosha_remedy"),
    ("Kalathra dosha remedies", "https://www.astroved.com/dosha-pariharam/kalathra-dosha-remedies", "dosha_remedy"),
    ("Shrapit dosha remedies", "https://www.astroved.com/dosha-pariharam/shrapit-dosha-remedies", "dosha_remedy"),
    
    # 5. Remedies / Fire Labs / Homas / Tarpanam
    ("Saturn remedies homa", "https://www.astroved.com/planetary-fire-lab-saturn-fire-lab-saturn-planetary-blessings-homa--P56.aspx", "remedy_ritual"),
    ("Ganesha homa for removing obstacles", "https://www.astroved.com/archetype-deity-fire-lab-ganesha-fire-lab-homa-for-obstacle-removal-and-success--P64.aspx", "remedy_ritual"),
    ("Lakshmi fire lab for financial prosperity", "https://www.astroved.com/archetype-deity-fire-lab-lakshmi-fire-lab-homa-for-material-wealth-and-abundance--P60.aspx", "remedy_ritual"),
    ("Kala Bhairava fire lab for good time management", "https://www.astroved.com/archetype-deity-fire-lab-kala-bhairava-fire-lab-homa-for-good-time-management-and-financial-status--P69.aspx", "remedy_ritual"),
    ("Amavasya tarpanam for ancestors", "https://www.astroved.com/amavasya-tarpanam-P48298.aspx", "remedy_ritual"),
    
    # 6. Astrologer Consultations (AstroVed Speaks)
    ("Career astrology consultation", "https://www.astroved.com/astrovedspeaks/astrologer/career", "consultation"),
    ("Chat with astrologer online", "https://www.astroved.com/astrovedspeaks/chat-with-astrologer", "consultation"),
    ("Talk to astrologer on call", "https://www.astroved.com/astrovedspeaks/talk-to-astrologer", "consultation"),
    ("Best astrologers in Bangalore", "https://www.astroved.com/astrovedspeaks/best-astrologers-in-bangalore", "consultation"),
    
    # 7. Nadi Astrology
    ("Nadi leaf reading", "https://www.astroved.com/nadi/nadi-leaf-reading", "nadi_astrology"),
    ("Nadi astrology overview", "https://www.astroved.com/nadi/nadi-astrology", "nadi_astrology"),
    
    # 8. Nakshatras & Virtual Poojas & Festivals
    ("Ashwini nakshatra remedies", "https://www.astroved.com/astropedia/en/nakshatra/ashwini-nakshatra", "nakshatra"),
    ("Virtual Ganesh pooja", "https://www.astroved.com/astropedia/en/virtual-pooja/ganesh-pooja", "virtual_pooja"),
    ("Pradosham fasting dates", "https://www.astroved.com/astropedia/en/festivals/pradosham", "festivals")
]


@pytest.mark.parametrize("query,expected_url,expected_cat", CORE_CATEGORY_TESTS)
def test_core_category_url_routing(query, expected_url, expected_cat, verified_urls):
    """Verifies intent detection and exact URL matching across core categories."""
    result = url_catalogue_service.search(query)
    
    assert result is not None
    assert result.entry is not None, f"Expected match for query: '{query}', got None"
    assert result.entry.url == expected_url, f"Query '{query}' expected '{expected_url}', got '{result.entry.url}'"
    assert result.entry.url in verified_urls, f"Returned URL '{result.entry.url}' is not in all_urls.txt"
    assert result.entry.category == expected_cat, f"Query '{query}' expected category '{expected_cat}', got '{result.entry.category}'"
    assert result.confidence >= 0.40, f"Confidence {result.confidence} was below 0.40 threshold for '{query}'"
    
    # Negative test: Never return generic homepage or Astropedia base hub
    assert result.entry.url != "https://www.astroved.com"
    assert result.entry.url != "https://www.astroved.com/astropedia/en/home"
    assert not result.entry.is_generic


def test_paraphrased_and_typo_queries(verified_urls):
    """Verifies that spelling mistakes and colloquial paraphrasing route accurately."""
    typo_tests = [
        ("horoscpe for today", "https://www.astroved.com/horoscope/"),
        ("numrology calculation", "https://www.astroved.com/astropedia/en/freetools/numerology"),
        ("check kundli milan for wedding", "https://www.astroved.com/astropedia/en/freetools/horoscope-matching"),
        ("sani homa remedies", "https://www.astroved.com/planetary-fire-lab-saturn-fire-lab-saturn-planetary-blessings-homa--P56.aspx"),
        ("daily prediciton horoscope", "https://www.astroved.com/horoscope/")
    ]
    for query, expected_url in typo_tests:
        result = url_catalogue_service.search(query)
        assert result.entry is not None, f"Failed on typo query: '{query}'"
        assert result.entry.url == expected_url
        assert result.entry.url in verified_urls


def test_missing_services_handled_gracefully_without_astropedia_home():
    """
    Verifies that requests for services not in all_urls.txt (Free Birth Chart, Panchang, Muhurta)
    do NOT return Astropedia base URL (https://www.astroved.com/astropedia/en/home),
    do NOT invent URLs, and offer helpful responses with human support.
    """
    missing_queries = [
        "Free birth chart / Generate Kundli",
        "calculate my birth chart",
        "Generate Kundli online",
        "Panchang today",
        "Muhurta calculation service"
    ]

    for q in missing_queries:
        result = url_catalogue_service.search(q)
        assert result.entry is None, f"Query '{q}' should not return a fake page"
        assert result.missing_service_msg is not None
        assert "https://www.astroved.com/astropedia/en/home" not in result.missing_service_msg
        assert "support" in result.missing_service_msg.lower() or "astrologers" in result.missing_service_msg.lower()

        # Check intent level response
        resp = detect_quick_action_intent(q)
        assert resp is not None
        assert "https://www.astroved.com/astropedia/en/home" not in resp


def test_ambiguity_triggers_clarification():
    """
    Verifies that broad/ambiguous requests trigger a clarification question
    rather than arbitrarily picking one option.
    """
    ambiguous_query = "Dosha remedies"
    result = url_catalogue_service.search(ambiguous_query)
    
    assert result.is_ambiguous is True
    assert result.clarification_prompt is not None
    assert "Which one would you like to explore?" in result.clarification_prompt
    assert len(result.candidate_options) >= 2


def test_ordinary_informational_questions_not_intercepted():
    """
    Rule 5: URL routing must NOT intercept ordinary informational questions.
    """
    info_questions = [
        "What is Rahu Kalam?",
        "Why does Saturn cause delays in life?",
        "Explain the significance of Jupiter transit",
        "Tell me about the 7th house in Vedic astrology"
    ]

    for q in info_questions:
        resp = detect_quick_action_intent(q)
        assert resp is None, f"Informational question '{q}' was incorrectly intercepted by URL router"


@pytest.mark.asyncio
async def test_feature_card_ui_format():
    """
    Verifies feature card layout:
    - Page/service name as normal text
    - 2-line description
    - One clear action button
    - URL in all_urls.txt
    """
    reply, is_mock, sources = await llm_service.get_response("Today's horoscope")
    assert reply is not None
    assert ":::feature_card" in reply
    assert "title: Today's Horoscope" in reply
    assert "description:" in reply
    assert "button: View Today's Horoscope" in reply
    assert "url: https://www.astroved.com/horoscope/" in reply
    assert "https://www.astroved.com/astropedia/en/home" not in reply


def test_negative_distractor_queries_rejected_across_all_categories():
    """
    Negative audit test across categories:
    Unrelated, off-topic, or non-astrological distractor queries must NEVER receive a feature URL.
    """
    unrelated_queries = [
        "weather forecast in London",
        "daily commute route",
        "match stick box",
        "fire extinguisher price",
        "lab coat size",
        "overview of modern economics",
        "reading glasses discount",
        "dates nutrition facts",
        "star wars movie cast",
        "recipe for chocolate cake",
        "loan EMI calculator excel",
        "bluetooth device pairing compatibility",
        "side effects of paracetamol medication",
        "legal consultation for contract dispute",
        "palm tree gardening tips",
        "virtual reality gaming headset",
        "film festival tickets booking",
        "hotel near Grand Canyon",
        "catholic church sunday mass timings",
        "domain name generator for startup"
    ]
    for q in unrelated_queries:
        res = url_catalogue_service.search(q)
        assert res.entry is None, f"Unrelated query '{q}' incorrectly matched URL: {res.entry.url}"
        assert res.confidence == 0.0


@pytest.mark.asyncio
async def test_multi_intent_query_routing():
    """
    Verifies multi-intent query handling:
    e.g. 'I want to check my birth chart and today's horoscope'
    - Routes to the available feature card (Today's Horoscope)
    - Concurrently addresses the Free Birth Chart request honestly
    - Never returns generic Astropedia home
    """
    multi_query = "I want to check my birth chart and today's horoscope"
    reply, is_mock, sources = await llm_service.get_response(multi_query)
    assert reply is not None
    assert ":::feature_card" in reply
    assert "url: https://www.astroved.com/horoscope/" in reply
    assert "https://www.astroved.com/astropedia/en/home" not in reply
    assert "birth chart" in reply.lower()
    assert "astrovedspeaks" in reply.lower() or "support" in reply.lower()


@pytest.mark.asyncio
async def test_real_chat_api_routing_flow():
    """
    Verifies the end-to-end HTTP API (/api/v1/chat/start and /api/v1/chat/send)
    with representative queries across categories.
    """
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.config import settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Start chat
        start_res = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Audit Seeker",
            "email": "audit@example.com",
            "mobile": "+919123456789"
        })
        assert start_res.status_code == 200
        conv_id = start_res.json()["conversation_id"]

        # 2. Test Horoscope tool routing
        send_horo = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "Today's horoscope"
        })
        assert send_horo.status_code == 200
        reply_horo = send_horo.json()["reply"]["text"]
        assert ":::feature_card" in reply_horo
        assert "url: https://www.astroved.com/horoscope/" in reply_horo

        # 3. Test Free tool (Sade Sati calculator)
        send_sade = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "Sade Sati calculator"
        })
        assert send_sade.status_code == 200
        reply_sade = send_sade.json()["reply"]["text"]
        assert "url: https://www.astroved.com/astropedia/en/freetools/sade-sati" in reply_sade

        # 4. Test Missing Service (Birth Chart)
        send_bc = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "Free birth chart"
        })
        assert send_bc.status_code == 200
        reply_bc = send_bc.json()["reply"]["text"]
        assert "https://www.astroved.com/astropedia/en/home" not in reply_bc
        assert "astrovedspeaks" in reply_bc.lower() or "support" in reply_bc.lower()

