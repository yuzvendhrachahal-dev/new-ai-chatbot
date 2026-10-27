import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.core.database import get_database, get_sessions_collection, get_agents_collection, get_messages_collection
from app.core.security import hash_password
from app.services.knowledge import knowledge_service
from app.services.events import event_broker
from app.services.store import store
from app.services.intent import (
    detect_support_handoff_intent,
    CATEGORY_HUMAN,
    CATEGORY_PAYMENT,
    CATEGORY_ORDER,
    CATEGORY_REFUND,
    CATEGORY_PUJA,
    CATEGORY_COMPLAINT,
    CATEGORY_TECH
)

@pytest.fixture(autouse=True)
def setup_test_agent():
    # Ensure agent1 exists with known password
    agents_col = get_agents_collection()
    agents_col.update_one(
        {"username": "test_agent_1"},
        {
            "$set": {
                "username": "test_agent_1",
                "display_name": "Test Vedic Advisor",
                "role": "advisor",
                "password_hash": hash_password("secret_pass_123"),
                "is_active": True
            }
        },
        upsert=True
    )

@pytest.mark.asyncio
async def test_health_check_with_mongodb():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"{settings.API_V1_STR}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"]["status"] == "connected"
        assert data["database"]["database"] == settings.MONGODB_DATABASE

@pytest.mark.asyncio
async def test_agent_authentication_argon2id():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Invalid credentials -> 401
        res_bad = await ac.post(f"{settings.API_V1_STR}/agent/login", json={
            "username": "test_agent_1",
            "password": "wrong_password"
        })
        assert res_bad.status_code == 401

        # 2. Valid credentials -> 200 with JWT token
        res_ok = await ac.post(f"{settings.API_V1_STR}/agent/login", json={
            "username": "test_agent_1",
            "password": "secret_pass_123"
        })
        assert res_ok.status_code == 200
        data = res_ok.json()
        assert data["success"] is True
        assert "token" in data
        assert data["display_name"] == "Test Vedic Advisor"
        assert "password_hash" not in data  # Never expose password hash

        # 3. Protected endpoint without token -> 401
        res_unauth = await ac.get(f"{settings.API_V1_STR}/agent/conversations")
        assert res_unauth.status_code == 401

        # 4. Protected endpoint with Bearer token -> 200
        headers = {"Authorization": f"Bearer {data['token']}"}
        res_auth = await ac.get(f"{settings.API_V1_STR}/agent/conversations", headers=headers)
        assert res_auth.status_code == 200

@pytest.mark.asyncio
async def test_atomic_claim_and_conflict_handling():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Agent login
        login_res = await ac.post(f"{settings.API_V1_STR}/agent/login", json={
            "username": "test_agent_1",
            "password": "secret_pass_123"
        })
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create a customer session
        start_res = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Ananya Roy",
            "email": "ananya@example.com",
            "mobile": "+919876543299",
            "topic_of_interest": "Career & Ketu Dasha"
        })
        assert start_res.status_code == 200
        conv_id = start_res.json()["conversation_id"]

        # 2. Customer requests handoff -> status: waiting
        handoff_res = await ac.post(f"{settings.API_V1_STR}/chat/{conv_id}/handoff")
        assert handoff_res.status_code == 200

        # 3. Agent claims waiting session -> 200 OK
        claim_res = await ac.post(
            f"{settings.API_V1_STR}/agent/conversations/{conv_id}/claim",
            headers=headers
        )
        assert claim_res.status_code == 200
        assert claim_res.json()["status"] == "success"

        # 4. Another claim on the same session -> 409 Conflict
        second_claim = await ac.post(
            f"{settings.API_V1_STR}/agent/conversations/{conv_id}/claim",
            headers=headers
        )
        assert second_claim.status_code == 409
        assert "cannot be claimed" in second_claim.json()["detail"].lower()

@pytest.mark.asyncio
async def test_return_to_bot_and_close_transitions():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Agent login
        login = await ac.post(f"{settings.API_V1_STR}/agent/login", json={
            "username": "test_agent_1",
            "password": "secret_pass_123"
        })
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        # Start customer session and request handoff
        start = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Karthik Raja",
            "email": "karthik@example.com",
            "mobile": "+919840199999"
        })
        conv_id = start.json()["conversation_id"]
        await ac.post(f"{settings.API_V1_STR}/chat/{conv_id}/handoff")

        # Claim chat
        await ac.post(f"{settings.API_V1_STR}/agent/conversations/{conv_id}/claim", headers=headers)

        # 1. Agent returns session to bot
        ret_res = await ac.post(f"{settings.API_V1_STR}/agent/conversations/{conv_id}/return-to-bot", headers=headers)
        assert ret_res.status_code == 200
        assert ret_res.json()["new_status"] == "bot_active"

        # 2. Customer can message again and bot responds
        send_res = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "Which planet rules the 10th house?"
        })
        assert send_res.status_code == 200
        assert send_res.json()["reply"]["sender"] == "assistant"

        # 3. Close conversation
        close_res = await ac.post(f"{settings.API_V1_STR}/agent/conversations/{conv_id}/close", headers=headers)
        assert close_res.status_code == 200
        assert close_res.json()["new_status"] == "closed"

        # 4. Message sent to closed conversation must be rejected (400 Bad Request)
        rejected = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "Can I still ask a question?"
        })
        assert rejected.status_code == 400
        assert "closed" in rejected.json()["detail"].lower()

@pytest.mark.asyncio
async def test_rag_retrieval_and_source_citations():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Start session
        start = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Pooja Hegde",
            "email": "pooja@example.com",
            "mobile": "+919888812345"
        })
        conv_id = start.json()["conversation_id"]

        # Send query matching approved knowledge (Sade Sati)
        res = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "What is Sade Sati and what remedies pacify Saturn?"
        })
        assert res.status_code == 200
        data = res.json()
        reply_text = data["reply"]["text"]
        
        # Verify source citation exists
        assert "Source:" in reply_text
        assert "AstroVed.com" in reply_text
        assert data.get("sources") is not None
        assert len(data["sources"]) > 0

@pytest.mark.asyncio
async def test_analytics_aggregation_from_mongodb():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login = await ac.post(f"{settings.API_V1_STR}/agent/login", json={
            "username": "test_agent_1",
            "password": "secret_pass_123"
        })
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        res = await ac.get(f"{settings.API_V1_STR}/agent/analytics", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "total_sessions" in data
        assert "resolved" in data
        assert "waiting" in data
        assert "with_agent" in data
        assert "top_issues" in data
        assert "status_mix" in data
        assert "recent_users" in data
        assert isinstance(data["avg_response_time_seconds"], (int, float))

@pytest.mark.asyncio
async def test_message_persistence_in_mongodb():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Start customer session
        start_res = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Devi Priya",
            "email": "devi@example.com",
            "mobile": "+919777766666",
            "topic_of_interest": "Remedies & Navagraha Puja"
        })
        conv_id = start_res.json()["conversation_id"]

        # Send a message
        send_res = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "Which gemstone is suitable for Jupiter?"
        })
        assert send_res.status_code == 200

        # Query MongoDB directly to verify persistence
        messages_col = get_messages_collection()
        stored_messages = list(messages_col.find({"conversation_id": conv_id}).sort("timestamp", 1))
        
        # Should have welcome message, user question, and assistant reply
        assert len(stored_messages) >= 3
        user_msg = next((m for m in stored_messages if m["sender"] == "user"), None)
        assert user_msg is not None
        assert "Which gemstone is suitable for Jupiter?" in user_msg["text"]
        assert user_msg["timestamp"] is not None

        assistant_msg = next((m for m in stored_messages if m["sender"] == "assistant"), None)
        assert assistant_msg is not None

@pytest.mark.asyncio
async def test_customer_sse_event_isolation():
    # Verify that event broker channels are isolated per conversation ID
    conv_a = "conv_test_isolation_aaa"
    conv_b = "conv_test_isolation_bbb"

    queue_a = await event_broker.register_customer(conv_a)
    queue_b = await event_broker.register_customer(conv_b)

    try:
        # Broadcast event strictly to conversation A
        await event_broker.broadcast_to_customer(conv_a, "message", {"text": "Private to A"})

        # Subscriber A should receive it
        event_a = await queue_a.get()
        assert event_a.event == "message"
        assert "Private to A" in event_a.data

        # Subscriber B queue should be empty (no cross-tenant leakage)
        assert queue_b.empty() is True
    finally:
        await event_broker.unregister_customer(conv_a, queue_a)
        await event_broker.unregister_customer(conv_b, queue_b)

@pytest.mark.asyncio
async def test_deactivated_agent_login_denied():
    agents_col = get_agents_collection()
    agents_col.update_one(
        {"username": "deactivated_agent_x"},
        {
            "$set": {
                "username": "deactivated_agent_x",
                "display_name": "Deactivated Agent",
                "role": "advisor",
                "password_hash": hash_password("pass_valid_123"),
                "is_active": False  # Deactivated
            }
        },
        upsert=True
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(f"{settings.API_V1_STR}/agent/login", json={
            "username": "deactivated_agent_x",
            "password": "pass_valid_123"
        })
        assert res.status_code == 403
        assert "deactivated" in res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_messaging_during_agent_handling():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Agent login
        login = await ac.post(f"{settings.API_V1_STR}/agent/login", json={
            "username": "test_agent_1",
            "password": "secret_pass_123"
        })
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        # Start customer session
        start = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Nandhini Mohan",
            "email": "nandhini@example.com",
            "mobile": "+919940123456"
        })
        conv_id = start.json()["conversation_id"]

        # Request handoff & claim
        await ac.post(f"{settings.API_V1_STR}/chat/{conv_id}/handoff")
        await ac.post(f"{settings.API_V1_STR}/agent/conversations/{conv_id}/claim", headers=headers)

        # Customer sends message while agent is handling
        cust_send = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "Hello advisor, could you check my Sade Sati period?"
        })
        assert cust_send.status_code == 200
        data = cust_send.json()
        assert "AstroVed Advisor" in data["reply"]["text"]
        assert data["reply"]["sender"] == "system"

        # Agent replies to customer
        agent_rep = await ac.post(f"{settings.API_V1_STR}/agent/conversations/{conv_id}/reply", json={
            "reply": "Namaste Nandhini, I am calculating your Saturn transit right now."
        }, headers=headers)
        assert agent_rep.status_code == 200
        assert agent_rep.json()["message"]["sender"] == "agent"

        # Verify messages in conversation
        detail = await ac.get(f"{settings.API_V1_STR}/agent/conversations/{conv_id}", headers=headers)
        assert detail.status_code == 200
        msgs = detail.json()["messages"]
        assert any(m["text"] == "Hello advisor, could you check my Sade Sati period?" for m in msgs)
        assert any("Saturn transit right now" in m["text"] for m in msgs)

@pytest.mark.asyncio
async def test_lifecycle_transition_rules_and_conflict():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login = await ac.post(f"{settings.API_V1_STR}/agent/login", json={
            "username": "test_agent_1",
            "password": "secret_pass_123"
        })
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        # Start customer session -> bot_active
        start = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Siddharth Verma",
            "email": "sid@example.com",
            "mobile": "+919811122233"
        })
        conv_id = start.json()["conversation_id"]

        # Close session
        close_res = await ac.post(f"{settings.API_V1_STR}/agent/conversations/{conv_id}/close", headers=headers)
        assert close_res.status_code == 200

        # Attempt to transition out of closed terminal state -> 409 Conflict
        invalid_trans = await ac.post(
            f"{settings.API_V1_STR}/agent/conversations/{conv_id}/status",
            params={"status": "waiting"},
            headers=headers
        )
        assert invalid_trans.status_code == 409
        assert "invalid transition" in invalid_trans.json()["detail"].lower()

@pytest.mark.asyncio
async def test_auto_handoff_detection_for_payment_issue():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Start customer session
        start = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Meera Raman",
            "email": "meera@example.com",
            "mobile": "+919940888888"
        })
        conv_id = start.json()["conversation_id"]

        # Customer sends message with payment problem
        send_res = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "payment issue: my amount was deducted but pooja was not booked"
        })
        assert send_res.status_code == 200
        data = send_res.json()
        reply_text = data["reply"]["text"]
        
        # Verify handoff confirmation is returned instead of generic fallback
        assert "AstroVed Support Team" in reply_text
        assert "Payment & Billing Issue" in reply_text

        # Verify session status is now 'waiting'
        conv = store.get_conversation(conv_id)
        assert conv is not None
        assert conv["status"] == "waiting"
        assert conv.get("issue_type") == "Payment & Billing Issue"

        # Agent can see it in waiting queue
        login = await ac.post(f"{settings.API_V1_STR}/agent/login", json={
            "username": "test_agent_1",
            "password": "secret_pass_123"
        })
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        queue = await ac.get(f"{settings.API_V1_STR}/agent/conversations?tab=waiting", headers=headers)
        assert queue.status_code == 200
        sessions = queue.json()
        matching = [s for s in sessions if s["conversation_id"] == conv_id]
        assert len(matching) == 1
        assert matching[0]["status"] == "waiting"
        assert matching[0]["issue_type"] == "Payment & Billing Issue"


def test_all_seven_handoff_intent_categories():
    """
    Verifies detection of natural customer phrasing across all 7 categories:
    Human assistance, Payment, Orders/bookings, Refunds/cancellations,
    Puja/services, Complaints/escalation, Technical support.
    """
    # 1. Human assistance
    human_phrases = [
        "human",
        "live agent",
        "advisor",
        "representative",
        "customer support",
        "customer care",
        "talk to someone",
        "speak to someone",
        "call me",
        "connect me",
        "contact your team",
        "how do i contact support?"
    ]
    for phrase in human_phrases:
        is_h, cat = detect_support_handoff_intent(phrase)
        assert is_h is True, f"Failed for human phrase: {phrase}"
        assert cat == CATEGORY_HUMAN, f"Expected {CATEGORY_HUMAN} for '{phrase}', got {cat}"

    # 2. Payment
    payment_phrases = [
        "payment failed",
        "payment issue",
        "money deducted from my bank",
        "charged twice for the same pooja",
        "transaction failed on card",
        "refund payment",
        "invoice copy requested",
        "billing dispute",
        "upi error during checkout",
        "card declined at payment gateway"
    ]
    for phrase in payment_phrases:
        is_h, cat = detect_support_handoff_intent(phrase)
        assert is_h is True, f"Failed for payment phrase: {phrase}"
        assert cat == CATEGORY_PAYMENT, f"Expected {CATEGORY_PAYMENT} for '{phrase}', got {cat}"

    # 3. Orders and bookings
    order_phrases = [
        "order not received",
        "booking failed",
        "booking confirmation not received",
        "what is my order status?",
        "reschedule my appointment",
        "cancel booking",
        "service not delivered on time"
    ]
    for phrase in order_phrases:
        is_h, cat = detect_support_handoff_intent(phrase)
        assert is_h is True, f"Failed for order phrase: {phrase}"
        assert cat == CATEGORY_ORDER, f"Expected {CATEGORY_ORDER} for '{phrase}', got {cat}"

    # 4. Refunds and cancellations
    refund_phrases = [
        "i need a refund",
        "money back please",
        "please cancel my subscription",
        "cancellation of my booking",
        "payment reversal",
        "chargeback request"
    ]
    for phrase in refund_phrases:
        is_h, cat = detect_support_handoff_intent(phrase)
        assert is_h is True, f"Failed for refund phrase: {phrase}"
        assert cat == CATEGORY_REFUND, f"Expected {CATEGORY_REFUND} for '{phrase}', got {cat}"

    # 5. Puja and services
    puja_phrases = [
        "puja not performed yesterday",
        "homam issue and delayed",
        "service delayed by 3 hours",
        "wrong service conducted",
        "priest didn't arrive for the ceremony"
    ]
    for phrase in puja_phrases:
        is_h, cat = detect_support_handoff_intent(phrase)
        assert is_h is True, f"Failed for puja phrase: {phrase}"
        assert cat == CATEGORY_PUJA, f"Expected {CATEGORY_PUJA} for '{phrase}', got {cat}"

    # 6. Complaints and escalation
    complaint_phrases = [
        "i want to file a complaint",
        "grievance regarding your service",
        "unresolved issue for 5 days",
        "not satisfied with the reply",
        "problem not solved yet",
        "speak to manager immediately"
    ]
    for phrase in complaint_phrases:
        is_h, cat = detect_support_handoff_intent(phrase)
        assert is_h is True, f"Failed for complaint phrase: {phrase}"
        assert cat == CATEGORY_COMPLAINT, f"Expected {CATEGORY_COMPLAINT} for '{phrase}', got {cat}"

    # 7. Technical support
    tech_phrases = [
        "login issue on website",
        "OTP not received on my phone",
        "website error 500",
        "can't book anything online",
        "app not working on android"
    ]
    for phrase in tech_phrases:
        is_h, cat = detect_support_handoff_intent(phrase)
        assert is_h is True, f"Failed for tech phrase: {phrase}"
        assert cat == CATEGORY_TECH, f"Expected {CATEGORY_TECH} for '{phrase}', got {cat}"


def test_astrological_false_positives_avoided():
    """
    Verifies that terms like 'cancel' in astrology (cancellation of debility, cancel dosha),
    or 'human' (human birth / life spiritual concept), or 'karmic debt' do NOT trigger handoffs.
    """
    negative_astrology_queries = [
        "does jupiter in lagna cancel the dosha?",
        "what are the rules for neecha bhanga raj yoga?",
        "cancellation of debilitation in navamsha chart",
        "what is the spiritual purpose of human life in vedic astrology?",
        "what is the meaning of human birth according to shastras?",
        "how to clear payment of karmic debt through charity?",
        "tell me about rahu and ketu karmic debt",
        "what remedies are recommended for saturn transit in 8th house?",
        "how does mars in 7th house affect marriage?",
        "what is the significance of maha shivaratri puja?"
    ]
    for query in negative_astrology_queries:
        is_h, cat = detect_support_handoff_intent(query)
        assert is_h is False, f"False positive triggered for query: '{query}' (classified as {cat})"


@pytest.mark.asyncio
async def test_immediate_queue_event_emission_on_handoff():
    """
    Verifies that when a handoff is requested, an immediate queue_update event
    is published through the SSE event broker to all authorized agent queues.
    """
    # Register an agent queue with the broker
    agent_q = await event_broker.register_agent()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            start_res = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
                "name": "Pooja Nambiar",
                "email": "pooja@example.com",
                "mobile": "+919876500112"
            })
            conv_id = start_res.json()["conversation_id"]

            # Clear start_chat queue event from the agent queue
            while not agent_q.empty():
                agent_q.get_nowait()

            # Trigger handoff
            handoff_res = await ac.post(
                f"{settings.API_V1_STR}/chat/{conv_id}/handoff",
                params={"issue_type": "Puja & Service Issue"}
            )
            assert handoff_res.status_code == 200

            # Verify immediate queue_update was placed on agent queue
            found_queue_update = False
            for _ in range(agent_q.qsize()):
                event = agent_q.get_nowait()
                if event.event == "queue_update":
                    found_queue_update = True
                    break

            assert found_queue_update, "Expected immediate queue_update SSE event for connected agents"
    finally:
        await event_broker.unregister_agent(agent_q)


@pytest.mark.asyncio
async def test_two_way_messaging_and_agent_reply():
    """
    Verifies that when an agent claims a chat:
    1. Customer replies are delivered directly to the agent without AI/LLM intervention.
    2. Agent replies are persisted to MongoDB and retrievable by the customer.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login = await ac.post(f"{settings.API_V1_STR}/agent/login", json={
            "username": "test_agent_1",
            "password": "secret_pass_123"
        })
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        # Start customer chat
        start = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Devi Prasad",
            "email": "devi@example.com",
            "mobile": "+919888877777"
        })
        conv_id = start.json()["conversation_id"]

        # Handoff & Claim
        await ac.post(f"{settings.API_V1_STR}/chat/{conv_id}/handoff")
        claim_res = await ac.post(f"{settings.API_V1_STR}/agent/conversations/{conv_id}/claim", headers=headers)
        assert claim_res.status_code == 200

        # Customer sends message while agent is active
        cust_msg = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "Namaste advisor, can you help with my puja rescheduling?"
        })
        assert cust_msg.status_code == 200
        reply_json = cust_msg.json()["reply"]
        # Must acknowledge agent delivery without AI auto-responding
        assert "delivered to your assigned" in reply_json["text"].lower()

        # Agent replies
        agent_reply_res = await ac.post(
            f"{settings.API_V1_STR}/agent/conversations/{conv_id}/reply",
            json={"reply": "Namaste Devi ji, I am reviewing your booking now. I will reschedule it for tomorrow morning."},
            headers=headers
        )
        assert agent_reply_res.status_code == 200

        # Customer fetches messages
        conv_res = await ac.get(f"{settings.API_V1_STR}/chat/{conv_id}/messages")
        assert conv_res.status_code == 200
        messages = conv_res.json()["messages"]

        # Check last message is the agent reply
        assert messages[-1]["sender"] == "agent"
        assert "reschedule it for tomorrow morning" in messages[-1]["text"]


@pytest.mark.asyncio
async def test_end_chat_disables_and_rejects_new_messages():
    """
    Verifies that once a conversation is ended/closed, further customer messages are rejected with 400.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        start = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Tarun Kumar",
            "email": "tarun@example.com",
            "mobile": "+919777766666"
        })
        conv_id = start.json()["conversation_id"]

        # End chat from customer side
        end_res = await ac.post(f"{settings.API_V1_STR}/chat/{conv_id}/end")
        assert end_res.status_code == 200

        # Sending new message must fail with 400
        send_res = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "Can I still ask a question?"
        })
        assert send_res.status_code == 400
        assert "closed" in send_res.json()["detail"].lower()
