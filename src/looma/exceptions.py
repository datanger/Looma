class LoomaError(Exception):
    """Base exception for Looma."""


class WorkflowSuspend(BaseException):
    """Internal control-flow exception used to suspend a workflow process."""

    def __init__(self, request: dict, request_file: str):
        super().__init__("workflow suspended waiting for agent")
        self.request = request
        self.request_file = request_file


class ReplayMismatchError(LoomaError):
    """Raised when replay no longer matches the persisted workflow history."""


class SerializationError(LoomaError):
    """Raised when a durable value cannot be serialized as JSON."""
