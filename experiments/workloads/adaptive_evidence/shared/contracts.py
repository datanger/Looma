from __future__ import annotations

EVIDENCE_SCHEMA = {
    "type": "object",
    "required": ["evidence", "actions", "coverage_note"],
    "properties": {
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source_id", "claim"],
                "properties": {
                    "source_id": {"type": "string"},
                    "claim": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "actions": {"type": "array", "items": {"type": "string"}},
        "coverage_note": {"type": "string"},
    },
    "additionalProperties": False,
}

ANALYSIS_SCHEMA = {
    "type": "object",
    "required": ["decision", "cited_source_ids", "rationale", "needs_revision"],
    "properties": {
        "decision": {"type": "string", "enum": ["approve", "reject", "insufficient"]},
        "cited_source_ids": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
        "needs_revision": {"type": "boolean"},
    },
    "additionalProperties": False,
}
