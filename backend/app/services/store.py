import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.schemas.chat import CustomerLead, MessageItem, ConversationSummary

class ConversationStore:
    def __init__(self):
        # In-memory storage for active sessions (MongoDB-ready abstraction)
        self.conversations: Dict[str, dict] = {}

    def create_conversation(self, customer: CustomerLead, initial_query: Optional[str] = None) -> str:
        conv_id = f"ast_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc)
        
        initial_messages = [
            MessageItem(
                id=f"msg_{uuid.uuid4().hex[:8]}",
                sender="assistant",
                text=f"Namaste {customer.name}! Welcome to AstroVed. I am your Vedic AI Astrology guide. How may I assist your life path, birth chart queries, or remedies today?",
                timestamp=now
            )
        ]

        if initial_query:
            initial_messages.append(
                MessageItem(
                    id=f"msg_{uuid.uuid4().hex[:8]}",
                    sender="user",
                    text=initial_query,
                    timestamp=now
                )
            )

        self.conversations[conv_id] = {
            "conversation_id": conv_id,
            "customer": customer,
            "created_at": now,
            "updated_at": now,
            "status": "active",
            "is_agent_handling": False,
            "messages": initial_messages
        }
        return conv_id

    def get_conversation(self, conv_id: str) -> Optional[dict]:
        return self.conversations.get(conv_id)

    def add_message(self, conv_id: str, sender: str, text: str) -> Optional[MessageItem]:
        conv = self.conversations.get(conv_id)
        if not conv:
            return None
        
        msg = MessageItem(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            sender=sender, # "user", "assistant", "agent"
            text=text,
            timestamp=datetime.now(timezone.utc)
        )
        conv["messages"].append(msg)
        conv["updated_at"] = msg.timestamp
        return msg

    def list_conversations(self) -> List[ConversationSummary]:
        summaries = []
        for cid, conv in sorted(self.conversations.items(), key=lambda x: x[1]["updated_at"], reverse=True):
            last_text = conv["messages"][-1].text if conv["messages"] else None
            summaries.append(
                ConversationSummary(
                    conversation_id=cid,
                    customer=conv["customer"],
                    created_at=conv["created_at"],
                    updated_at=conv["updated_at"],
                    status=conv["status"],
                    messages_count=len(conv["messages"]),
                    last_message=last_text,
                    is_agent_handling=conv.get("is_agent_handling", False)
                )
            )
        return summaries

    def update_status(self, conv_id: str, status: str, is_agent: Optional[bool] = None) -> bool:
        conv = self.conversations.get(conv_id)
        if not conv:
            return False
        conv["status"] = status
        if is_agent is not None:
            conv["is_agent_handling"] = is_agent
        conv["updated_at"] = datetime.now(timezone.utc)
        return True

store = ConversationStore()
