import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pymongo import ReturnDocument, DESCENDING, ASCENDING
from app.core.database import (
    get_sessions_collection,
    get_messages_collection,
    get_analytics_collection,
    check_mongo_connection,
    init_db_indexes
)
from app.schemas.chat import (
    CustomerLead,
    MessageItem,
    ConversationSummary,
    IssueTypeMetric,
    StatusMixMetric,
    RecentUserRecord,
    AnalyticsResponse
)

logger = logging.getLogger(__name__)

# Allowed lifecycle states
ALLOWED_STATUSES = {"bot_active", "waiting", "active", "escalated", "closed"}

# Allowed state transitions
ALLOWED_TRANSITIONS = {
    "bot_active": {"waiting", "closed"},
    "waiting": {"active", "bot_active", "closed"},
    "active": {"escalated", "bot_active", "closed"},
    "escalated": {"active", "bot_active", "closed"},
    "closed": set(),  # Terminal state: cannot transition out
}

class SessionConflictError(Exception):
    """Raised when an atomic claim or state transition conflicts with current session state."""
    pass

class SessionNotFoundError(Exception):
    """Raised when a requested session is not found in the database."""
    pass

class SessionClosedError(Exception):
    """Raised when attempting to post a message to an already closed session."""
    pass

class MongoConversationStore:
    def __init__(self):
        # Verify MongoDB connectivity on initialization; fail fast if unavailable
        check_mongo_connection()
        init_db_indexes()

    def create_conversation(self, customer: CustomerLead, initial_query: Optional[str] = None) -> str:
        """
        Creates a new customer conversation session in MongoDB.
        Status begins as 'waiting' if an initial query requests human support, else 'bot_active'.
        """
        conv_id = f"ast_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        
        # Determine initial status
        initial_status = "bot_active"
        if initial_query and any(w in initial_query.lower() for w in ["agent", "human", "advisor", "support", "help"]):
            initial_status = "waiting"

        session_doc = {
            "conversation_id": conv_id,
            "customer": customer.model_dump(),
            "created_at": now,
            "updated_at": now,
            "status": initial_status,
            "is_agent_handling": False,
            "assigned_agent": None,
            "issue_type": customer.topic_of_interest or "General Vedic Astrology",
            "messages_count": 0,
            "last_message": None
        }

        sessions_col = get_sessions_collection()
        sessions_col.insert_one(session_doc)

        # 1. Welcome greeting message
        welcome_text = (
            f"Namaste {customer.name}! Welcome to AstroVed. I am your Vedic AI Astrology guide. "
            f"How may I assist your life path, birth chart queries, or remedies today?"
        )
        self.add_message(conv_id, sender="assistant", text=welcome_text)

        # 2. Initial query if supplied
        if initial_query:
            self.add_message(conv_id, sender="user", text=initial_query)

        # Log analytics event
        analytics_col = get_analytics_collection()
        analytics_col.insert_one({
            "event_type": "session_created",
            "conversation_id": conv_id,
            "initial_status": initial_status,
            "topic": customer.topic_of_interest,
            "timestamp": now
        })

        logger.info("Created new customer session: %s (status: %s)", conv_id, initial_status)
        return conv_id

    def get_conversation(self, conv_id: str) -> Optional[dict]:
        """
        Retrieves complete conversation detail: session metadata and all chronologically ordered messages.
        """
        sessions_col = get_sessions_collection()
        session = sessions_col.find_one({"conversation_id": conv_id}, {"_id": 0})
        if not session:
            return None

        messages_col = get_messages_collection()
        messages_cursor = messages_col.find({"conversation_id": conv_id}, {"_id": 0}).sort("timestamp", ASCENDING)
        messages = [MessageItem(**m) for m in messages_cursor]

        session["messages"] = messages
        session["customer"] = CustomerLead(**session["customer"])
        return session

    def add_message(self, conv_id: str, sender: str, text: str) -> MessageItem:
        """
        Persists a message to the database before publishing any events.
        Rejects messages if the conversation is closed.
        """
        sessions_col = get_sessions_collection()
        session = sessions_col.find_one({"conversation_id": conv_id})
        if not session:
            raise SessionNotFoundError(f"Conversation {conv_id} not found.")

        if session.get("status") == "closed" and sender != "system":
            raise SessionClosedError(f"Conversation {conv_id} is closed. New messages cannot be accepted.")

        now = datetime.now(timezone.utc)
        msg_id = f"msg_{uuid.uuid4().hex[:10]}"

        msg_doc = {
            "id": msg_id,
            "conversation_id": conv_id,
            "sender": sender,
            "text": text,
            "timestamp": now
        }

        messages_col = get_messages_collection()
        messages_col.insert_one(msg_doc)

        # Update session timestamp and preview
        sessions_col.update_one(
            {"conversation_id": conv_id},
            {
                "$set": {"updated_at": now, "last_message": text},
                "$inc": {"messages_count": 1}
            }
        )

        # Log analytics event
        analytics_col = get_analytics_collection()
        analytics_col.insert_one({
            "event_type": "message_sent",
            "conversation_id": conv_id,
            "sender": sender,
            "timestamp": now
        })

        return MessageItem(id=msg_id, sender=sender, text=text, timestamp=now)

    def list_conversations(self, tab: str = "all", search: Optional[str] = None) -> List[ConversationSummary]:
        """
        Lists conversations for agent dashboard queue with tab filters and optional search query.
        """
        query: Dict[str, Any] = {}
        tab = tab.lower()
        if tab == "waiting":
            query["status"] = "waiting"
        elif tab in ["with_agent", "active"]:
            query["status"] = {"$in": ["active", "with_agent", "escalated"]}
        elif tab in ["closed", "history"]:
            query["status"] = {"$in": ["closed", "resolved"]}

        if search:
            regex_q = {"$regex": search.strip(), "$options": "i"}
            query["$or"] = [
                {"customer.name": regex_q},
                {"customer.email": regex_q},
                {"customer.mobile": regex_q},
                {"conversation_id": regex_q},
                {"last_message": regex_q}
            ]

        sessions_col = get_sessions_collection()
        cursor = sessions_col.find(query, {"_id": 0}).sort("updated_at", DESCENDING)

        summaries = []
        for s in cursor:
            # Map legacy status strings to canonical schema
            display_status = s.get("status", "bot_active")
            if display_status == "active":
                display_status = "with_agent"
            elif display_status == "closed":
                display_status = "closed"

            summaries.append(
                ConversationSummary(
                    conversation_id=s["conversation_id"],
                    customer=CustomerLead(**s["customer"]),
                    created_at=s["created_at"],
                    updated_at=s["updated_at"],
                    status=display_status,
                    messages_count=s.get("messages_count", 0),
                    last_message=s.get("last_message"),
                    is_agent_handling=s.get("is_agent_handling", False),
                    assigned_agent=s.get("assigned_agent"),
                    issue_type=s.get("issue_type", "General Vedic Astrology"),
                    rating=s.get("rating"),
                    feedback=s.get("feedback")
                )
            )
        return summaries

    def claim_conversation(self, conv_id: str, agent_name: str) -> dict:
        """
        Atomic claim: only one agent can claim a waiting session.
        If another agent already claimed it or it is not waiting, raises SessionConflictError.
        """
        now = datetime.now(timezone.utc)
        sessions_col = get_sessions_collection()

        # Atomic find_one_and_update
        updated = sessions_col.find_one_and_update(
            {"conversation_id": conv_id, "status": "waiting"},
            {
                "$set": {
                    "status": "active",
                    "assigned_agent": agent_name,
                    "is_agent_handling": True,
                    "updated_at": now
                }
            },
            return_document=ReturnDocument.AFTER
        )

        if not updated:
            existing = sessions_col.find_one({"conversation_id": conv_id})
            if not existing:
                raise SessionNotFoundError(f"Conversation {conv_id} not found.")
            assigned = existing.get("assigned_agent")
            status = existing.get("status")
            raise SessionConflictError(
                f"Session cannot be claimed. Status is '{status}', assigned to '{assigned or 'none'}'."
            )

        # Log lifecycle event
        analytics_col = get_analytics_collection()
        analytics_col.insert_one({
            "event_type": "session_claimed",
            "conversation_id": conv_id,
            "agent": agent_name,
            "timestamp": now
        })

        logger.info("Agent '%s' atomically claimed session %s", agent_name, conv_id)
        return updated

    def return_to_bot(self, conv_id: str) -> dict:
        """
        Returns an active or escalated session back to the bot.
        Clears agent assignment without closing the session.
        """
        now = datetime.now(timezone.utc)
        sessions_col = get_sessions_collection()

        updated = sessions_col.find_one_and_update(
            {"conversation_id": conv_id, "status": {"$in": ["active", "with_agent", "escalated"]}},
            {
                "$set": {
                    "status": "bot_active",
                    "assigned_agent": None,
                    "is_agent_handling": False,
                    "updated_at": now
                }
            },
            return_document=ReturnDocument.AFTER
        )

        if not updated:
            existing = sessions_col.find_one({"conversation_id": conv_id})
            if not existing:
                raise SessionNotFoundError(f"Conversation {conv_id} not found.")
            raise SessionConflictError(
                f"Cannot return session to bot. Current status is '{existing.get('status')}'."
            )

        analytics_col = get_analytics_collection()
        analytics_col.insert_one({
            "event_type": "returned_to_bot",
            "conversation_id": conv_id,
            "timestamp": now
        })

        logger.info("Returned session %s to bot", conv_id)
        return updated

    def close_conversation(self, conv_id: str) -> dict:
        """
        Closes/ends a session. Rejects new messages from this point forward.
        """
        now = datetime.now(timezone.utc)
        sessions_col = get_sessions_collection()

        updated = sessions_col.find_one_and_update(
            {"conversation_id": conv_id, "status": {"$ne": "closed"}},
            {
                "$set": {
                    "status": "closed",
                    "is_agent_handling": False,
                    "updated_at": now
                }
            },
            return_document=ReturnDocument.AFTER
        )

        if not updated:
            existing = sessions_col.find_one({"conversation_id": conv_id})
            if not existing:
                raise SessionNotFoundError(f"Conversation {conv_id} not found.")
            # Already closed
            return existing

        analytics_col = get_analytics_collection()
        analytics_col.insert_one({
            "event_type": "session_closed",
            "conversation_id": conv_id,
            "timestamp": now
        })

        logger.info("Closed session %s", conv_id)
        return updated

    def request_handoff(self, conv_id: str, issue_type: Optional[str] = None) -> dict:
        """
        Customer requests connection to a human astrology advisor.
        Moves status to 'waiting' and updates issue_type.
        """
        now = datetime.now(timezone.utc)
        sessions_col = get_sessions_collection()

        set_fields: Dict[str, Any] = {
            "status": "waiting",
            "is_agent_handling": False,
            "updated_at": now
        }
        if issue_type:
            set_fields["issue_type"] = issue_type

        updated = sessions_col.find_one_and_update(
            {"conversation_id": conv_id, "status": {"$ne": "closed"}},
            {"$set": set_fields},
            return_document=ReturnDocument.AFTER
        )

        if not updated:
            existing = sessions_col.find_one({"conversation_id": conv_id})
            if not existing:
                raise SessionNotFoundError(f"Conversation {conv_id} not found.")
            raise SessionClosedError(f"Cannot request handoff on closed conversation {conv_id}.")

        analytics_col = get_analytics_collection()
        analytics_col.insert_one({
            "event_type": "handoff_requested",
            "conversation_id": conv_id,
            "issue_type": issue_type or updated.get("issue_type", "General Vedic Astrology"),
            "timestamp": now
        })

        logger.info("Handoff requested for session %s (status -> waiting, issue: %s)", conv_id, issue_type)
        return updated

    def update_status(self, conv_id: str, status: str, is_agent: Optional[bool] = None) -> bool:
        """
        Generic status update helper honoring allowed statuses and transition rules.
        """
        if status not in ALLOWED_STATUSES and status not in ["with_agent", "resolved"]:
            raise ValueError(f"Invalid status: '{status}'. Allowed: {ALLOWED_STATUSES}")

        canonical_status = status
        if status == "with_agent":
            canonical_status = "active"
        elif status == "resolved":
            canonical_status = "closed"

        sessions_col = get_sessions_collection()
        current = sessions_col.find_one({"conversation_id": conv_id})
        if not current:
            raise SessionNotFoundError(f"Conversation {conv_id} not found.")

        current_status = current.get("status", "bot_active")
        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if canonical_status != current_status and canonical_status not in allowed:
            raise SessionConflictError(
                f"Invalid transition from '{current_status}' to '{canonical_status}'. Allowed transitions: {sorted(allowed)}"
            )

        now = datetime.now(timezone.utc)
        update_fields: Dict[str, Any] = {
            "status": canonical_status,
            "updated_at": now
        }
        if is_agent is not None:
            update_fields["is_agent_handling"] = is_agent
        if canonical_status == "closed":
            update_fields["is_agent_handling"] = False

        res = sessions_col.update_one({"conversation_id": conv_id}, {"$set": update_fields})

        # Record analytics event
        analytics_col = get_analytics_collection()
        analytics_col.insert_one({
            "event_type": "status_changed",
            "conversation_id": conv_id,
            "old_status": current_status,
            "new_status": canonical_status,
            "timestamp": now
        })

        return res.matched_count > 0

    def get_analytics(self) -> dict:
        """
        Calculates all dashboard KPIs and aggregations directly from MongoDB collections.
        """
        sessions_col = get_sessions_collection()
        messages_col = get_messages_collection()

        total = sessions_col.count_documents({})
        waiting = sessions_col.count_documents({"status": "waiting"})
        with_agent = sessions_col.count_documents({"status": {"$in": ["active", "with_agent"]}})
        escalated = sessions_col.count_documents({"status": "escalated"})
        resolved = sessions_col.count_documents({"status": {"$in": ["closed", "resolved"]}})
        bot_handled = sessions_col.count_documents({"is_agent_handling": False, "assigned_agent": None})

        # Calculate average response time over actual user->reply message pairs
        # Find consecutive user and assistant/agent messages
        pipeline_pairs = [
            {"$sort": {"conversation_id": 1, "timestamp": 1}},
            {"$group": {
                "_id": "$conversation_id",
                "msgs": {"$push": {"sender": "$sender", "time": "$timestamp"}}
            }}
        ]
        
        deltas = []
        for group in messages_col.aggregate(pipeline_pairs):
            msgs = group.get("msgs", [])
            for i in range(len(msgs) - 1):
                m_current = msgs[i]
                m_next = msgs[i + 1]
                if m_current.get("sender") == "user" and m_next.get("sender") in ["assistant", "agent"]:
                    t1 = m_current.get("time")
                    t2 = m_next.get("time")
                    if isinstance(t1, datetime) and isinstance(t2, datetime):
                        delta_sec = (t2 - t1).total_seconds()
                        if 0 <= delta_sec < 86400:  # Reasonable range
                            deltas.append(delta_sec)

        avg_response_time = round(sum(deltas) / len(deltas), 1) if deltas else 0.0

        # Top issues aggregation
        pipeline_issues = [
            {"$group": {"_id": "$issue_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        top_issues = []
        for doc in sessions_col.aggregate(pipeline_issues):
            name = doc["_id"] or "General Vedic Astrology"
            cnt = doc["count"]
            pct = int((cnt / total * 100)) if total else 0
            top_issues.append({"name": name, "count": cnt, "pct": pct})

        status_mix = [
            {"status": "Waiting", "count": waiting, "color": "#F2B84B"},
            {"status": "With Agent", "count": with_agent, "color": "#22C55E"},
            {"status": "Escalated", "count": escalated, "color": "#A855F7"},
            {"status": "Resolved", "count": resolved, "color": "#38BDF8"},
        ]

        # Recent 10 users with safe metadata
        recent_users = []
        for s in sessions_col.find({}, {"_id": 0}).sort("updated_at", DESCENDING).limit(10):
            cust = s.get("customer", {})
            created = s.get("created_at")
            date_str = created.strftime("%Y-%m-%d %H:%M") if isinstance(created, datetime) else str(created)
            recent_users.append({
                "name": cust.get("name", "Seeker"),
                "email": cust.get("email", ""),
                "phone": cust.get("mobile", ""),
                "status": s.get("status", "bot_active").capitalize(),
                "issue": s.get("issue_type", "General Vedic Astrology"),
                "date": date_str
            })

        return {
            "total_sessions": total,
            "resolved": resolved,
            "waiting": waiting,
            "with_agent": with_agent,
            "escalated": escalated,
            "bot_handled": bot_handled,
            "avg_response_time_seconds": avg_response_time,
            "top_issues": top_issues,
            "status_mix": status_mix,
            "recent_users": recent_users
        }

    def submit_rating(self, conv_id: str, rating: int, feedback: Optional[str] = None) -> dict:
        """
        Saves customer 5-star rating (1-5) and optional feedback to MongoDB.
        Associates with the session and analytics_events.
        Prevents duplicate rating updates if already rated.
        """
        sessions_col = get_sessions_collection()
        conv = sessions_col.find_one({"conversation_id": conv_id})
        if not conv:
            raise SessionNotFoundError(f"Conversation {conv_id} not found.")

        # If already rated, return existing rating without overwriting
        if conv.get("rating") is not None:
            return {
                "already_submitted": True,
                "rating": conv["rating"],
                "feedback": conv.get("feedback")
            }

        now = datetime.now(timezone.utc)
        clean_feedback = feedback.strip() if feedback else None

        sessions_col.update_one(
            {"conversation_id": conv_id},
            {
                "$set": {
                    "rating": rating,
                    "feedback": clean_feedback,
                    "rated_at": now,
                    "updated_at": now
                }
            }
        )

        analytics_col = get_analytics_collection()
        analytics_col.insert_one({
            "event_type": "customer_rating",
            "conversation_id": conv_id,
            "rating": rating,
            "feedback": clean_feedback,
            "timestamp": now
        })

        logger.info("Customer rating %d saved for conversation %s", rating, conv_id)
        return {
            "already_submitted": False,
            "rating": rating,
            "feedback": clean_feedback
        }

store = MongoConversationStore()
