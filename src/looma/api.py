from __future__ import annotations

from typing import Any, Callable, TypeVar

from .runtime import current_runtime, workflow_decorator

T = TypeVar("T")


def workflow(fn: Callable[..., T]) -> Callable[..., T]:
    """Mark the outer durable workflow entry function."""
    return workflow_decorator(fn)


def step(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Execute a deterministic/side-effectful function once and replay its cached JSON result."""
    return current_runtime().step(fn, *args, **kwargs)


def agent(*, task: str, input: Any = None, output_schema: Any = None) -> Any:
    """Suspend on first execution and return the persisted agent result on replay."""
    return current_runtime().agent(task=task, input=input, output_schema=output_schema)
