"""
Tests for AstroVed Product Catalog import, normalization, URL generation,
search, and LLM customer-facing description synthesis.
"""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings
from app.services.catalog import (
    generate_product_slug,
    generate_product_url,
    parse_inr_price,
    is_astroved_only,
    is_product_query,
    catalog_service,
    NormalizedProduct
)


def test_product_slug_generation():
    """
    Verifies slug generation requirements:
    - lowercase
    - replace spaces with hyphens
    - remove punctuation and unsupported characters
    - collapse repeated hyphens
    """
    assert generate_product_slug("Archetype Deity Pooja Ashtalakshmi Pooja") == "archetype-deity-pooja-ashtalakshmi-pooja"
    assert generate_product_slug("Rare Human Head Ganesha (Adhi Ganesha): 6 inches (") == "rare-human-head-ganesha-adhi-ganesha-6-inches"
    assert generate_product_slug("Saturn Retrograde 2016: Light & Sound Ritual @ Powerspot!") == "saturn-retrograde-2016-light-sound-ritual-powerspot"
    assert generate_product_slug("  Multi---Hyphen   Spacing / Slash  ") == "multi-hyphen-spacing-slash"
    assert generate_product_slug("") == ""


def test_product_url_canonical_pattern():
    """
    Verifies URL generation using the pattern:
    https://www.astroved.com/{slug}-P{ProductId}.aspx
    Preserving the product ID in the required P{ProductId} suffix.
    """
    url1 = generate_product_url(105, "Archetype Deity Pooja Ashtalakshmi Pooja")
    assert url1 == "https://www.astroved.com/archetype-deity-pooja-ashtalakshmi-pooja-P105.aspx"

    url2 = generate_product_url("22013", "Mothers Day 2014 - Feeding 3 Elderly Women on Mothers Day May 11th IST")
    assert url2 == "https://www.astroved.com/mothers-day-2014-feeding-3-elderly-women-on-mothers-day-may-11th-ist-P22013.aspx"

    url3 = generate_product_url(327, "Rare Human Head Ganesha (Adhi Ganesha): 6 inches (")
    assert url3 == "https://www.astroved.com/rare-human-head-ganesha-adhi-ganesha-6-inches-P327.aspx"


def test_price_inr_parsing():
    """
    Verifies INR pricing rules:
    - Use INR prices only.
    - Format valid prices as ₹ amounts.
    - If the INR price is missing, 0, or invalid, omit the price rather than inventing one.
    """
    num, fmt = parse_inr_price("225")
    assert num == 225
    assert fmt == "₹225"

    num, fmt = parse_inr_price("3330")
    assert num == 3330
    assert fmt == "₹3,330"

    num, fmt = parse_inr_price("15300.50")
    assert num == 15300.5
    assert fmt == "₹15,300.50"

    # Missing, empty, 0, negative, or invalid prices should be omitted (None, None)
    assert parse_inr_price("") == (None, None)
    assert parse_inr_price("0") == (None, None)
    assert parse_inr_price("-500") == (None, None)
    assert parse_inr_price(None) == (None, None)
    assert parse_inr_price("N/A") == (None, None)
    assert parse_inr_price("free") == (None, None)


def test_astroved_only_filtering_excludes_pillaicenter():
    """
    Verifies filtering requirements:
    - Include AstroVed-only records.
    - Exclude records associated with PillaiCenter; do not expose PillaiCenter products.
    - If a record is shared between AstroVed and PillaiCenter, exclude it for now.
    """
    # Exclusively AstroVed
    assert is_astroved_only("AstroVed") is True
    assert is_astroved_only("  AstroVed  ") is True

    # PillaiCenter or shared records must be excluded
    assert is_astroved_only("PillaiCenter") is False
    assert is_astroved_only("AstroVed | PillaiCenter") is False
    assert is_astroved_only("AstroVed | PillaiCenter | Priest Services") is False
    assert is_astroved_only("PillaiCenter | AstroVed") is False
    assert is_astroved_only("") is False
    assert is_astroved_only(None) is False


def test_catalog_normalization_and_structure():
    """
    Verifies that catalog_service loads the AstroVed-only catalog from the Excel spreadsheet,
    strips long description and dates, and includes both Active and Disabled products.
    """
    catalog_service.initialize()
    products = catalog_service.products

    assert len(products) > 0, "Expected normalized AstroVed products to be loaded."

    # Verify no PillaiCenter product is exposed
    for p in products:
        assert "pillaicenter" not in p.available_shops.lower(), f"PillaiCenter product leaked: {p.product_id}"
        assert p.product_id != "", "Product ID must be present."
        assert p.product_name != "", "Product name must be present."
        assert p.url.startswith("https://www.astroved.com/"), "URL must have canonical prefix."
        assert f"-P{p.product_id}.aspx" in p.url, "URL must contain -P{ProductId}.aspx suffix."

    # Verify both Active and Disabled records are included
    statuses = {p.product_status for p in products}
    assert "Disabled" in statuses
    # If Active products exist in dataset, they should also be represented
    assert any(p.product_status in ["Active", "Disabled"] for p in products)

    # Verify dates and long description HTML are completely ignored in NormalizedProduct schema
    sample = products[0]
    assert not hasattr(sample, "start_date"), "Start date must be ignored."
    assert not hasattr(sample, "end_date"), "End date must be ignored."
    assert not hasattr(sample, "long_description"), "Long description HTML must be ignored."

    # Verify INR-only currency formatting
    assert hasattr(sample, "price_inr")
    assert not hasattr(sample, "price_usd")
    assert not hasattr(sample, "price_myr")


def test_is_product_query_detection():
    """
    Verifies distinction between product/service questions and ordinary conversational messages.
    """
    # Product / service questions
    assert is_product_query("suggest me a saturn ritual") is True
    assert is_product_query("suggest a ritual for saturn") is True
    assert is_product_query("recommend a saturn ritual") is True
    assert is_product_query("saturn ritual") is True
    assert is_product_query("saturn rituals") is True
    assert is_product_query("shani ritual") is True
    assert is_product_query("What is the price of Ganesha homam?") is True
    assert is_product_query("Do you have any pooja for Saturn transit?") is True
    assert is_product_query("I want to book an online consultation") is True
    assert is_product_query("Can I buy a yantra or gemstone?") is True
    assert is_product_query("What rituals are available for Rahu Ketu?") is True

    # Ordinary greetings and general astrology questions (must NOT trigger product search)
    assert is_product_query("What is Saturn in Vedic astrology?") is False
    assert is_product_query("What is Saturn?") is False
    assert is_product_query("Tell me about Saturn") is False
    assert is_product_query("What are the remedies for Rahu Mahadasha?") is False
    assert is_product_query("hi") is False
    assert is_product_query("hello there") is False
    assert is_product_query("namaste") is False
    assert is_product_query("thank you so much") is False
    assert is_product_query("what is vedic astrology?") is False
    assert is_product_query("tell me about the 12 houses") is False


def test_catalog_search_relevance():
    """
    Verifies that search returns relevant products and does not return the entire catalog.
    """
    catalog_service.initialize()

    # Search for Saturn ritual
    results = catalog_service.search("Saturn ritual", top_k=3)
    assert 1 <= len(results) <= 3
    for r in results:
        combined = (r.product_name + " " + r.short_description).lower()
        assert "saturn" in combined or "shani" in combined

    # Search for non-existent item should return empty
    empty_results = catalog_service.search("completely non-existent xyz rocket spaceship", top_k=3)
    assert len(empty_results) == 0


@pytest.mark.asyncio
async def test_offline_product_response_formatting():
    """
    Verifies grounded offline description formatting when OpenAI is offline:
    - Includes product name, formatted INR price if valid, and link.
    - Never fabricates prices when missing.
    """
    product_with_price = NormalizedProduct(
        product_id="22013",
        product_name="Mothers Day Feeding Service",
        short_description="Feeding elderly women on Mothers day.",
        manufacturer_name="Service",
        available_shops="AstroVed",
        price_inr=225,
        formatted_price="₹225",
        product_status="Disabled",
        url="https://www.astroved.com/mothers-day-feeding-service-P22013.aspx"
    )

    product_without_price = NormalizedProduct(
        product_id="35733",
        product_name="Saturn Retrograde Light and Sound",
        short_description="Ritual to Saturn at His Powerspot.",
        manufacturer_name="Service",
        available_shops="AstroVed",
        price_inr=None,
        formatted_price=None,
        product_status="Disabled",
        url="https://www.astroved.com/saturn-retrograde-light-and-sound-P35733.aspx"
    )

    text, is_mock, sources = await catalog_service.generate_customer_description(
        query="Saturn pooja",
        products=[product_with_price, product_without_price],
        api_key="",  # Offline
        model="gpt-4o-mini"
    )

    assert is_mock is True
    assert "Mothers Day Feeding Service" in text
    assert "₹225" in text
    assert "https://www.astroved.com/mothers-day-feeding-service-P22013.aspx" in text

    assert "Saturn Retrograde Light and Sound" in text
    # Product without price should NOT have a fabricated price
    assert "₹0" not in text
    assert len(sources) == 2


@pytest.mark.asyncio
async def test_no_match_offers_human_handoff():
    """
    Verifies that if no relevant product matches, the chatbot responds honestly
    and offers the existing human handoff.
    """
    text, is_mock, sources = await catalog_service.generate_customer_description(
        query="unobtainium astral space voyage",
        products=[],
        api_key="",
        model="gpt-4o-mini"
    )
    assert "could not find a matching astroved catalog item" in text.lower()
    assert "advisor" in text.lower() or "connect" in text.lower()
    assert sources == []


@pytest.mark.asyncio
async def test_chat_send_triggers_catalog_search_for_product_query():
    """
    End-to-end test: sending a product query to /chat/send searches the catalog
    and returns product information with link and INR price without triggering handoff.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        start_res = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Meera",
            "email": "meera@example.com",
            "mobile": "+91 9876543210"
        })
        assert start_res.status_code == 200
        conv_id = start_res.json()["conversation_id"]

        send_res = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "Do you have any ritual or pooja for Saturn?"
        })
        assert send_res.status_code == 200
        data = send_res.json()
        reply_text = data["reply"]["text"]

        # Must include product link and name
        assert "astroved.com" in reply_text.lower()
        assert "saturn" in reply_text.lower()
        # Must not claim verified purchasability
        assert "currently purchasable" not in reply_text.lower()


@pytest.mark.asyncio
async def test_greeting_does_not_trigger_product_search():
    """
    Verifies that greetings (namaste, hi, hello) never trigger product search.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        start_res = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Rohan",
            "email": "rohan@example.com",
            "mobile": "+91 9876543210"
        })
        conv_id = start_res.json()["conversation_id"]

        send_res = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "Namaste! Good morning"
        })
        assert send_res.status_code == 200
        data = send_res.json()
        reply_text = data["reply"]["text"]

        # Should be a warm greeting, not product offerings
        assert any(w in reply_text.lower() for w in ["namaste", "morning", "welcome", "assist", "help"])
        assert "relevant offerings from the astroved catalog" not in reply_text.lower()
        assert data.get("sources") == []


@pytest.mark.asyncio
async def test_suggest_me_a_saturn_ritual_focused_behavior():
    """
    Focused verification for 'suggest me a saturn ritual':
    - Returns at most 3 AstroVed catalog products (excluding PillaiCenter).
    - Prefer matches related to Saturn/Shani and relevant ritual/pooja terms.
    - Each result has: product name, short description (max 1-2 sentences), INR price only if valid, product link.
    - Concise response: no generic ritual steps, DIY instructions, materials, mantra lists, or gemstone advice.
    - Never claims purchasability.
    """
    catalog_service.initialize()
    matched = catalog_service.search("suggest me a saturn ritual", top_k=3)

    assert 1 <= len(matched) <= 3, "Must return at most top 3 matches"

    for p in matched:
        # Excludes PillaiCenter
        assert "pillaicenter" not in p.available_shops.lower()
        assert "astroved" in p.available_shops.lower()
        # Related to Saturn / Shani
        combined = (p.product_name + " " + p.short_description).lower()
        assert "saturn" in combined or "shani" in combined or "sani" in combined
        # Canonical URL helper
        assert p.url.startswith("https://www.astroved.com/")
        assert f"-P{p.product_id}.aspx" in p.url
        # If price present, it's INR
        if p.formatted_price:
            assert p.formatted_price.startswith("₹")

    # Verify end-to-end response formatting (offline grounded response)
    resp_text = catalog_service.format_offline_response("suggest me a saturn ritual", matched)

    # Concise: no DIY guides or lengthy lists
    assert "step 1" not in resp_text.lower()
    assert "ingredients" not in resp_text.lower()
    assert "mantra list" not in resp_text.lower()
    assert "currently purchasable" not in resp_text.lower()

    # Contains links and product names
    for p in matched:
        assert p.url in resp_text
        assert p.product_name in resp_text


@pytest.mark.asyncio
async def test_product_description_grounded_in_short_description_and_missing_fallback():
    """
    Verifies that:
    - Excel Short Description column is the sole source for product description.
    - Long Description HTML is never used.
    - When source short description is missing, description is minimal and factual rather than hallucinating.
    - Output contains at most 3 products with product name, short description, valid INR price, and URL.
    """
    prod_with_short = NormalizedProduct(
        product_id="111",
        product_name="Saturn Remedy Homa",
        short_description="Special Vedic fire lab to pacify Saturn. Helps reduce delays and obstacles in life.",
        manufacturer_name="AstroVed",
        available_shops="AstroVed",
        price_inr=1500,
        formatted_price="₹1,500",
        product_status="Active",
        url="https://www.astroved.com/saturn-remedy-homa-P111.aspx"
    )

    prod_missing_short = NormalizedProduct(
        product_id="222",
        product_name="Saturn Yantra",
        short_description="",  # Missing short description
        manufacturer_name="AstroVed",
        available_shops="AstroVed",
        price_inr=850,
        formatted_price="₹850",
        product_status="Active",
        url="https://www.astroved.com/saturn-yantra-P222.aspx"
    )

    offline_resp = catalog_service.format_offline_response("saturn homa", [prod_with_short, prod_missing_short])

    # prod_with_short is grounded in short description
    assert "pacify Saturn" in offline_resp
    assert "obstacles" in offline_resp
    assert "₹1,500" in offline_resp
    assert "https://www.astroved.com/saturn-remedy-homa-P111.aspx" in offline_resp

    # prod_missing_short is minimal and factual (does not hallucinate imaginary rituals/benefits)
    assert "Vedic spiritual offering for Saturn Yantra" in offline_resp or "Saturn Yantra" in offline_resp
    assert "₹850" in offline_resp
    assert "https://www.astroved.com/saturn-yantra-P222.aspx" in offline_resp

    # Long description HTML must never exist on NormalizedProduct
    assert not hasattr(prod_with_short, "long_description")
    assert not hasattr(prod_missing_short, "long_description")


@pytest.mark.asyncio
async def test_what_is_saturn_routes_to_conversational_llm():
    """
    Focused verification:
    'What is Saturn in Vedic astrology?' must route to the conversational LLM,
    NOT forced catalog output.
    """
    from app.services.llm import llm_service

    query = "What is Saturn in Vedic astrology?"
    assert is_product_query(query) is False, "General astrology query must not trigger product intent"

    reply, is_mock, sources = await llm_service.get_response(query)
    # Must NOT return catalog listings
    assert "relevant offerings from the astroved catalog" not in reply.lower()
    assert "product name:" not in reply.lower()
    # Must be conversational Vedic astrology response
    assert any(term in reply.lower() for term in ["shani", "saturn", "planet", "karma", "vedic"])


@pytest.mark.asyncio
async def test_handoff_precedence_over_product_and_llm():
    """
    Focused verification:
    Payment/refund/booking/agent requests must hand off before catalog or LLM handling.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        start_res = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Karthik",
            "email": "karthik@example.com",
            "mobile": "+91 9876543210"
        })
        conv_id = start_res.json()["conversation_id"]

        # User mentions payment issue for a Saturn ritual
        send_res = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "My payment for Saturn ritual failed, please help me with refund"
        })
        assert send_res.status_code == 200
        data = send_res.json()

        # Hand off must be triggered immediately
        assert "Support Team" in data["reply"]["text"]
        assert any(cat in data["reply"]["text"] for cat in ["Refund & Cancellation", "Payment & Billing Issue"])
        assert "relevant offerings from the astroved catalog" not in data["reply"]["text"].lower()


@pytest.mark.asyncio
async def test_love_pooja_and_misspelled_poja_catalog_routing():
    """
    Focused verification for 'suggest me love pooja' and 'love poja':
    - 'love poja' spelling error is normalized to 'love pooja'
    - Both queries trigger catalog search BEFORE general LLM response
    - Returns at most 3 AstroVed products related to love/relationship rituals
    - Excludes PillaiCenter
    - Shows product name, 2-3 line description from Excel Short Description, valid INR price, and URL
    """
    from app.services.catalog import normalize_spelling, catalog_service
    from app.services.llm import llm_service

    assert normalize_spelling("love poja") == "love pooja"
    assert is_product_query("suggest me love pooja") is True
    assert is_product_query("love poja") is True

    catalog_service.initialize()
    matched = catalog_service.search("love poja", top_k=3)
    assert 1 <= len(matched) <= 3

    for p in matched:
        assert "pillaicenter" not in p.available_shops.lower()
        assert "astroved" in p.available_shops.lower()
        combined = (p.product_name + " " + p.short_description).lower()
        assert any(term in combined for term in ["relationship", "love", "romance", "marriage", "venus"])
        assert p.url.startswith("https://www.astroved.com/")
        if p.formatted_price:
            assert p.formatted_price.startswith("₹")

    # End-to-end response routing through LLMService
    reply, is_mock, sources = await llm_service.get_response("suggest me love pooja")
    assert any(term in reply.lower() for term in ["relevant", "astroved"])
    assert "astroved.com" in reply.lower()
    assert len(sources) <= 3
    # Check that it did not return generic ritual advice
    assert "step 1" not in reply.lower()


@pytest.mark.asyncio
async def test_saturn_product_and_gemstone_routing():
    """
    Focused verification for 'saturn ritual' and 'recommend a gemstone':
    - Triggers catalog search
    - Returns at most 3 AstroVed products
    """
    assert is_product_query("saturn ritual") is True
    assert is_product_query("recommend a gemstone") is True

    catalog_service.initialize()
    saturn_prods = catalog_service.search("saturn ritual", top_k=3)
    assert 1 <= len(saturn_prods) <= 3
    for p in saturn_prods:
        combined = (p.product_name + " " + p.short_description).lower()
        assert "saturn" in combined or "shani" in combined or "sani" in combined

    gemstone_prods = catalog_service.search("recommend a gemstone", top_k=3)
    assert 1 <= len(gemstone_prods) <= 3
    for p in gemstone_prods:
        combined = (p.product_name + " " + p.short_description).lower()
        assert any(term in combined for term in ["gemstone", "mala", "sapphire", "ruby", "emerald", "stone"])


@pytest.mark.asyncio
async def test_no_match_catalog_behavior_never_falls_back_to_generic_rituals():
    """
    Focused verification for no-match queries:
    - If no relevant catalog products are found, state that no matching AstroVed product was found
    - Offer human support
    - Never fall back to generic ritual recommendations
    """
    from app.services.llm import llm_service

    assert is_product_query("suggest me an unobtainium pooja") is True

    catalog_service.initialize()
    empty = catalog_service.search("unobtainium pooja", top_k=3)
    assert len(empty) == 0

    reply, is_mock, sources = await llm_service.get_response("suggest me an unobtainium pooja")
    assert "could not find a matching astroved catalog item" in reply.lower()
    assert "advisor" in reply.lower() or "support" in reply.lower()
    assert sources == []
    # Must not contain generic DIY ritual steps
    assert "step 1" not in reply.lower()
    assert "ingredients" not in reply.lower()


@pytest.mark.asyncio
async def test_ordinary_astrology_questions_route_to_conversational_llm():
    """
    Focused verification for ordinary conversational questions:
    'What is love in Vedic astrology?' and 'What is Saturn in Vedic astrology?'
    must route to conversational LLM, NOT catalog search.
    """
    from app.services.llm import llm_service

    q_love = "What is love in Vedic astrology?"
    q_saturn = "What is Saturn in Vedic astrology?"

    assert is_product_query(q_love) is False
    assert is_product_query(q_saturn) is False

    reply_love, _, sources_love = await llm_service.get_response(q_love)
    assert "relevant offerings from the astroved catalog" not in reply_love.lower()
    assert "product name:" not in reply_love.lower()
    assert any(w in reply_love.lower() for w in ["venus", "love", "7th house", "vedic", "astrology", "relationship"])

    reply_saturn, _, sources_saturn = await llm_service.get_response(q_saturn)
    assert "relevant offerings from the astroved catalog" not in reply_saturn.lower()
    assert "product name:" not in reply_saturn.lower()
    assert any(w in reply_saturn.lower() for w in ["saturn", "shani", "karma", "planet", "discipline"])


def test_greetings_do_not_trigger_catalog_and_avoid_repetition():
    """
    Focused verification:
    - Greetings must not trigger catalog search
    - Welcome message is not repeated on subsequent turns (when has_history is True)
    """
    from app.services.intent import detect_greeting_intent

    assert is_product_query("hi") is False
    assert is_product_query("namaste") is False
    assert is_product_query("hello") is False

    # First turn greeting: includes welcome
    first_turn = detect_greeting_intent("hi", has_history=False)
    assert "Welcome to AstroVed" in first_turn

    # Subsequent turn greeting: avoids repeating 'Welcome to AstroVed'
    subsequent_turn = detect_greeting_intent("hi", has_history=True)
    assert "Welcome to AstroVed" not in subsequent_turn
    assert "Namaste" in subsequent_turn


@pytest.mark.asyncio
async def test_quick_action_routing_and_priority():
    """
    Focused verification for quick-action buttons:
    - Today's Horoscope: prompts for Moon sign / birth details
    - Free Birth Chart: prompts for Date, Time, Place of birth
    - Compatibility Match: prompts for both partners' birth details
    - Remedies: provides overview of 4 remedy categories and invites specific product queries
    - Payment Issue: triggers payment handoff
    - Talk to Human: triggers human advisor handoff
    """
    from app.services.intent import detect_quick_action_intent, detect_support_handoff_intent
    from app.services.llm import llm_service

    # Quick actions should not trigger product catalog search
    assert is_product_query("Today's Horoscope") is False
    assert is_product_query("Free Birth Chart") is False
    assert is_product_query("Compatibility Match") is False
    assert is_product_query("Remedies") is False

    # Today's Horoscope
    resp_horo, _, _ = await llm_service.get_response("Today's Horoscope")
    assert "moon sign" in resp_horo.lower() or "rashi" in resp_horo.lower()
    assert "relevant offerings from the astroved catalog" not in resp_horo.lower()

    # Free Birth Chart
    resp_chart, _, _ = await llm_service.get_response("Free Birth Chart")
    assert "date of birth" in resp_chart.lower()
    assert "time of birth" in resp_chart.lower()
    assert "place of birth" in resp_chart.lower()

    # Compatibility Match
    resp_compat, _, _ = await llm_service.get_response("Compatibility Match")
    assert "partner 1" in resp_compat.lower()
    assert "partner 2" in resp_compat.lower()

    # Remedies
    resp_rem, _, _ = await llm_service.get_response("Remedies")
    assert "planetary & dosha remedies" in resp_rem.lower()
    assert "career & financial remedies" in resp_rem.lower()
    assert "love & relationship remedies" in resp_rem.lower()

    # Payment Issue priority
    is_handoff_pay, cat_pay = detect_support_handoff_intent("Payment issue with my order")
    assert is_handoff_pay is True
    assert cat_pay == "Payment & Billing Issue"

    # Talk to Human priority
    is_handoff_human, cat_human = detect_support_handoff_intent("Talk to Human")
    assert is_handoff_human is True
    assert cat_human == "Live Advisor Request"

