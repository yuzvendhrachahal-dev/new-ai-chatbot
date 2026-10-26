import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings

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
async def test_start_chat_and_send_message():
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
        assert "10th House" in send_data["reply"]["text"]
        assert send_data["is_mock"] is True

        # Check public session endpoint
        res_msgs = await ac.get(f"{settings.API_V1_STR}/chat/{conv_id}/messages")
        assert res_msgs.status_code == 200
        msgs_data = res_msgs.json()
        assert len(msgs_data["messages"]) >= 3 # welcome + user + assistant

@pytest.mark.asyncio
async def test_internal_agent_separation_and_security():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Unauthorized access without agent key
        res_unauth = await ac.get(f"{settings.API_V1_STR}/agent/conversations")
        assert res_unauth.status_code == 403

        # Authorized access with agent key
        headers = {"x-agent-key": settings.INTERNAL_AGENT_KEY}
        res_auth = await ac.get(f"{settings.API_V1_STR}/agent/conversations", headers=headers)
        assert res_auth.status_code == 200
        conv_list = res_auth.json()
        assert isinstance(conv_list, list)
