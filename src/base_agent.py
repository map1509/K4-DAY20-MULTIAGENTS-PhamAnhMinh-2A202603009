"""Common worker contract used by the coordinator."""
from abc import ABC, abstractmethod
import logging


class BaseAgent(ABC):
    """Workers return {type: data/code/evaluation, content: ...}.

    Implementations must use nonblocking async operations and propagate
    cancellation so the coordinator can enforce its deadline.
    """

    def __init__(self, name, model=None, system_prompt="", tools=None):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Agent name must be a nonempty string")
        self.name = name
        self.model = model
        self.system_prompt = system_prompt
        self.tools = list(tools) if tools is not None else []
        self.logger = logging.getLogger(name)

    @abstractmethod
    async def process_async(self, content):
        """Process a delegated request and return a typed result mapping."""
        raise NotImplementedError
