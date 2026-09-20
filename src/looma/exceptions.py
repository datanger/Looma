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


class Agent2ScriptValidationError(LoomaError):
    """Raised when a handoff response violates the resume contract."""

    error_code = "agent2script_validation_error"
    action = (
        "Do not execute actual_output. Return exactly expected_output, "
        "then retry validation."
    )

    def __init__(self, message: str, *, expected=None, actual=None, mismatches=None):
        super().__init__(message)
        self.expected = expected
        self.actual = actual
        self.mismatches = list(mismatches or [])

    def as_dict(self) -> dict:
        return {
            "error": self.error_code,
            "message": str(self),
            "expected_output": self.expected,
            "actual_output": self.actual,
            "mismatches": self.mismatches,
            "action": self.action,
        }


class AgentResultValidationError(Agent2ScriptValidationError):
    """Raised when output.result_file does not satisfy output.output_schema."""

    error_code = "agent_result_validation_error"
    action = (
        "Fix output.result_file so it satisfies output.output_schema. "
        "Do not resume the workflow until result validation passes."
    )

    def as_dict(self) -> dict:
        return {
            "error": self.error_code,
            "message": str(self),
            "output_schema": self.expected,
            "actual_result": self.actual,
            "mismatches": self.mismatches,
            "action": self.action,
        }
