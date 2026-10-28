import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.core.database import get_agents_collection
from app.core.security import hash_password

@pytest.fixture(autouse=True)
def setup_api_test_agent():
    agents_col = get_agents_collection()
    agents_col.update_one(
        {"username": "test_api_agent"},
        {
            "$set": {
                "username": "test_api_agent",
                "display_name": "AstroVed Test Advisor",
                "role": "advisor",
                "password_hash": hash_password("astroved"),
                "is_active": True
            }
        },
        upsert=True
    )

@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"{settings.API_V1_STR}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "AstroVed AI" in data["service"]

@pytest.mark.asyncio
async def test_start_chat_and_send_message(monkeypatch):
    monkeypatch.setattr(settings, "RAG_ENABLED", True)
    from app.services.knowledge import knowledge_service
    knowledge_service._ensure_fixtures_seeded()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Start chat with customer details
        start_payload = {
            "name": "Nivash K",
            "email": "nivash.test@example.com",
            "mobile": "+919876543210",
            "topic_of_interest": "Career & Vedic Remedies"
        }
        res_start = await ac.post(f"{settings.API_V1_STR}/chat/start", json=start_payload)
        assert res_start.status_code == 200
        start_data = res_start.json()
        assert "conversation_id" in start_data
        assert "Namaste Nivash K" in start_data["welcome_message"]
        conv_id = start_data["conversation_id"]

        # Send a career question
        send_payload = {
            "conversation_id": conv_id,
            "message": "What does my 10th house say about my job?"
        }
        res_send = await ac.post(f"{settings.API_V1_STR}/chat/send", json=send_payload)
        assert res_send.status_code == 200
        send_data = res_send.json()
        assert send_data["reply"]["sender"] == "assistant"
        assert "10th house" in send_data["reply"]["text"].lower() or "karma bhava" in send_data["reply"]["text"].lower()

        # Check public session endpoint
        res_msgs = await ac.get(f"{settings.API_V1_STR}/chat/{conv_id}/messages")
        assert res_msgs.status_code == 200
        msgs_data = res_msgs.json()
        assert len(msgs_data["messages"]) >= 3 # welcome + user + assistant

@pytest.mark.asyncio
async def test_internal_agent_separation_and_security():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Unauthorized access without agent key -> 401
        res_unauth = await ac.get(f"{settings.API_V1_STR}/agent/conversations")
        assert res_unauth.status_code == 401

@pytest.mark.asyncio
async def test_agent_login_and_claim_and_analytics():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Agent login
        login_res = await ac.post(f"{settings.API_V1_STR}/agent/login", json={"username": "test_api_agent", "password": "astroved"})
        assert login_res.status_code == 200
        login_data = login_res.json()
        assert login_data["success"] is True
        token = login_data["token"]

        # Create session to claim
        start_res = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Arjun Sharma",
            "email": "arjun@example.com",
            "mobile": "+919876543210"
        })
        conv_id = start_res.json()["conversation_id"]
        await ac.post(f"{settings.API_V1_STR}/chat/{conv_id}/handoff")

        # Claim conversation
        headers = {"Authorization": f"Bearer {token}"}
        claim_res = await ac.post(
            f"{settings.API_V1_STR}/agent/conversations/{conv_id}/claim",
            headers=headers
        )
        assert claim_res.status_code == 200

        # Analytics
        analytics_res = await ac.get(f"{settings.API_V1_STR}/agent/analytics", headers=headers)
        assert analytics_res.status_code == 200
        analytics_data = analytics_res.json()
        assert "total_sessions" in analytics_data
        assert "top_issues" in analytics_data
        assert "status_mix" in analytics_data
        assert "recent_users" in analytics_data

@pytest.mark.asyncio
async def test_customer_handoff_and_end():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Start chat
        res_start = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Sita Lakshmi",
            "email": "sita@example.com",
            "mobile": "+919888877777"
        })
        assert res_start.status_code == 200
        conv_id = res_start.json()["conversation_id"]

        # Handoff
        res_handoff = await ac.post(f"{settings.API_V1_STR}/chat/{conv_id}/handoff")
        assert res_handoff.status_code == 200
        assert res_handoff.json()["status"] == "success"

        # End chat
        res_end = await ac.post(f"{settings.API_V1_STR}/chat/{conv_id}/end")
        assert res_end.status_code == 200
        assert res_end.json()["status"] == "success"

@pytest.mark.asyncio
async def test_submit_rating():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res_start = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Kavitha Raman",
            "email": "kavitha@example.com",
            "mobile": "+919777788888"
        })
        conv_id = res_start.json()["conversation_id"]

        # Submit 5-star rating with feedback
        rating_res = await ac.post(
            f"{settings.API_V1_STR}/chat/{conv_id}/rating",
            json={"rating": 5, "feedback": "Astrology insights were very accurate and divine!"}
        )
        assert rating_res.status_code == 200
        rating_data = rating_res.json()
        assert rating_data["success"] is True
        assert rating_data["rating"] == 5

        # Duplicate submission check
        dup_res = await ac.post(
            f"{settings.API_V1_STR}/chat/{conv_id}/rating",
            json={"rating": 4, "feedback": "Different feedback"}
        )
        assert dup_res.status_code == 200
        dup_data = dup_res.json()
        assert dup_data["success"] is True
        assert dup_data["already_submitted"] is True
        assert dup_data["rating"] == 5  # Unchanged

@pytest.mark.asyncio
async def test_end_and_return_to_bot_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Agent login
        login_res = await ac.post(f"{settings.API_V1_STR}/agent/login", json={"username": "test_api_agent", "password": "astroved"})
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Customer starts chat & requests handoff
        res_start = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Gopal K",
            "email": "gopal@example.com",
            "mobile": "+919555544444"
        })
        conv_id = res_start.json()["conversation_id"]
        await ac.post(f"{settings.API_V1_STR}/chat/{conv_id}/handoff")

        # Agent claims chat
        claim_res = await ac.post(f"{settings.API_V1_STR}/agent/conversations/{conv_id}/claim", headers=headers)
        assert claim_res.status_code == 200

        # Agent clicks "End & Return to Bot"
        return_res = await ac.post(f"{settings.API_V1_STR}/agent/conversations/{conv_id}/return-to-bot", headers=headers)
        assert return_res.status_code == 200
        return_data = return_res.json()
        assert return_data["status"] == "success"

        # Check session: bot_active, unassigned, not closed
        conv_res = await ac.get(f"{settings.API_V1_STR}/chat/{conv_id}/messages")
        assert conv_res.status_code == 200
        conv_data = conv_res.json()
        assert conv_data["status"] == "bot_active"
        assert conv_data["assigned_agent"] is None

        # Verify agent CANNOT reply now that it is returned to bot
        reply_res = await ac.post(
            f"{settings.API_V1_STR}/agent/conversations/{conv_id}/reply",
            json={"reply": "I am trying to talk after returning to bot"},
            headers=headers
        )
        assert reply_res.status_code == 400
        assert "Cannot reply to a conversation that is with the bot" in reply_res.json()["detail"]

        # Customer sends next message -> AI responds
        user_msg = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "Can you tell me about Rahu Ketu transit?"
        })
        assert user_msg.status_code == 200
        user_msg_data = user_msg.json()
        assert user_msg_data["reply"]["sender"] == "assistant"

@pytest.mark.asyncio
async def test_greeting_intent_routing_and_rag_separation(monkeypatch):
    monkeypatch.setattr(settings, "RAG_ENABLED", True)
    from app.services.knowledge import knowledge_service
    knowledge_service._ensure_fixtures_seeded()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Start customer session
        start_res = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Meera Natarajan",
            "email": "meera@example.com",
            "mobile": "+919888812345"
        })
        conv_id = start_res.json()["conversation_id"]

        # 1. Casual greeting 'hi' -> natural brief response, NO knowledge fallback
        hi_res = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "hi"
        })
        assert hi_res.status_code == 200
        hi_data = hi_res.json()
        hi_reply = hi_data["reply"]["text"]
        assert any(w in hi_reply.lower() for w in ["namaste", "welcome", "assist", "help", "journey"])
        assert "knowledge base does not currently contain" not in hi_reply

        # 2. 'good morning'
        morning_res = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "Good morning!"
        })
        assert morning_res.status_code == 200
        morning_reply = morning_res.json()["reply"]["text"]
        assert any(w in morning_reply.lower() for w in ["good morning", "morning", "namaste"])
        assert "knowledge base does not currently contain" not in morning_reply

        # 3. 'thank you'
        thanks_res = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "thank you so much"
        })
        assert thanks_res.status_code == 200
        thanks_reply = thanks_res.json()["reply"]["text"]
        assert any(w in thanks_reply.lower() for w in ["welcome", "blessings", "assist", "help"])
        assert "knowledge base does not currently contain" not in thanks_reply

        # 4. Genuine astrology query -> triggers knowledge retrieval / RAG
        rag_res = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "What does my 10th house say about my job?"
        })
        assert rag_res.status_code == 200
        rag_data = rag_res.json()
        assert "10th house" in rag_data["reply"]["text"].lower() or "karma bhava" in rag_data["reply"]["text"].lower()
        assert len(rag_data["sources"]) > 0

        # 5. Support intent has higher priority than greeting or RAG
        support_res = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
            "conversation_id": conv_id,
            "message": "Hello, my payment failed and money was deducted"
        })
        assert support_res.status_code == 200
        support_data = support_res.json()
        assert "AstroVed Support Team" in support_data["reply"]["text"]
        assert "Payment & Billing Issue" in support_data["reply"]["text"]


