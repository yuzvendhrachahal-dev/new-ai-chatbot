import logging
from typing import Optional
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from app.core.config import settings

logger = logging.getLogger(__name__)

_mongo_client: Optional[MongoClient] = None

def get_mongo_client(uri: Optional[str] = None) -> MongoClient:
    global _mongo_client
    if _mongo_client is None:
        target_uri = uri or settings.MONGODB_URI
        if not target_uri:
            raise RuntimeError("MONGODB_URI environment variable is not configured.")
        try:
            _mongo_client = MongoClient(
                target_uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                maxPoolSize=50,
                uuidRepresentation="standard"
            )
            # Verify connectivity immediately
            _mongo_client.admin.command("ping")
            logger.info("Successfully connected to MongoDB at %s", target_uri)
        except (ConnectionFailure, ServerSelectionTimeoutError) as err:
            _mongo_client = None
            raise RuntimeError(f"MongoDB connection failed: {err}") from err
    return _mongo_client

def get_database(db_name: Optional[str] = None) -> Database:
    client = get_mongo_client()
    target_name = db_name or settings.MONGODB_DATABASE
    return client[target_name]

def check_mongo_connection() -> dict:
    """
    Checks MongoDB connection health.
    Returns details if healthy, raises RuntimeError if unavailable.
    """
    try:
        client = get_mongo_client()
        res = client.admin.command("ping")
        return {
            "status": "connected",
            "database": settings.MONGODB_DATABASE,
            "ping": res.get("ok", 1.0)
        }
    except Exception as err:
        raise RuntimeError(f"MongoDB health check failed: {err}") from err

def init_db_indexes(db: Optional[Database] = None) -> dict:
    """
    Initializes all necessary indexes for collections:
    - sessions
    - messages
    - agents
    - knowledge_documents
    - analytics_events
    """
    if db is None:
        db = get_database()
        
    created = {}

    # 1. sessions
    sessions_col = db["sessions"]
    sessions_col.create_index([("conversation_id", ASCENDING)], unique=True, name="idx_conv_id_unique")
    sessions_col.create_index([("status", ASCENDING)], name="idx_status")
    sessions_col.create_index([("assigned_agent", ASCENDING)], name="idx_assigned_agent")
    sessions_col.create_index([("updated_at", DESCENDING)], name="idx_updated_at")
    sessions_col.create_index([("created_at", DESCENDING)], name="idx_created_at")
    created["sessions"] = [idx["name"] for idx in sessions_col.list_indexes()]

    # 2. messages
    messages_col = db["messages"]
    messages_col.create_index([("id", ASCENDING)], unique=True, name="idx_msg_id_unique")
    messages_col.create_index([("conversation_id", ASCENDING), ("timestamp", ASCENDING)], name="idx_conv_time")
    created["messages"] = [idx["name"] for idx in messages_col.list_indexes()]

    # 3. agents
    agents_col = db["agents"]
    agents_col.create_index([("username", ASCENDING)], unique=True, name="idx_username_unique")
    agents_col.create_index([("is_active", ASCENDING)], name="idx_is_active")
    created["agents"] = [idx["name"] for idx in agents_col.list_indexes()]

    # 4. knowledge_documents
    knowledge_col = db["knowledge_documents"]
    knowledge_col.create_index([("document_id", ASCENDING)], unique=True, name="idx_doc_id_unique")
    knowledge_col.create_index([("source", ASCENDING)], name="idx_source")
    knowledge_col.create_index([("tags", ASCENDING)], name="idx_tags")
    # Text index for keyword retrieval fallback
    try:
        knowledge_col.create_index(
            [("title", TEXT), ("content", TEXT), ("tags", TEXT)],
            name="idx_knowledge_text",
            weights={"title": 5, "tags": 3, "content": 1}
        )
    except Exception as err:
        logger.warning("Text index creation notice: %s", err)
    created["knowledge_documents"] = [idx["name"] for idx in knowledge_col.list_indexes()]

    # 5. analytics_events
    analytics_col = db["analytics_events"]
    analytics_col.create_index([("event_type", ASCENDING), ("timestamp", DESCENDING)], name="idx_event_type_time")
    analytics_col.create_index([("conversation_id", ASCENDING), ("timestamp", DESCENDING)], name="idx_conv_time_analytics")
    created["analytics_events"] = [idx["name"] for idx in analytics_col.list_indexes()]

    logger.info("MongoDB indexes successfully created/verified for all collections.")
    return created

# Collection accessors
def get_sessions_collection(db: Optional[Database] = None):
    return (db or get_database())["sessions"]

def get_messages_collection(db: Optional[Database] = None):
    return (db or get_database())["messages"]

def get_agents_collection(db: Optional[Database] = None):
    return (db or get_database())["agents"]

def get_knowledge_collection(db: Optional[Database] = None):
    return (db or get_database())["knowledge_documents"]

def get_analytics_collection(db: Optional[Database] = None):
    return (db or get_database())["analytics_events"]
