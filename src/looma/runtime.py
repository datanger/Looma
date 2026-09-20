from __future__ import annotations

import inspect
import json
import os
import sys
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from .exceptions import ReplayMismatchError, WorkflowSuspend
from .protocol import build_script2agent
from .serde import coerce_result, dump_json, json_hash, load_json, normalize_json

CURRENT_RUNTIME: ContextVar["WorkflowRuntime | None"] = ContextVar("looma_runtime", default=None)
SUSPEND_EXIT_CODE = 75
REQUEST_BEGIN = "<<<SCRIPT2AGENT>>>"
REQUEST_END = "<<<END_SCRIPT2AGENT>>>"


@dataclass(frozen=True)
class Invocation:
    script: str
    args: list[str]
    cwd: str

    @classmethod
    def capture(cls) -> "Invocation":
        # Re-running Python with the original argv is semantically equivalent to
        # the original Python script invocation and avoids exposing a resume helper.
        argv0 = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else sys.argv[0]
        return cls(script=sys.executable, args=[argv0, *sys.argv[1:]], cwd=os.getcwd())

    def fingerprint(self) -> str:
        return json_hash({"script": self.script, "args": self.args, "cwd": self.cwd})[:20]


class WorkflowRuntime:
    def __init__(self, *, workflow_name: str, source_function: str, state_root: Path | None = None):
        self.workflow_name = workflow_name
        self.source_function = source_function
        self.invocation = Invocation.capture()
        self.state_root = Path(state_root or os.environ.get("LOOMA_STATE_DIR", ".looma")).resolve()
        self.invocation_dir = self.state_root / "invocations"
        self.runs_dir = self.state_root / "runs"
        self.invocation_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.cursor = 0
        self.run_id, self.state = self._load_or_create_run()
        self.run_dir = self.runs_dir / self.run_id
        self.events_dir = self.run_dir / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)

    @property
    def active_pointer(self) -> Path:
        key = json_hash({"workflow": self.workflow_name, "invocation": self.invocation.fingerprint()})[:24]
        return self.invocation_dir / f"{key}.json"

    @property
    def state_file(self) -> Path:
        return self.run_dir / "state.json"

    def _load_or_create_run(self) -> tuple[str, dict]:
        pointer = self.active_pointer
        if pointer.exists():
            ref = load_json(pointer)
            run_id = ref["run_id"]
            state_path = self.runs_dir / run_id / "state.json"
            if state_path.exists():
                state = load_json(state_path)
                if state.get("status") != "completed":
                    return run_id, state

        run_id = uuid.uuid4().hex
        state = {
            "version": 1,
            "run_id": run_id,
            "workflow_name": self.workflow_name,
            "source_function": self.source_function,
            "invocation": {
                "script": self.invocation.script,
                "args": self.invocation.args,
                "cwd": self.invocation.cwd,
            },
            "status": "running",
            "events": [],
        }
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        dump_json(run_dir / "state.json", state)
        dump_json(pointer, {"run_id": run_id})
        return run_id, state

    def save(self) -> None:
        dump_json(self.state_file, self.state)

    def complete(self) -> None:
        self.state["status"] = "completed"
        self.save()
        if self.active_pointer.exists():
            self.active_pointer.unlink()

    def fail(self, error: BaseException) -> None:
        self.state["status"] = "failed"
        self.state["error"] = f"{type(error).__name__}: {error}"
        self.save()

    def _caller_key(self, kind: str) -> str:
        frame = inspect.currentframe()
        # runtime._caller_key -> runtime.step/agent -> api.step/agent -> user code
        for _ in range(4):
            if frame is not None:
                frame = frame.f_back
        if frame is None:
            return f"{kind}:unknown"
        return f"{kind}:{os.path.abspath(frame.f_code.co_filename)}:{frame.f_lineno}:{frame.f_code.co_name}"

    def _event(self, *, kind: str, key: str, input_hash: str) -> dict | None:
        idx = self.cursor
        self.cursor += 1
        events = self.state["events"]
        if idx >= len(events):
            return None
        event = events[idx]
        if event["kind"] != kind or event["key"] != key or event.get("input_hash") != input_hash:
            raise ReplayMismatchError(
                "Workflow replay diverged from persisted history at event "
                f"{idx}. Expected kind={event['kind']} key={event['key']} input_hash={event.get('input_hash')}, "
                f"got kind={kind} key={key} input_hash={input_hash}. "
                "Do not change replay-visible control flow while a workflow is suspended."
            )
        return event

    def step(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        key = self._caller_key("step") + f":{fn.__module__}.{fn.__qualname__}"
        normalized_input = {"args": normalize_json(args), "kwargs": normalize_json(kwargs)}
        input_hash = json_hash(normalized_input)
        event = self._event(kind="step", key=key, input_hash=input_hash)
        idx = self.cursor - 1
        result_file = self.events_dir / f"{idx:04d}-step-result.json"

        if event is not None:
            return load_json(Path(event["result_file"]))

        result = fn(*args, **kwargs)
        dump_json(result_file, result)
        self.state["events"].append(
            {
                "index": idx,
                "kind": "step",
                "key": key,
                "input_hash": input_hash,
                "status": "completed",
                "result_file": str(result_file),
            }
        )
        self.save()
        return load_json(result_file)

    def agent(self, *, task: str, input: Any = None, output_schema: Any = None) -> Any:
        key = self._caller_key("agent")
        normalized_input = normalize_json(input)
        schema_name = getattr(output_schema, "__qualname__", str(output_schema))
        input_hash = json_hash({"task": task, "input": normalized_input, "schema": schema_name})
        event = self._event(kind="agent", key=key, input_hash=input_hash)
        idx = self.cursor - 1
        result_file = self.events_dir / f"{idx:04d}-agent-result.json"
        request_file = self.events_dir / f"{idx:04d}-script2agent.json"

        if event is not None:
            persisted_result = Path(event["result_file"])
            if persisted_result.exists():
                if event.get("status") != "completed":
                    event["status"] = "completed"
                    self.state["status"] = "running"
                    self.save()
                return coerce_result(load_json(persisted_result), output_schema)
            # Re-emitting the same request is idempotent if resume was triggered too early.
            request = load_json(Path(event["request_file"]))
            raise WorkflowSuspend(request, str(event["request_file"]))

        request = build_script2agent(
            source_script=os.path.abspath(sys.argv[0]),
            source_function=self.source_function,
            agent_input=normalized_input,
            task=task,
            result_file=result_file,
            output_schema=output_schema,
            expected_script=self.invocation.script,
            expected_args=self.invocation.args,
        )
        dump_json(request_file, request)
        self.state["events"].append(
            {
                "index": idx,
                "kind": "agent",
                "key": key,
                "input_hash": input_hash,
                "status": "waiting_agent",
                "result_file": str(result_file),
                "request_file": str(request_file),
            }
        )
        self.state["status"] = "waiting_agent"
        self.save()
        raise WorkflowSuspend(request, str(request_file))


def workflow_decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
    workflow_name = f"{fn.__module__}.{fn.__qualname__}"

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        existing = CURRENT_RUNTIME.get()
        if existing is not None:
            return fn(*args, **kwargs)

        runtime = WorkflowRuntime(workflow_name=workflow_name, source_function=fn.__qualname__)
        token = CURRENT_RUNTIME.set(runtime)
        try:
            result = fn(*args, **kwargs)
            runtime.complete()
            return result
        except WorkflowSuspend as suspended:
            # Request is persisted for machine consumption and also emitted as the
            # final stdout block so a coding-agent host can consume it directly.
            print(REQUEST_BEGIN)
            print(json.dumps(suspended.request, ensure_ascii=False, indent=2))
            print(REQUEST_END)
            print(f"LOOMA_REQUEST_FILE={suspended.request_file}")
            raise SystemExit(SUSPEND_EXIT_CODE)
        except SystemExit:
            raise
        except BaseException as exc:
            runtime.fail(exc)
            raise
        finally:
            CURRENT_RUNTIME.reset(token)

    return wrapper


def current_runtime() -> WorkflowRuntime:
    runtime = CURRENT_RUNTIME.get()
    if runtime is None:
        raise RuntimeError("step() and agent() must be called from inside a @workflow function")
    return runtime
