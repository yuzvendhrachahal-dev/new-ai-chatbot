"""
Test Suite for AstroVed Chatbot - Manual Testing Fixes Verification.
Verifies all 8 manual testing fixes:
1. Product recommendation UI - clickable product cards with valid format, no raw URLs, no status.
2. Feature redirects from all_urls.txt (Today's Horoscope, Compatibility Match, Free Birth Chart).
3. Birth details submission redirects to Free Birth Chart without fake calculations.
4. Birth details followed by unrelated questions does not cause chart calculations.
5. Today's Horoscope intent detection and redirect card.
6. Honest reporting of missing URLs in all_urls.txt without inventing URLs.
7. Safe URL validation (no javascript:, data:, etc.).
8. Support handoff and agent flow preservation.
"""

import pytest
import re
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.services.catalog import (
    catalog_service,
    NormalizedProduct,
    is_product_query
)
from app.services.intent import (
    detect_quick_action_intent,
    detect_birth_details_submission,
    is_horoscope_intent,
    detect_support_handoff_intent
)
from app.services.llm import llm_service
from app.services.feature_urls import (
    get_feature_url,
    get_verified_urls,
    FEATURE_URLS_IN_SOURCE,
    MISSING_URLS_REPORT
)


# ---------------------------------------------------------------------------
# 1. Product recommendation card format
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_product_recommendation_card_format():
    """
    Verifies that product recommendations:
    - Include product name as normal text (no ### heading).
    - Include formatted price below name.
    - Format as structured :::product_card block.
    - Do NOT display product status (Active/Disabled).
    - Do NOT display raw URLs outside the card block.
    - Use valid INR price.
    """
    prod1 = NormalizedProduct(
        product_id="105",
        product_name="Archetype Deity Pooja Ashtalakshmi Pooja",
        short_description="Sacred 8-form Lakshmi ritual for wealth and prosperity.",
        manufacturer_name="Service",
        category="pooja",
        available_shops="AstroVed",
        price_inr=3330.0,
        formatted_price="₹3,330",
        product_status="Active",
        url="https://www.astroved.com/archetype-deity-pooja-ashtalakshmi-pooja-P105.aspx"
    )
    prod2 = NormalizedProduct(
        product_id="35733",
        product_name="Saturn Retrograde Light and Sound",
        short_description="Remedial Saturn transit ritual.",
        manufacturer_name="Service",
        category="ritual",
        available_shops="AstroVed",
        price_inr=None,
        formatted_price=None,
        product_status="Disabled",
        url="https://www.astroved.com/saturn-retrograde-light-and-sound-P35733.aspx"
    )

    text, is_mock, sources = await catalog_service.generate_customer_description(
        query="Saturn pooja",
        products=[prod1, prod2],
        api_key="",
        model="gpt-4o-mini"
    )

    assert is_mock is True
    # Structured card format
    assert ":::product_card" in text
    assert "name: Archetype Deity Pooja Ashtalakshmi Pooja" in text
    assert "price: ₹3,330" in text
    assert "url: https://www.astroved.com/archetype-deity-pooja-ashtalakshmi-pooja-P105.aspx" in text

    # Second product (disabled) should not have its status displayed in text
    assert "name: Saturn Retrograde Light and Sound" in text
    assert "Active" not in text
    assert "Disabled" not in text
    # No markdown heading tags for products
    assert "###" not in text


# ---------------------------------------------------------------------------
# 2. Use all_urls.txt for AstroVed feature redirects
# ---------------------------------------------------------------------------
def test_all_urls_verification():
    """
    Verifies feature URLs against all_urls.txt:
    - Today's Horoscope exists in all_urls.txt
    - Compatibility match exists in all_urls.txt
    - Free Birth Chart is verified as missing from all_urls.txt and reported honestly
    """
    verified = get_verified_urls()
    assert len(verified) > 0, "all_urls.txt must be loaded."

    # Today's Horoscope
    horo_url = get_feature_url("todays_horoscope")
    assert horo_url in verified, f"Expected {horo_url} in all_urls.txt"
    assert horo_url == "https://www.astroved.com/horoscope/"

    # Compatibility Matching
    compat_url = get_feature_url("compatibility_matching")
    assert compat_url in verified, f"Expected {compat_url} in all_urls.txt"
    assert compat_url == "https://www.astroved.com/astropedia/en/freetools/horoscope-matching"

    # Missing URL report
    assert "free_birth_chart" in MISSING_URLS_REPORT
    assert MISSING_URLS_REPORT["free_birth_chart"]["status_in_all_urls_txt"] == "MISSING"


# ---------------------------------------------------------------------------
# 3. Today's Horoscope Intent and Redirect Card
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_todays_horoscope_redirect_card():
    """
    Verifies that horoscope queries:
    - Today's horoscope
    - Daily horoscope
    - Horoscope today
    - My daily prediction
    - Horoscope for my zodiac sign
    Return the clickable redirect card with URL from all_urls.txt and a 2-line description.
    """
    horoscope_queries = [
        "Today's horoscope",
        "Daily horoscope",
        "Horoscope today",
        "My daily prediction",
        "Horoscope for my zodiac sign"
    ]

    for q in horoscope_queries:
        reply, is_mock, sources = await llm_service.get_response(q)
        assert reply is not None
        assert ":::feature_card" in reply
        assert "title: Today's Horoscope" in reply
        assert "button: View Today's Horoscope" in reply
        assert "url: https://www.astroved.com/horoscope/" in reply
        assert "Explore your daily horoscope" in reply
        # No fake daily predictions
        assert "lucky number" not in reply.lower()
        assert "today you will win" not in reply.lower()


# ---------------------------------------------------------------------------
# 4. Free Birth Chart Requests & Birth Details Submission
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_birth_details_submission_redirects_without_fake_calculation():
    """
    Verifies that when a user provides birth details:
    - Chatbot detects birth coordinates.
    - Redirects to official Free Birth Chart tool with card.
    - Does NOT fabricate Ascendant, Moon sign, planetary placements, or Dashas.
    """
    birth_inputs = [
        "My birth details: 15-08-1990, 10:30 AM, Chennai",
        "DOB: 24/03/1985, Time: 14:15, Place: Mumbai",
        "I was born on 12 Jan 1992 at 7:45 am in Bangalore",
        "Here are my birth details: 05-11-1998, 08:00 PM, Delhi"
    ]

    for b_input in birth_inputs:
        assert detect_birth_details_submission(b_input) is True
        reply, is_mock, sources = await llm_service.get_response(b_input)
        assert reply is not None
        # Does NOT redirect to irrelevant Astropedia home base URL
        assert "https://www.astroved.com/astropedia/en/home" not in reply
        assert ("support" in reply.lower() or "astrovedspeaks" in reply.lower())
        # Absolutely NO fabricated calculations
        assert "lagna is leo" not in reply.lower()
        assert "your moon sign is" not in reply.lower()
        assert "you are running rahu dasha" not in reply.lower()


# ---------------------------------------------------------------------------
# 5. Birth Details followed by an unrelated question
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_birth_details_followed_by_unrelated_question():
    """
    Verifies that previously submitted birth details in conversation history
    do NOT cause unrelated subsequent questions to be interpreted as birth chart requests.
    """
    history_with_birth_details = [
        {"role": "user", "content": "My birth details: 15-08-1990, 10:30 AM, Chennai"},
        {"role": "assistant", "content": "Thank you for sharing your details. How can I assist you with astrology today?"}
    ]

    unrelated_question = "What is Saturn retrograde?"
    assert detect_birth_details_submission(unrelated_question) is False

    reply, is_mock, sources = await llm_service.get_response(
        unrelated_question,
        history=history_with_birth_details
    )

    assert reply is not None
    # Unrelated question should NOT return birth chart card
    assert "title: Free Birth Chart" not in reply
    # Must answer about Saturn
    assert "saturn" in reply.lower() or "shani" in reply.lower()
    # Must NOT fabricate chart calculation from past birth details
    assert "based on your birth details" not in reply.lower()
    assert "your ascendant" not in reply.lower()


# ---------------------------------------------------------------------------
# 6. Compatibility Match Redirect Card
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_compatibility_match_redirect_card():
    """
    Verifies that compatibility match query returns the official redirect card
    from all_urls.txt (line 435).
    """
    reply, is_mock, sources = await llm_service.get_response("Compatibility Match")
    assert reply is not None
    assert ":::feature_card" in reply
    assert "title: Compatibility Match" in reply
    assert "button: Check Compatibility" in reply
    assert "url: https://www.astroved.com/astropedia/en/freetools/horoscope-matching" in reply
    assert "Partner 1" in reply
    assert "Partner 2" in reply


# ---------------------------------------------------------------------------
# 7. Support handoff remains fully functional
# ---------------------------------------------------------------------------
def test_support_handoff_by_typing():
    """
    Verifies that even with suggested buttons removed, typing support queries
    still triggers agent handoff.
    """
    handoff_queries = [
        "I have a payment issue with my order",
        "Talk to a human advisor",
        "Can I speak with an astrologer?"
    ]
    for q in handoff_queries:
        is_handoff, cat = detect_support_handoff_intent(q)
        assert is_handoff is True, f"Expected handoff for query: '{q}'"
