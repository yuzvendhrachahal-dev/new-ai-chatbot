from fastapi import APIRouter, HTTPException, Header
from app.schemas.chat import (
    StartChatRequest,
    StartChatResponse,
    SendMessageRequest,
    SendMessageResponse,
    AgentReplyRequest,
    ConversationSummary,
    CustomerLead
)
from app.services.store import store
from app.services.llm import llm_service
from app.core.config import settings

api_router = APIRouter()

# -----------------
# PUBLIC ENDPOINTS (Seekers / Customers)
# -----------------

@api_router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AstroVed AI Chatbot Service",
        "version": "1.0.0",
        "openai_configured": bool(settings.OPENAI_API_KEY.strip()),
        "mongodb_configured": bool(settings.MONGODB_URI.strip())
    }

@api_router.post("/chat/start", response_model=StartChatResponse)
async def start_chat(payload: StartChatRequest):
    """
    Public endpoint: Customer submits welcome form with Name, Email, Mobile
    Creates a new conversation session and returns initial greeting.
    """
    customer = CustomerLead(
        name=payload.name.strip(),
        email=payload.email.strip(),
        mobile=payload.mobile.strip(),
        topic_of_interest=payload.topic_of_interest or "General Vedic Astrology"
    )
    conv_id = store.create_conversation(customer, payload.initial_query)
    conv = store.get_conversation(conv_id)
    
    welcome_msg = conv["messages"][0].text
    return StartChatResponse(
        conversation_id=conv_id,
        welcome_message=welcome_msg,
        customer=customer
    )

@api_router.post("/chat/send", response_model=SendMessageResponse)
async def send_chat_message(payload: SendMessageRequest):
    """
    Public endpoint: Customer sends a message in their active conversation.
    If human agent hasn't taken over, AstroVed AI responds automatically.
    """
    conv = store.get_conversation(payload.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation session not found")

    user_msg = store.add_message(payload.conversation_id, sender="user", text=payload.message)
    
    # Check if human agent has taken over
    if conv.get("is_agent_handling", False):
        reply_msg = store.add_message(
            payload.conversation_id,
            sender="agent",
            text="Your message has been received by your dedicated AstroVed Astrology Consultant. We will respond momentarily."
        )
        return SendMessageResponse(
            conversation_id=payload.conversation_id,
            user_message=user_msg,
            reply=reply_msg,
            is_mock=False
        )

    # Format history for LLM
    history = []
    for m in conv["messages"][:-1]:
        role = "assistant" if m.sender in ["assistant", "agent"] else "user"
        history.append({"role": role, "content": m.text})

    llm_reply, is_mock = await llm_service.get_response(payload.message, history=history[-6:])
    reply_msg = store.add_message(payload.conversation_id, sender="assistant", text=llm_reply)

    return SendMessageResponse(
        conversation_id=payload.conversation_id,
        user_message=user_msg,
        reply=reply_msg,
        is_mock=is_mock
    )

@api_router.get("/chat/{conversation_id}/messages")
def get_session_messages(conversation_id: str):
    """
    Public endpoint strictly scoped to the specific conversation ID.
    Never exposes other conversations or user listings.
    """
    conv = store.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation session not found")
    return {
        "conversation_id": conversation_id,
        "customer_name": conv["customer"].name,
        "status": conv["status"],
        "is_agent_handling": conv.get("is_agent_handling", False),
        "messages": conv["messages"]
    }

# -----------------
# INTERNAL AGENT ENDPOINTS (Secured / Separated)
# -----------------

def verify_internal_access(x_agent_key: str = Header(None)):
    # Simple secure internal access gate
    if settings.INTERNAL_AGENT_KEY and x_agent_key != settings.INTERNAL_AGENT_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized agent access")
    return True

@api_router.get("/agent/conversations", response_model=list[ConversationSummary])
def list_agent_conversations(x_agent_key: str = Header(None)):
    """
    Internal agent endpoint: list all customer conversations and leads.
    """
    verify_internal_access(x_agent_key)
    return store.list_conversations()

@api_router.get("/agent/conversations/{conversation_id}")
def get_agent_conversation_detail(conversation_id: str, x_agent_key: str = Header(None)):
    """
    Internal agent endpoint: full conversation history and customer details.
    """
    verify_internal_access(x_agent_key)
    conv = store.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

@api_router.post("/agent/conversations/{conversation_id}/reply")
def agent_reply(conversation_id: str, payload: AgentReplyRequest, x_agent_key: str = Header(None)):
    """
    Internal agent endpoint: live human advisor overrides or replies directly to customer.
    """
    verify_internal_access(x_agent_key)
    conv = store.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Mark as agent handling
    store.update_status(conversation_id, status="active", is_agent=True)
    msg = store.add_message(conversation_id, sender="agent", text=payload.reply)
    return {"status": "success", "message": msg}

@api_router.post("/agent/conversations/{conversation_id}/status")
def update_conversation_status(conversation_id: str, status: str, x_agent_key: str = Header(None)):
    """
    Internal agent endpoint: update status (active, escalated, resolved)
    """
    verify_internal_access(x_agent_key)
    if not store.update_status(conversation_id, status):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success", "conversation_id": conversation_id, "new_status": status}
