"""Expose an unmodified A-RAG checkout as deterministic Host-callable retrieval tools.

The bridge intentionally does not instantiate A-RAG's BaseAgent or LLMClient.
It reuses only A-RAG's retrieval tools and AgentContext, leaving semantic
planning to the already-running Host Agent.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _imports():
    from arag import AgentContext, Config, ToolRegistry
    from arag.core.context import RetrievalLog
    from arag.tools.keyword_search import KeywordSearchTool
    from arag.tools.read_chunk import ReadChunkTool
    from arag.tools.semantic_search import SemanticSearchTool

    return {
        "AgentContext": AgentContext,
        "Config": Config,
        "ToolRegistry": ToolRegistry,
        "RetrievalLog": RetrievalLog,
        "KeywordSearchTool": KeywordSearchTool,
        "ReadChunkTool": ReadChunkTool,
        "SemanticSearchTool": SemanticSearchTool,
    }


def _load_context(path: Path | None):
    api = _imports()
    context = api["AgentContext"]()
    if path is None or not path.exists():
        return context

    data = json.loads(path.read_text(encoding="utf-8"))
    context.read_chunk_ids = {
        str(item) for item in data.get("chunks_read_ids", [])
    }
    context.search_history = list(data.get("search_history", []))
    context.retrieval_logs = [
        api["RetrievalLog"](
            tool_name=item.get("tool_name", "unknown"),
            tokens=int(item.get("tokens", 0)),
            metadata=dict(item.get("metadata") or {}),
        )
        for item in data.get("retrieval_logs", [])
        if isinstance(item, dict)
    ]
    context.total_retrieved_tokens = int(
        data.get(
            "total_retrieved_tokens",
            sum(item.tokens for item in context.retrieval_logs),
        )
    )
    return context


def _context_dict(context) -> dict[str, Any]:
    data = context.get_summary()
    data["search_history"] = list(getattr(context, "search_history", []))
    return data


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def build_runtime(
    config_path: str,
    *,
    session_path: str | None,
    enable_semantic: bool,
):
    api = _imports()
    config = api["Config"].from_yaml(config_path)
    chunks_file = config.get("data.chunks_file", "data/chunks.json")
    index_dir = config.get("data.index_dir", "data/index")

    tools = api["ToolRegistry"]()
    tools.register(api["KeywordSearchTool"](chunks_file=chunks_file))
    tools.register(api["ReadChunkTool"](chunks_file=chunks_file))

    warnings: list[str] = []
    index_file = Path(index_dir) / "sentence_index.pkl"
    if enable_semantic and index_file.exists():
        try:
            tools.register(
                api["SemanticSearchTool"](
                    chunks_file=chunks_file,
                    index_dir=index_dir,
                    model_name=config.get(
                        "embedding.model",
                        "sentence-transformers/all-MiniLM-L6-v2",
                    ),
                    device=config.get("embedding.device"),
                )
            )
        except Exception as exc:
            warnings.append(
                f"semantic_search unavailable: {type(exc).__name__}: {exc}"
            )
    elif enable_semantic:
        warnings.append(
            f"semantic_search disabled: index not found at {index_file}"
        )

    session = Path(session_path) if session_path else None
    return tools, _load_context(session), session, warnings


def execute(
    config_path: str,
    *,
    session_path: str | None,
    tool_name: str,
    arguments: dict[str, Any],
    enable_semantic: bool = True,
) -> dict[str, Any]:
    tools, context, session, warnings = build_runtime(
        config_path,
        session_path=session_path,
        enable_semantic=enable_semantic,
    )
    observation, metadata = tools.execute(
        tool_name,
        context,
        **arguments,
    )
    context_data = _context_dict(context)
    if session is not None:
        _atomic_json(session, context_data)
    return {
        "tool": tool_name,
        "observation": observation,
        "metadata": metadata,
        "context": context_data,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--session")
    parser.add_argument("--no-semantic", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("schemas")
    sub.add_parser("context")
    sub.add_parser("reset")
    call = sub.add_parser("call")
    call.add_argument("--tool", required=True)
    call.add_argument("--arguments", default="{}")
    args = parser.parse_args()

    tools, context, session, warnings = build_runtime(
        args.config,
        session_path=args.session,
        enable_semantic=not args.no_semantic,
    )

    if args.command == "list":
        payload = {"tools": tools.list_tools(), "warnings": warnings}
    elif args.command == "schemas":
        payload = {"schemas": tools.get_all_schemas(), "warnings": warnings}
    elif args.command == "context":
        payload = _context_dict(context)
    elif args.command == "reset":
        context.reset()
        payload = _context_dict(context)
        if session is not None:
            _atomic_json(session, payload)
    else:
        arguments = json.loads(args.arguments)
        if not isinstance(arguments, dict):
            parser.error("--arguments must decode to a JSON object")
        observation, metadata = tools.execute(
            args.tool,
            context,
            **arguments,
        )
        payload = {
            "tool": args.tool,
            "observation": observation,
            "metadata": metadata,
            "context": _context_dict(context),
            "warnings": warnings,
        }
        if session is not None:
            _atomic_json(session, payload["context"])

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
