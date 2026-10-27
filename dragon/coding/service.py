"""The coding agents as a service of the runtime: one place the API and the Dragon's own
tool go through. Calls read the disk and start CLI runs on this computer.

Runs publish on the bus as ``{"kind": "coding", …}`` so every open app follows a run
live; the finished ones are kept for the session list (the last 50) — in memory and in
``<data_dir>/coding/runs.json``, so a restart of the runtime does not lose what was asked
and answered. A run that was still going when the runtime stopped comes back as
``stopped`` with a note; the CLI process itself was ended with the runtime.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dragon.coding import agents
from dragon.coding.runner import Run, start_run
from dragon.logger import logger

if TYPE_CHECKING:
    from dragon.server.service import DragonService

KEEP_RUNS = 50


class CodingError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class CodingService:
    def __init__(self, svc: DragonService):
        self.svc = svc
        self.runs: dict[str, Run] = {}
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._detected: list[dict[str, Any]] = []
        self._detected_at = 0.0
        self._store: Path | None = None
        data_dir = getattr(svc, "data_dir", None)
        if data_dir is not None:
            self._store = Path(data_dir) / "coding" / "runs.json"
            self._load()

    # ------------------------------------------------------------------ the record
    def _load(self) -> None:
        """The finished runs of earlier sessions of the runtime, newest kept."""
        if self._store is None or not self._store.is_file():
            return
        try:
            rows = json.loads(self._store.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("coding: could not read {}: {}", self._store, exc)
            return
        if not isinstance(rows, list):
            return
        for row in rows[-KEEP_RUNS:]:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            run = Run(
                id=str(row["id"]),
                agent=str(row.get("agent") or ""),
                session_id=str(row.get("asked_session_id") or ""),
                workspace=str(row.get("workspace") or ""),
                text=str(row.get("text") or ""),
                started_at=float(row.get("started_at") or 0),
                ended_at=row.get("ended_at"),
                status=str(row.get("status") or "done"),
                output=str(row.get("output") or ""),
                result_session_id=str(row.get("session_id") or ""),
                resumed=bool(row.get("resumed")),
                error=str(row.get("error") or ""),
                tools=int(row.get("tools") or 0),
            )
            if run.status == "running":
                # it was going when the runtime stopped; the process went with it
                run.status = "stopped"
                run.ended_at = run.ended_at or run.started_at
                run.error = run.error or "the runtime restarted while this was running"
            self.runs[run.id] = run

    def _save(self) -> None:
        """Every run that is not still going, oldest first, replaced atomically."""
        if self._store is None:
            return
        rows = [
            r.to_dict()
            for r in sorted(self.runs.values(), key=lambda r: r.started_at)
            if r.status != "running"
        ][-KEEP_RUNS:]
        try:
            self._store.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._store.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self._store)
        except OSError as exc:
            logger.warning("coding: could not write {}: {}", self._store, exc)

    # ------------------------------------------------------------------ local
    def agents(self, fresh: bool = False) -> list[dict[str, Any]]:
        """Installed agents with versions (cached a minute; `running` is always live)."""
        if fresh or time.time() - self._detected_at > 60:
            self._detected = [a.to_dict() for a in agents.detect(with_versions=True)]
            self._detected_at = time.time()
        else:
            live = {a.id: a.running for a in agents.detect(with_versions=False)}
            for a in self._detected:
                a["running"] = live.get(a["id"], 0)
        return self._detected

    def sessions(
        self, agent: str | None = None, limit: int = 30, workspace: str | None = None
    ) -> list[dict[str, Any]]:
        if agent and agent not in agents.AGENTS:
            raise CodingError("unknown_agent", f"no coding agent called {agent!r}")
        out = [s.to_dict() for s in agents.sessions(agent, limit, workspace or None)]
        # a run in progress marks its session as running even before the agent writes
        for r in self.runs.values():
            if r.status == "running":
                sid = r.result_session_id or r.session_id
                for s in out:
                    if s["agent"] == r.agent and s["id"] == sid:
                        s["status"] = "running"
                        s["run"] = r.id
        return out

    def session(self, agent: str, session_id: str) -> dict[str, Any]:
        if agent not in agents.AGENTS:
            raise CodingError("unknown_agent", f"no coding agent called {agent!r}")
        s = agents.read_session(agent, session_id)
        if s is None:
            raise CodingError("no_session", "that session is not on this computer")
        d = s.to_dict(with_transcript=True)
        for r in self.runs.values():
            if r.agent == agent and (r.result_session_id or r.session_id) == session_id:
                d.setdefault("runs", []).append(r.to_dict())
        return d

    async def send(
        self, agent: str, text: str, session_id: str = "", workspace: str = "", wait: bool = False
    ) -> dict[str, Any]:
        """Start a run; returns at once with the run (or, with ``wait``, when it ends)."""
        if agent not in agents.AGENTS:
            raise CodingError("unknown_agent", f"no coding agent called {agent!r}")
        if not text.strip():
            raise CodingError("usage", "text is required")
        if not agents.which(agent):
            raise CodingError(
                "not_installed", f"{agents.AGENTS[agent]['name']} is not installed on this computer"
            )
        running = [
            r
            for r in self.runs.values()
            if r.status == "running"
            and r.agent == agent
            and (r.result_session_id or r.session_id) == session_id
            and session_id
        ]
        if running:
            raise CodingError("busy", "that session already has a message running")
        self.svc.app.audit.record(
            "coding_send", agent=agent, session=session_id[:12], summary=text[:100]
        )

        run_id = "run_" + uuid.uuid4().hex[:8]

        def register(run: Run) -> None:
            self.runs[run_id] = run

        async def on_event(ev: dict[str, Any]) -> None:
            run = self.runs.get(run_id)
            self.svc.bus.publish(
                {
                    "kind": "coding",
                    "event": ev,
                    "agent": agent,
                    "session_id": (run.result_session_id if run else "") or session_id,
                    "run": run.to_dict()
                    if run and ev.get("kind") in ("started", "done", "error")
                    else None,
                }
            )

        task = asyncio.create_task(
            start_run(
                agent,
                text,
                session_id=session_id,
                workspace=workspace,
                on_event=on_event,
                run_id=run_id,
                register=register,
            )
        )
        self._tasks[run_id] = task

        def _done(t: asyncio.Task[Run]) -> None:
            self._tasks.pop(run_id, None)
            run = self.runs.get(run_id)
            try:
                run = t.result()
            except asyncio.CancelledError:
                if run is not None and run.status == "running":
                    run.status, run.ended_at = "stopped", time.time()
            except Exception as exc:  # noqa: BLE001
                if run is not None:
                    run.status, run.error, run.ended_at = "failed", str(exc)[:300], time.time()
            if run is not None:
                self.runs[run_id] = run
                self.svc.bus.publish(
                    {
                        "kind": "coding",
                        "event": {"kind": "run"},
                        "agent": agent,
                        "session_id": run.result_session_id or session_id,
                        "run": run.to_dict(),
                    }
                )
            self._trim()
            self._save()

        task.add_done_callback(_done)
        # give start_run a tick to register the Run so the caller gets its shape back
        await asyncio.sleep(0)
        run = self.runs.get(run_id)
        if wait:
            run = await task
            return run.to_dict()
        if run is None:
            return {
                "id": run_id,
                "agent": agent,
                "session_id": session_id,
                "workspace": workspace,
                "text": text,
                "status": "running",
                "output": "",
                "error": "",
                "tools": 0,
                "started_at": time.time(),
                "ended_at": None,
                "resumed": bool(session_id),
            }
        return run.to_dict()

    def stop(self, run_id: str) -> bool:
        run = self.runs.get(run_id)
        task = self._tasks.get(run_id)
        stopped = False
        if run is not None:
            stopped = run.stop()
        if not stopped and task is not None and not task.done():
            task.cancel()
            stopped = True
            if run is not None:
                run.status, run.ended_at = "stopped", time.time()
        return stopped

    def stop_all(self) -> int:
        return sum(1 for rid in list(self.runs) if self.stop(rid))

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        runs = sorted(self.runs.values(), key=lambda r: -r.started_at)
        return [r.to_dict() for r in runs[:limit]]

    def _trim(self) -> None:
        if len(self.runs) <= KEEP_RUNS:
            return
        finished = sorted(
            (r for r in self.runs.values() if r.status != "running"), key=lambda r: r.started_at
        )
        for r in finished[: len(self.runs) - KEEP_RUNS]:
            self.runs.pop(r.id, None)

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            self.stop_all()
        tasks = [t for t in self._tasks.values() if not t.done()]
        for t in tasks:
            t.cancel()
        if tasks:
            # each run's cancellation waits for its agent to leave (start_run); a few
            # seconds at most, and the service does not return with children behind it
            with contextlib.suppress(BaseException):
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 10)
        logger.debug("coding: closed")


__all__ = ["CodingError", "CodingService"]
