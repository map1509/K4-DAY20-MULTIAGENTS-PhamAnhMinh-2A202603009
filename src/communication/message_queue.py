"""In-memory async agent mailboxes and JSON-compatible communication log."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import uuid


class MessageQueue:
    def __init__(self):
        self.queues = {}
        self.message_log = []
        self._conditions = {}
        self._loop = None

    def register_agent(self, agent_name):
        if not isinstance(agent_name, str) or not agent_name:
            raise ValueError("agent_name must be a nonempty string")
        # Re-registering must not discard messages already waiting.
        self.queues.setdefault(agent_name, asyncio.Queue())

    def _condition(self, agent_name):
        if agent_name not in self.queues:
            raise ValueError(f"Agent {agent_name} not registered")
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            # Support sequential asyncio.run calls; active use is on one loop.
            self._conditions = {}
            self._loop = loop
        return self._conditions.setdefault(agent_name, asyncio.Condition())

    async def send_message(self, from_agent, to_agent, message):
        condition = self._condition(to_agent)
        if not isinstance(message, dict):
            raise ValueError("message must be a dict")
        envelope = deepcopy(message)
        envelope.update({"from": from_agent, "to": to_agent,
                         "timestamp": datetime.now(timezone.utc).isoformat(), "id": str(uuid.uuid4())})
        json.dumps(envelope, allow_nan=False)
        async with condition:
            self.message_log.append(deepcopy(envelope))
            await self.queues[to_agent].put(envelope)
            condition.notify_all()
        return envelope["id"]

    async def receive_message(self, agent_name, timeout=30, *, in_reply_to=None, message_id=None):
        """Receive FIFO or the reply/request with a specific correlation ID."""
        condition = self._condition(agent_name)
        async def receive():
            async with condition:
                while True:
                    mailbox = self.queues[agent_name]
                    selected = None
                    retained = []
                    while not mailbox.empty():
                        message = mailbox.get_nowait()
                        mailbox.task_done()
                        matches = ((in_reply_to is None or message.get("in_reply_to") == in_reply_to)
                                   and (message_id is None or message.get("id") == message_id))
                        if selected is None and matches:
                            selected = message
                        else:
                            retained.append(message)
                    for message in retained:
                        mailbox.put_nowait(message)
                    if selected is not None:
                        return selected
                    await condition.wait()
        try:
            return await asyncio.wait_for(receive(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"No message for {agent_name} within {timeout}s") from exc

    def get_message_log(self, agent_name=None):
        messages = self.message_log
        if agent_name is not None:
            messages = [m for m in messages if m["from"] == agent_name or m["to"] == agent_name]
        return deepcopy(messages)
