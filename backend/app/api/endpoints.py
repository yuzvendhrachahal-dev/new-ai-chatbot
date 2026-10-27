import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query
from sse_starlette.sse import EventSourceResponse

from app.schemas.chat import (
    StartChatRequest,
    StartChatResponse,
    SendMessageRequest,
    SendMessageResponse,
    MessageItem,
    AgentReplyRequest,
    ConversationSummary,
    ConversationDetail,
    CustomerLead,
    AgentLoginRequest,
    AgentLoginResponse,
    AnalyticsResponse,
    RatingSubmitRequest,
    RatingSubmitResponse
)
from app.services.store import (
    store,
    SessionConflictError,
    SessionNotFoundError,
    SessionClosedError
)
from app.services.llm import llm_service
from app.services.events import event_broker
from app.services.intent import detect_support_handoff_intent, detect_greeting_intent
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_agent
)
from app.core.database import (
    check_mongo_connection,
    get_agents_collection,
    get_sessions_collection
)
from app.core.config import settings

logger = logging.getLogger(__name__)

api_router = APIRouter()

# -----------------
# PUBLIC ENDPOINTS (Customers / Seekers)
# -----------------

@api_router.get("/health")
def health_check():
    """
    Health check endpoint: verifies MongoDB connectivity and service readiness.
    If MongoDB is unavailable, raises 503 rather than claiming storage works.
    """
    try:
        mongo_status = check_mongo_connection()
        return {
            "status": "healthy",
            "service": "AstroVed AI Chatbot Service",
            "version": "1.0.0",
            "database": mongo_status,
            "openai_configured": bool(settings.OPENAI_API_KEY.strip())
        }
    except Exception as err:
        logger.error("Health check failure: %s", err)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Backend unhealthy: {err}"
        )

@api_router.post("/chat/start", response_model=StartChatResponse)
async def start_chat(payload: StartChatRequest):
    """
    Customer initializes a chat consultation with Name, Email, and Mobile.
    Creates MongoDB session, saves initial greeting, and broadcasts queue update.
    """
    customer = CustomerLead(
        name=payload.name.strip(),
        email=payload.email.strip(),
        mobile=payload.mobile.strip(),
        topic_of_interest=payload.topic_of_interest or "General Vedic Astrology"
    )

    conv_id = store.create_conversation(customer, payload.initial_query)
    conv = store.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=500, detail="Failed to initialize conversation session.")

    welcome_msg = conv["messages"][0].text

    # Notify connected agents about the new session
    analytics = store.get_analytics()
    await event_broker.publish_queue_update(
        waiting_count=analytics["waiting"],
        active_count=analytics["with_agent"],
        conversation_id=conv_id,
        action="created"
    )

    return StartChatResponse(
        conversation_id=conv_id,
        welcome_message=welcome_msg,
        customer=customer
    )


@api_router.post("/chat/send", response_model=SendMessageResponse)
async def send_chat_message(payload: SendMessageRequest):
    """
    Customer sends a message in their active conversation.
    Rejects messages if the session has been closed.
    If human agent has claimed the chat, holds for agent reply;
    If support handoff or waiting, sets queue status and confirms;
    Otherwise responds with Vedic AI (RAG).
    """
    conv = store.get_conversation(payload.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation session not found.")

    if conv.get("status") == "closed":
        raise HTTPException(status_code=400, detail="Conversation is closed. New messages cannot be accepted.")

    # 1. Save user message to MongoDB before any event dispatch
    try:
        user_msg = store.add_message(payload.conversation_id, sender="user", text=payload.message)
    except SessionClosedError as err:
        raise HTTPException(status_code=400, detail=str(err))

    # Publish user message via SSE
    await event_broker.publish_message(payload.conversation_id, user_msg.model_dump())

    # 2. Check if a live human agent is currently handling this conversation
    if conv.get("is_agent_handling", False) or conv.get("status") == "active":
        # Do not let AI auto-reply when an agent is assigned (frontend filters out visible system delivery message)
        return SendMessageResponse(
            conversation_id=payload.conversation_id,
            user_message=user_msg,
            reply=MessageItem(
                id=f"ack_{user_msg.id}",
                sender="system",
                text="Message delivered to your assigned AstroVed Advisor."
            ),
            is_mock=False
        )

    # 3. Check if session is already waiting for an agent in the queue
    if conv.get("status") == "waiting":
        # Do not repeat handoff ack; the waiting status banner communicates queue state
        return SendMessageResponse(
            conversation_id=payload.conversation_id,
            user_message=user_msg,
            reply=None,
            is_mock=False
        )

    # 4. Check for automatic handoff intent (payment issue, booking, refund, agent request)
    is_handoff, issue_category = detect_support_handoff_intent(payload.message)
    if is_handoff:
        target_issue = issue_category or "Customer Support Request"
        store.request_handoff(payload.conversation_id, issue_type=target_issue)

        handoff_ack_text = (
            f"Your request regarding {target_issue} has been sent to our AstroVed Support Team. "
            f"An advisor will join this consultation shortly. You can also reach our team directly via "
            f"WhatsApp (+91 96773 91109) or email (support@astroved.com)."
        )
        handoff_reply = store.add_message(payload.conversation_id, sender="assistant", text=handoff_ack_text)

        # Broadcast SSE events to customer and agent queue immediately
        await event_broker.publish_message(payload.conversation_id, handoff_reply.model_dump())
        await event_broker.publish_status_change(payload.conversation_id, "waiting", None)
        analytics = store.get_analytics()
        await event_broker.publish_queue_update(
            waiting_count=analytics["waiting"],
            active_count=analytics["with_agent"],
            conversation_id=payload.conversation_id,
            action="waiting"
        )

        return SendMessageResponse(
            conversation_id=payload.conversation_id,
            user_message=user_msg,
            reply=handoff_reply,
            is_mock=False
        )

    # 5. Check for greeting / gratitude / small talk before RAG retrieval
    greeting_reply = detect_greeting_intent(payload.message)
    if greeting_reply:
        reply_msg = store.add_message(payload.conversation_id, sender="assistant", text=greeting_reply)
        await event_broker.publish_message(payload.conversation_id, reply_msg.model_dump())
        return SendMessageResponse(
            conversation_id=payload.conversation_id,
            user_message=user_msg,
            reply=reply_msg,
            is_mock=True,
            sources=[]
        )

    # 6. Format message history for RAG / LLM knowledge retrieval
    history = []
    for m in conv["messages"][:-1]:
        role = "assistant" if m.sender in ["assistant", "agent"] else "user"
        history.append({"role": role, "content": m.text})

    llm_reply, is_mock, sources = await llm_service.get_response(payload.message, history=history[-6:])
    
    # 7. Save AI reply to MongoDB
    reply_msg = store.add_message(payload.conversation_id, sender="assistant", text=llm_reply)

    # Publish AI reply via SSE
    await event_broker.publish_message(payload.conversation_id, reply_msg.model_dump())

    return SendMessageResponse(
        conversation_id=payload.conversation_id,
        user_message=user_msg,
        reply=reply_msg,
        is_mock=is_mock,
        sources=sources
    )

@api_router.get("/chat/{conversation_id}/messages")
def get_session_messages(conversation_id: str):
    """
    Public customer endpoint strictly scoped to the specific conversation ID.
    Never exposes other conversations or user data.
    """
    conv = store.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation session not found.")
    return {
        "conversation_id": conversation_id,
        "customer_name": conv["customer"].name,
        "status": conv["status"],
        "is_agent_handling": conv.get("is_agent_handling", False),
        "assigned_agent": conv.get("assigned_agent"),
        "issue_type": conv.get("issue_type"),
        "rating": conv.get("rating"),
        "feedback": conv.get("feedback"),
        "messages": conv["messages"]
    }

@api_router.post("/chat/{conversation_id}/handoff")
async def customer_handoff_to_team(
    conversation_id: str,
    issue_type: Optional[str] = Query(None),
    payload: Optional[dict] = None
):
    """
    Customer requests connection to a live human astrology advisor.
    Atomically updates status to 'waiting' and notifies the agent queue.
    """
    chosen_issue = (payload.get("issue_type") if payload else None) or issue_type or "Live Advisor Request"
    try:
        updated = store.request_handoff(conversation_id, issue_type=chosen_issue)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation session not found.")
    except SessionClosedError as err:
        raise HTTPException(status_code=400, detail=str(err))

    msg = store.add_message(
        conversation_id,
        sender="assistant",
        text=f"Your request has been sent to our AstroVed Support Team ({chosen_issue}). An advisor will join this consultation shortly."
    )

    # Publish events
    await event_broker.publish_message(conversation_id, msg.model_dump())
    await event_broker.publish_status_change(conversation_id, "waiting", None)
    analytics = store.get_analytics()
    await event_broker.publish_queue_update(
        waiting_count=analytics["waiting"],
        active_count=analytics["with_agent"],
        conversation_id=conversation_id,
        action="waiting"
    )

    return {"status": "success", "conversation_id": conversation_id, "message": msg}

@api_router.post("/chat/{conversation_id}/end")
async def customer_end_chat(conversation_id: str):
    """
    Customer concludes the consultation session.
    Closes the session in MongoDB and notifies agents.
    """
    try:
        store.close_conversation(conversation_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation session not found.")

    sys_msg = store.add_message(
        conversation_id,
        sender="system",
        text="Consultation session concluded. Thank you for connecting with AstroVed."
    )

    await event_broker.publish_message(conversation_id, sys_msg.model_dump())
    await event_broker.publish_status_change(conversation_id, "closed", None)
    analytics = store.get_analytics()
    await event_broker.publish_queue_update(
        waiting_count=analytics["waiting"],
        active_count=analytics["with_agent"],
        conversation_id=conversation_id,
        action="closed"
    )

    return {"status": "success", "conversation_id": conversation_id, "message": "Consultation ended."}

@api_router.post("/chat/{conversation_id}/rating", response_model=RatingSubmitResponse)
def submit_conversation_rating(
    conversation_id: str,
    payload: RatingSubmitRequest
):
    """
    Customer submits a 1-5 star rating and optional feedback upon ending the consultation.
    Persists to MongoDB and logs analytics event.
    """
    try:
        result = store.submit_rating(conversation_id, rating=payload.rating, feedback=payload.feedback)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation session not found.")

    return RatingSubmitResponse(
        status="success",
        conversation_id=conversation_id,
        rating=result["rating"],
        feedback=result.get("feedback"),
        already_submitted=result.get("already_submitted", False),
        message="Thank you! Your rating and feedback have been recorded." if not result.get("already_submitted") else "Rating already submitted. Thank you!"
    )

@api_router.get("/chat/{conversation_id}/events")
async def customer_events(conversation_id: str):
    """
    Customer real-time Server-Sent Events stream.
    Strictly isolated: customer receives events only for their own conversation.
    Includes keepalive heartbeats and automatic disconnect cleanup.
    """
    conv = store.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return EventSourceResponse(
        event_broker.customer_event_stream(conversation_id),
        ping=15
    )

# -----------------
# INTERNAL AGENT ENDPOINTS (Secured by Argon2id & Bearer JWT)
# -----------------

@api_router.post("/agent/login", response_model=AgentLoginResponse)
def agent_login(payload: AgentLoginRequest):
    """
    Agent login endpoint: validates credentials with Argon2id against MongoDB agents collection.
    Issues a signed JWT access token.
    Never exposes password hashes, passwords, or tokens.
    """
    username_input = payload.username.strip() if payload.username else ""
    password_input = payload.password

    if not username_input or not password_input:
        logger.warning("Agent login failed: empty username or password received.")
        raise HTTPException(status_code=400, detail="Username and password are required.")

    # 1. Lookup agent in MongoDB: exact match first, then case-insensitive fallback
    agents_col = get_agents_collection()
    agent = agents_col.find_one({"username": username_input})
    if not agent:
        import re
        agent = agents_col.find_one(
            {"username": {"$regex": f"^{re.escape(username_input)}$", "$options": "i"}}
        )

    if not agent:
        logger.warning(
            "Agent login diagnostic: username '%s' not found in database '%s'.",
            username_input,
            settings.MONGODB_DATABASE
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    canonical_username = agent.get("username", username_input)

    # 2. Check activation status
    if not agent.get("is_active", True):
        logger.warning("Agent login diagnostic: account for '%s' is deactivated (is_active=False).", canonical_username)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent account has been deactivated.",
        )

    # 3. Verify Argon2id password hash
    stored_hash = agent.get("password_hash")
    if not stored_hash:
        logger.warning("Agent login diagnostic: account for '%s' has no stored password_hash.", canonical_username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check password matching (supports exact password or trimmed fallback)
    is_valid = verify_password(password_input, stored_hash) or (
        password_input != password_input.strip() and verify_password(password_input.strip(), stored_hash)
    )

    if not is_valid:
        logger.warning("Agent login diagnostic: password verification failed for agent '%s'.", canonical_username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Success: issue signed JWT access token
    logger.info("Agent login successful: agent '%s' authenticated (role: %s).", canonical_username, agent.get("role", "advisor"))
    token = create_access_token(data={"sub": canonical_username, "role": agent.get("role", "advisor")})

    return AgentLoginResponse(
        success=True,
        token=token,
        display_name=agent.get("display_name", canonical_username),
        role=agent.get("role", "advisor")
    )

@api_router.get("/agent/conversations", response_model=list[ConversationSummary])
def list_agent_conversations(
    tab: str = Query("all"),
    search: Optional[str] = Query(None),
    current_agent: dict = Depends(get_current_agent)
):
    """
    Internal agent endpoint: lists queue conversations filtered by tab and optional search.
    Requires valid agent JWT bearer token.
    """
    return store.list_conversations(tab=tab, search=search)

@api_router.get("/agent/conversations/{conversation_id}", response_model=ConversationDetail)
def get_agent_conversation_detail(
    conversation_id: str,
    current_agent: dict = Depends(get_current_agent)
):
    """
    Internal agent endpoint: fetches complete conversation detail, user profile, and messages.
    Requires valid agent JWT bearer token.
    """
    conv = store.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conv

@api_router.post("/agent/conversations/{conversation_id}/claim")
async def claim_agent_conversation(
    conversation_id: str,
    current_agent: dict = Depends(get_current_agent)
):
    """
    Internal agent endpoint: atomically claims a waiting chat from the live queue.
    If another agent has already claimed it, returns 409 Conflict.
    Disables Claim Chat for all other agents and moves status to 'active'.
    """
    agent_name = current_agent.get("display_name", current_agent["username"])
    try:
        updated = store.claim_conversation(conversation_id, agent_name)
    except SessionConflictError as err:
        logger.warning("Claim conflict on %s: %s", conversation_id, err)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    # Save agent join message
    greeting = store.add_message(
        conversation_id,
        sender="agent",
        text=f"Namaste! I am {agent_name}. I have claimed your consultation and am reviewing your details."
    )

    # Publish real-time events to both customer and agent streams
    await event_broker.publish_message(conversation_id, greeting.model_dump())
    await event_broker.publish_status_change(conversation_id, "active", agent_name)
    analytics = store.get_analytics()
    await event_broker.publish_queue_update(
        waiting_count=analytics["waiting"],
        active_count=analytics["with_agent"],
        conversation_id=conversation_id,
        action="claimed"
    )

    return {
        "status": "success",
        "conversation_id": conversation_id,
        "assigned_agent": agent_name
    }

@api_router.post("/agent/conversations/{conversation_id}/reply")
async def agent_reply(
    conversation_id: str,
    payload: AgentReplyRequest,
    current_agent: dict = Depends(get_current_agent)
):
    """
    Internal agent endpoint: live human advisor sends reply to customer.
    Persists message in MongoDB and emits SSE to customer and agent streams.
    """
    conv = store.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    if conv.get("status") == "closed":
        raise HTTPException(status_code=400, detail="Cannot reply to a closed conversation.")

    if conv.get("status") != "active" or not conv.get("is_agent_handling", False):
        raise HTTPException(status_code=400, detail="Cannot reply to a conversation that is with the bot or not claimed by an agent.")

    # Save agent reply
    msg = store.add_message(conversation_id, sender="agent", text=payload.reply)

    # Broadcast via SSE
    await event_broker.publish_message(conversation_id, msg.model_dump())

    return {"status": "success", "message": msg}

@api_router.post("/agent/conversations/{conversation_id}/return-to-bot")
async def return_session_to_bot(
    conversation_id: str,
    current_agent: dict = Depends(get_current_agent)
):
    """
    Internal agent endpoint: returns active session to bot replies without closing the conversation.
    Clears agent assignment and sets status to 'bot_active'.
    """
    try:
        updated = store.return_to_bot(conversation_id)
    except SessionConflictError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    bot_note = store.add_message(
        conversation_id,
        sender="assistant",
        text="Your live session has been returned to our AstroVed AI guide. Feel free to continue asking astrological questions."
    )

    await event_broker.publish_message(conversation_id, bot_note.model_dump())
    await event_broker.publish_status_change(conversation_id, "bot_active", None)
    analytics = store.get_analytics()
    await event_broker.publish_queue_update(
        waiting_count=analytics["waiting"],
        active_count=analytics["with_agent"],
        conversation_id=conversation_id,
        action="returned_to_bot"
    )

    return {"status": "success", "conversation_id": conversation_id, "new_status": "bot_active"}

@api_router.post("/agent/conversations/{conversation_id}/close")
async def close_agent_conversation(
    conversation_id: str,
    current_agent: dict = Depends(get_current_agent)
):
    """
    Internal agent endpoint: closes/ends session. Rejects new messages from this point forward.
    """
    try:
        updated = store.close_conversation(conversation_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    agent_name = current_agent.get("display_name", current_agent["username"])
    close_msg = store.add_message(
        conversation_id,
        sender="system",
        text=f"Consultation concluded by advisor {agent_name}."
    )

    await event_broker.publish_message(conversation_id, close_msg.model_dump())
    await event_broker.publish_status_change(conversation_id, "closed", None)
    analytics = store.get_analytics()
    await event_broker.publish_queue_update(
        waiting_count=analytics["waiting"],
        active_count=analytics["with_agent"],
        conversation_id=conversation_id,
        action="closed"
    )

    return {"status": "success", "conversation_id": conversation_id, "new_status": "closed"}

@api_router.post("/agent/conversations/{conversation_id}/status")
async def update_conversation_status(
    conversation_id: str,
    status_query: Optional[str] = Query(None, alias="status"),
    payload: Optional[dict] = None,
    current_agent: dict = Depends(get_current_agent)
):
    """
    Internal agent endpoint: updates conversation lifecycle status (e.g. escalated, closed).
    """
    new_status = status_query or (payload.get("status") if payload else None)
    if not new_status:
        raise HTTPException(status_code=400, detail="Missing status parameter.")

    if new_status == "closed":
        return await close_agent_conversation(conversation_id, current_agent)

    try:
        success = store.update_status(conversation_id, new_status)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    except SessionConflictError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    await event_broker.publish_status_change(conversation_id, new_status, current_agent.get("display_name"))
    analytics = store.get_analytics()
    await event_broker.publish_queue_update(
        waiting_count=analytics["waiting"],
        active_count=analytics["with_agent"],
        conversation_id=conversation_id,
        action=new_status
    )

    return {"status": "success", "conversation_id": conversation_id, "new_status": new_status}

@api_router.get("/agent/analytics", response_model=AnalyticsResponse)
def get_analytics(current_agent: dict = Depends(get_current_agent)):
    """
    Internal agent endpoint: retrieves aggregated KPI metrics, top topics,
    status mix, and recent users directly from MongoDB data.
    Requires agent authorization.
    """
    return store.get_analytics()

@api_router.get("/agent/events")
async def agent_events(current_agent: dict = Depends(get_current_agent)):
    """
    Internal agent real-time Server-Sent Events stream.
    Requires agent authorization. Emits live queue updates, incoming customer messages,
    and status transitions.
    """
    return EventSourceResponse(
        event_broker.agent_event_stream(),
        ping=15
    )
