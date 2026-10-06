"""Common interface for specialized worker tools."""
from abc import ABC, abstractmethod


class BaseTool(ABC):
    def __init__(self, name, description):
        self.name = name
        self.description = description

    @abstractmethod
    def invoke(self, input_dict):
        """Execute the tool with a dictionary of parameters."""
        raise NotImplementedError

    @abstractmethod
    def validate_input(self, input_dict):
        """Validate parameters before execution."""
        raise NotImplementedError
