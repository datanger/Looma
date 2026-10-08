"""Structural schemas for the AEP optimization handoff payloads."""

from __future__ import annotations

from typing import Any

from ..protocol import describe_schema
from .protocol import CandidateProposal


def candidate_proposal_schema() -> dict[str, Any]:
    """Return the JSON schema used for Host Agent candidate proposals."""

    return describe_schema(CandidateProposal)


def reflection_input_schema() -> dict[str, Any]:
    """Return the input contract for a Host Agent reflection request."""

    return {
        "type": "object",
        "properties": {
            "candidate": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
            "components_to_update": {
                "type": "array",
                "items": {"type": "string"},
            },
            "evaluation": {"type": "object"},
            "frontier": {
                "type": "object",
                "properties": {
                    "candidate_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                },
                "required": ["candidate_ids"],
                "additionalProperties": False,
            },
            "budget": {
                "type": "object",
                "properties": {
                    "metric_calls": {"type": "integer"},
                    "remaining_metric_calls": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}]
                    },
                },
                "required": ["metric_calls", "remaining_metric_calls"],
                "additionalProperties": False,
            },
        },
        "required": [
            "candidate",
            "components_to_update",
            "evaluation",
            "frontier",
            "budget",
        ],
        "additionalProperties": False,
    }
