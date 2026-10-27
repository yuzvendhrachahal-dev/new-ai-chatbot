import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Set, Any, AsyncGenerator
from sse_starlette.sse import ServerSentEvent

logger = logging.getLogger(__name__)

class EventBroker:
    """
    In-memory Pub-Sub broker for Server-Sent Events (SSE).
    Provides strict isolation between customer session channels and agent channels.
    """
    def __init__(self):
        # conversation_id -> set of asyncio.Queue
        self._customer_queues: Dict[str, Set[asyncio.Queue]] = {}
        # set of asyncio.Queue for authorized agents
        self._agent_queues: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def register_customer(self, conversation_id: str) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            if conversation_id not in self._customer_queues:
                self._customer_queues[conversation_id] = set()
            self._customer_queues[conversation_id].add(queue)
        logger.debug("Customer client registered for conversation %s", conversation_id)
        return queue

    async def unregister_customer(self, conversation_id: str, queue: asyncio.Queue):
        async with self._lock:
            if conversation_id in self._customer_queues:
                self._customer_queues[conversation_id].discard(queue)
                if not self._customer_queues[conversation_id]:
                    del self._customer_queues[conversation_id]
        logger.debug("Customer client disconnected from conversation %s", conversation_id)

    async def register_agent(self) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._agent_queues.add(queue)
        logger.debug("Agent client registered to live queue stream")
        return queue

    async def unregister_agent(self, queue: asyncio.Queue):
        async with self._lock:
            self._agent_queues.discard(queue)
        logger.debug("Agent client disconnected from live queue stream")

    async def broadcast_to_customer(self, conversation_id: str, event_type: str, data: Any):
        payload = ServerSentEvent(
            event=event_type,
            data=json.dumps(data, default=str),
            id=str(int(datetime.now(timezone.utc).timestamp() * 1000))
        )
        async with self._lock:
            queues = list(self._customer_queues.get(conversation_id, []))

        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning("Customer queue full for %s, skipping event", conversation_id)

    async def broadcast_to_agents(self, event_type: str, data: Any):
        payload = ServerSentEvent(
            event=event_type,
            data=json.dumps(data, default=str),
            id=str(int(datetime.now(timezone.utc).timestamp() * 1000))
        )
        async with self._lock:
            queues = list(self._agent_queues)

        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning("Agent queue full, skipping event")

    async def publish_message(self, conversation_id: str, message: dict):
        event_data = {
            "conversation_id": conversation_id,
            "message": message
        }
        # Send to the specific customer
        await self.broadcast_to_customer(conversation_id, "message", event_data)
        # Send to all connected agents
        await self.broadcast_to_agents("message", event_data)

    async def publish_status_change(self, conversation_id: str, status: str, assigned_agent: Any = None):
        event_data = {
            "conversation_id": conversation_id,
            "status": status,
            "assigned_agent": assigned_agent
        }
        await self.broadcast_to_customer(conversation_id, "status_change", event_data)
        await self.broadcast_to_agents("status_change", event_data)

    async def publish_queue_update(self, waiting_count: int, active_count: int, conversation_id: str, action: str):
        event_data = {
            "waiting_count": waiting_count,
            "active_count": active_count,
            "conversation_id": conversation_id,
            "action": action
        }
        await self.broadcast_to_agents("queue_update", event_data)

    async def customer_event_stream(self, conversation_id: str) -> AsyncGenerator[ServerSentEvent, None]:
        queue = await self.register_customer(conversation_id)
        try:
            # Yield initial connection confirmation
            yield ServerSentEvent(
                event="connected",
                data=json.dumps({"status": "connected", "conversation_id": conversation_id})
            )
            while True:
                try:
                    # Wait up to 15 seconds for an event; send heartbeat if timeout
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield event
                except asyncio.TimeoutError:
                    yield ServerSentEvent(
                        event="heartbeat",
                        data=json.dumps({"timestamp": datetime.now(timezone.utc).isoformat()})
                    )
        except asyncio.CancelledError:
            pass
        finally:
            await self.unregister_customer(conversation_id, queue)

    async def agent_event_stream(self) -> AsyncGenerator[ServerSentEvent, None]:
        queue = await self.register_agent()
        try:
            yield ServerSentEvent(
                event="connected",
                data=json.dumps({"status": "connected", "stream": "agent_live_queue"})
            )
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield event
                except asyncio.TimeoutError:
                    yield ServerSentEvent(
                        event="heartbeat",
                        data=json.dumps({"timestamp": datetime.now(timezone.utc).isoformat()})
                    )
        except asyncio.CancelledError:
            pass
        finally:
            await self.unregister_agent(queue)

event_broker = EventBroker()
