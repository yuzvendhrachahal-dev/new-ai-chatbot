from datetime import datetime, timezone
from typing import Optional, Literal, List, Dict, Any
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
    welcome_message_id: Optional[str] = None
    customer: CustomerLead

class SendMessageRequest(BaseModel):
    conversation_id: str
    message: str = Field(..., min_length=1, max_length=3000)

class SendMessageResponse(BaseModel):
    conversation_id: str
    user_message: MessageItem
    reply: Optional[MessageItem] = None
    is_mock: bool = False
    sources: Optional[List[Dict[str, Any]]] = None

class AgentReplyRequest(BaseModel):
    reply: str = Field(..., min_length=1, max_length=4000)

class RatingSubmitRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    feedback: Optional[str] = Field(None, max_length=2000)

class RatingSubmitResponse(BaseModel):
    status: str = "success"
    success: bool = True
    conversation_id: str
    rating: int
    feedback: Optional[str] = None
    already_submitted: bool = False
    message: str = "Thank you for your rating and feedback!"

class ConversationSummary(BaseModel):
    conversation_id: str
    customer: CustomerLead
    created_at: datetime
    updated_at: datetime
    status: str = "bot_active"
    messages_count: int
    last_message: Optional[str] = None
    is_agent_handling: bool = False
    assigned_agent: Optional[str] = None
    issue_type: Optional[str] = "General Vedic Astrology"
    rating: Optional[int] = None
    feedback: Optional[str] = None

class ConversationDetail(BaseModel):
    conversation_id: str
    customer: CustomerLead
    created_at: datetime
    updated_at: datetime
    status: str
    messages_count: int = 0
    last_message: Optional[str] = None
    is_agent_handling: bool = False
    assigned_agent: Optional[str] = None
    issue_type: Optional[str] = "General Vedic Astrology"
    rating: Optional[int] = None
    feedback: Optional[str] = None
    messages: List[MessageItem] = []

class AgentLoginRequest(BaseModel):
    username: str
    password: str

class AgentLoginResponse(BaseModel):
    success: bool
    token: str
    display_name: str
    role: str = "advisor"

class IssueTypeMetric(BaseModel):
    name: str
    count: int
    pct: int

class StatusMixMetric(BaseModel):
    status: str
    count: int
    color: str

class RecentUserRecord(BaseModel):
    name: str
    email: str
    phone: str
    status: str
    issue: str
    date: str

class AnalyticsResponse(BaseModel):
    total_sessions: int
    resolved: int
    waiting: int
    with_agent: int
    escalated: int = 0
    bot_handled: int = 0
    avg_response_time_seconds: float = 0.0
    top_issues: List[IssueTypeMetric]
    status_mix: List[StatusMixMetric]
    recent_users: List[RecentUserRecord]
