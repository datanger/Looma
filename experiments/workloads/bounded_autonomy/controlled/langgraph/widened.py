"""Route widening for the LangGraph implementation.

A graph cannot grow a route at runtime, so admitting the held-out perturbation means
adding a node bound to the missing action plus its edges. This module holds exactly that
addition so the development-route cost and the widening cost stay separable.
"""

from __future__ import annotations

from experiments.workloads.bounded_autonomy.controlled.protocol import ACTION_LIST, ACTION_READ


WIDENED_ACTIONS = (ACTION_READ, ACTION_LIST)


def widened_path_map() -> dict[str, str]:
    return {"read": "read_source", "list": "discover", "gate": "gate", "finalize": "finalize"}