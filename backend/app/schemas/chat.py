from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr

class CustomerLead(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    mobile: str = Field(..., min_length=7, max_length=20)
    topic_of_interest: Optional[str] = "Vedic Astrology & Remedies"

class MessageItem(BaseModel):
    id: str
    sender: Literal["user", "assistant", "agent", "system"]
    text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StartChatRequest(BaseModel):
    name: str
    email: EmailStr
    mobile: str
    initial_query: Optional[str] = None
    topic_of_interest: Optional[str] = "General Vedic Astrology"

class StartChatResponse(BaseModel):
    conversation_id: str
    welcome_message: str
    customer: CustomerLead

class SendMessageRequest(BaseModel):
    conversation_id: str
    message: str

class SendMessageResponse(BaseModel):
    conversation_id: str
    user_message: MessageItem
    reply: MessageItem
    is_mock: bool = False

class AgentReplyRequest(BaseModel):
    reply: str
    agent_name: Optional[str] = "Astrology Advisor"

class ConversationSummary(BaseModel):
    conversation_id: str
    customer: CustomerLead
    created_at: datetime
    updated_at: datetime
    status: Literal["active", "escalated", "resolved"]
    messages_count: int
    last_message: Optional[str] = None
    is_agent_handling: bool = False
