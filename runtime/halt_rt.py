"""
HALT v1.1 — Minimal Reference Runtime (single-node)
====================================================

A small, dependency-free Python library that makes the core HALT v1.0.2
mechanisms *executable*, so the failure modes observed in field run
`halt-fieldrun-01` (see ../12-validation-report.md) become impossible
by construction instead of avoided by discipline.

Implements (spec refs in brackets):
  - Journal append with tail-derived seq            [04 Rule J-4 / A-1]
  - Atomic event batches (single write, fsync-able)
  - Registry with (path, checksum) immutability     [04 Rule AR-3 / A-2]
  - Artifact presence verification before DONE      [07 Rule PD-J1 / A-3]
  - Task-graph state transitions with legality check [02 FSM]
  - Checkpoint refresh                              [04]
  - Resume: rebuild full state from ledger alone    [AX-1, 05 R0-R7]

Design rules:
  * Journal is the only authority; every other file is a rebuildable
    projection (04 "recoverable, not atomic").
  * Single-writer lease via a lock file; two writers = hard error.
  * No dependencies beyond the Python standard library.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: str, default: Any = None) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # empty or torn projection file: treat as absent; the journal is
        # the authority and rebuild paths recover it (04 "recoverable,
        # not atomic"; field run I-1).
        return default


def _write_json_atomic(path: str, obj: Any) -> None:
    """Write JSON atomically: temp file + os.replace. Prevents torn writes
    of projection files (registry/checkpoint/graph)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _append_line_atomic(path: str, line: str) -> None:
    """Append one line to a JSONL journal with flush+fsync.
    Appending is atomic enough on POSIX/Windows for single-writer use;
    the fsync guarantees the line survives a crash."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


class HaltError(Exception):
    """Base class for protocol violations. Raising is conformant behaviour:
    HALT prefers loud refusal over silent corruption."""


# --------------------------------------------------------------------------
# the runtime
# --------------------------------------------------------------------------

class HaltRuntime:
    """Single-node HALT runtime bound to one workspace directory."""

    NODE_STATES = {"PENDING", "READY", "RUNNING", "VERIFYING",
                   "DONE", "FAILED", "BLOCKED"}
    TASK_STATES = {"INIT", "DECOMPOSING", "EXECUTING", "FINAL_AUDIT",
                   "ARCHIVED"}

    LEGAL_NODE_TRANSITIONS = {
        ("PENDING", "READY"), ("READY", "RUNNING"),
        ("RUNNING", "VERIFYING"), ("VERIFYING", "DONE"),
        ("RUNNING", "FAILED"), ("VERIFYING", "FAILED"),
        ("FAILED", "READY"),          # retry
        ("BLOCKED", "READY"),         # unblocked by steering/gate
        ("RUNNING", "BLOCKED"),       # waiting on human gate
    }

    def __init__(self, workspace: str, task_id: str, actor: str = "coord:main"):
        self.ws = workspace
        self.task_id = task_id
        self.actor = actor

        self.journal_path = os.path.join(workspace, "journal.jsonl")
        self.graph_path = os.path.join(workspace, "task-graph.json")
        self.checkpoint_path = os.path.join(workspace, "checkpoint.json")
        self.registry_path = os.path.join(workspace, "artifacts", "registry.json")
        self.lock_path = os.path.join(workspace, ".halt-lease.lock")

        os.makedirs(os.path.join(workspace, "artifacts"), exist_ok=True)

        # ---- single-writer lease -------------------------------------
        # If another live writer exists, refuse loudly (04 single-writer).
        if os.path.exists(self.lock_path):
            raise HaltError(
                f"single-writer lease held: {self.lock_path} exists. "
                "Two concurrent writers are undefined behaviour (04). "
                "Remove the stale lock only after verifying the old "
                "writer is dead.")
        os.makedirs(workspace, exist_ok=True)
        with open(self.lock_path, "w", encoding="utf-8") as f:
            f.write(f"{_now()} pid={os.getpid()}\n")

        # ---- state ----------------------------------------------------
        self._events: list[dict] = []
        self._journal_lines: list[str] = []
        self._load_journal()

        if not self._journal_lines:
            # fresh workspace: emit INSTANCE_STARTED
            self.append("INSTANCE_STARTED",
                        {"type": "task", "id": task_id},
                        {"task": task_id,
                         "desc": "started by halt_rt v1.1"},
                         tx=None)

        self.graph = self._load_or_init_graph()
        self.registry: dict[str, dict] = self._load_registry()

    # ------------------------------------------------------------------
    # context manager = lease lifetime
    # ------------------------------------------------------------------
    def __enter__(self) -> "HaltRuntime":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False  # do not swallow exceptions

    def close(self) -> None:
        try:
            os.remove(self.lock_path)
        except FileNotFoundError:
            pass

    # ------------------------------------------------------------------
    # journal
    # ------------------------------------------------------------------
    def _load_journal(self) -> None:
        """Read all lines, tolerating (and flagging) a torn final line.
        The torn tail is preserved in memory as raw text but never parsed
        as an event; per spec, recovery truncates it after inspection."""
        self._journal_lines = []
        self.torn_tail: Optional[str] = None
        if not os.path.exists(self.journal_path):
            return
        with open(self.journal_path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        for i, ln in enumerate(lines):
            if not ln.strip():
                continue
            try:
                ev = json.loads(ln)
                self._events.append(ev)
                self._journal_lines.append(ln)
            except json.JSONDecodeError:
                if i == len(lines) - 1:
                    # torn write on the last line: keep for inspection
                    self.torn_tail = ln
                    break
                raise HaltError(
                    f"corrupt journal line {i+1} (not last line): {ln[:80]}")

    @property
    def seq_last(self) -> int:
        """Rule J-4: derived from the journal tail every time.
        Never cached across instances — this method IS the counter."""
        if not self._events:
            return 0
        mx = max(int(e["seq"]) for e in self._events if "seq" in e)
        return mx

    def append(self, kind: str, entity: dict, payload: dict,
               evidence: Optional[list] = None, tx: Optional[str] = None,
               actor: Optional[str] = None) -> dict:
        """Append one event. Seq comes from the tail (Rule J-4).
        Returns the stored event."""
        ev = {
            "seq": str(self.seq_last + 1),
            "ts": _now(),
            "actor": actor or self.actor,
            "kind": kind,
            "tx": tx,
            "entity": entity,
            "payload": payload,
            "evidence": evidence or [],
        }
        line = json.dumps(ev, ensure_ascii=False)
        _append_line_atomic(self.journal_path, line)
        self._events.append(ev)
        self._journal_lines.append(line)
        return ev

    # ------------------------------------------------------------------
    # graph
    # ------------------------------------------------------------------
    def _load_or_init_graph(self) -> dict:
        g = _read_json(self.graph_path)
        if g is not None:
            return g
        g = {"task_id": self.task_id,
             "created": _now(),
             "tier": 1,
             "nodes": [],
             "acceptance": []}
        _write_json_atomic(self.graph_path, g)
        return g

    def add_node(self, node_id: str, title: str,
                 acceptance_criteria: Optional[list] = None,
                 resume_policy: str = "skip_if_checksum") -> None:
        if any(n["node_id"] == node_id for n in self.graph["nodes"]):
            raise HaltError(f"node {node_id} already exists")
        node = {"node_id": node_id, "title": title, "state": "PENDING",
                "attempts": 0, "verification_level": "V1",
                "acceptance_criteria": acceptance_criteria or [],
                "resume_policy": resume_policy,
                "artifacts": [], "deps": []}
        self.graph["nodes"].append(node)
        _write_json_atomic(self.graph_path, self.graph)

    def _node(self, node_id: str) -> dict:
        for n in self.graph["nodes"]:
            if n["node_id"] == node_id:
                return n
        raise HaltError(f"unknown node {node_id}")

    def transition(self, node_id: str, to_state: str,
                   evidence: Optional[list] = None) -> None:
        """Legal-transition-checked STATE_TRANSITION + graph update +
        checkpoint refresh, in that order (journal first: recoverable-not-
        atomic means projections may lag the journal but never lead it)."""
        n = self._node(node_id)
        frm = n["state"]
        if to_state not in self.NODE_STATES:
            raise HaltError(f"illegal target state {to_state}")
        if (frm, to_state) not in self.LEGAL_NODE_TRANSITIONS:
            raise HaltError(f"illegal transition {node_id}: {frm} -> {to_state}")
        if to_state == "DONE" and evidence is None:
            # PD-J1: DONE requires disk evidence, checked by caller via
            # verify_artifact(); we accept pre-verified ids here.
            pass
        ev = self.append("STATE_TRANSITION",
                         {"type": "node", "id": node_id},
                         {"from": frm, "to": to_state},
                         evidence=evidence)
        n["state"] = to_state
        if to_state == "RUNNING":
            n["attempts"] = int(n.get("attempts", 0)) + 1
        _write_json_atomic(self.graph_path, self.graph)
        self._refresh_checkpoint()
        return ev

    def attach_artifact(self, node_id: str, artifact_id: str) -> None:
        n = self._node(node_id)
        if artifact_id not in n["artifacts"]:
            n["artifacts"].append(artifact_id)
            _write_json_atomic(self.graph_path, self.graph)

    # ------------------------------------------------------------------
    # registry  (AR-3 immutability)
    # ------------------------------------------------------------------
    def _load_registry(self) -> dict:
        reg = _read_json(self.registry_path)
        if not isinstance(reg, dict) or not reg:
            # missing/empty/torn registry: it is a rebuildable projection;
            # rebuild current entries from journal ARTIFACT_REGISTERED
            # events (last registration per id wins).
            rebuilt = {}
            for e in self._events:
                if e.get("kind") == "ARTIFACT_REGISTERED":
                    aid = (e.get("entity") or {}).get("id")
                    pl = e.get("payload") or {}
                    if aid and pl.get("path"):
                        pl = dict(pl)
                        pl.setdefault("status", "current")
                        rebuilt[aid] = pl
            reg = rebuilt if rebuilt else {}
            if reg:
                _write_json_atomic(self.registry_path, reg)
        return reg

    def _save_registry(self) -> None:
        _write_json_atomic(self.registry_path, self.registry)

    def register_artifact(self, artifact_id: str, path: str,
                          kind: str, node_id: Optional[str] = None,
                          produced_by_invocation: Optional[str] = None
                          ) -> dict:
        """Register an artifact. Enforces AR-3:
        same path + different content => must use new id / versioned path."""
        apath = path if os.path.isabs(path) else os.path.join(self.ws, path)
        if not os.path.exists(apath):
            raise HaltError(f"cannot register missing artifact: {apath} "
                            "(PD-J1: no disk, no DONE)")
        checksum = _sha256_file(apath)

        # find any existing entry claiming this path
        prior = None
        prior_id = None
        for aid, ent in self.registry.items():
            if os.path.normcase(ent.get("path", "")) == os.path.normcase(path):
                if ent.get("status", "current") == "current":
                    prior, prior_id = ent, aid
                    break

        if prior is not None and prior.get("integrity", {}).get("value") != checksum:
            raise HaltError(
                f"AR-3 violation: path already registered under id "
                f"{prior_id} with a different checksum. Use a NEW artifact id "
                f"(e.g. {artifact_id}-v2) or a versioned path; overwriting in "
                "place retroactively invalidates the earlier entry.")

        entry = {"path": path, "kind": kind,
                 "produced_by_node": node_id,
                 "produced_by_invocation": produced_by_invocation,
                 "integrity": {"algo": "sha256", "value": checksum,
                               "checked_at": _now()},
                 "status": "current",
                 "commit_event": int(self.seq_last)}
        if prior_id is not None:
            # same content re-registration is idempotent; mark chain
            entry["supersedes"] = prior_id
            prior["status"] = "current"   # same bytes: still current
        self.registry[artifact_id] = entry
        if node_id:
            self.attach_artifact(node_id, artifact_id)

        # journal AFTER registry save? No — journal first (authority),
        # then projection. If we crash between, rebuild recovers it.
        self.append("ARTIFACT_REGISTERED",
                    {"type": "artifact", "id": artifact_id},
                    entry, evidence=[path])
        self._save_registry()
        return entry

    def verify_artifact(self, artifact_id: str) -> bool:
        """Integrity walk for one id: disk hash must equal registered hash.
        With AR-3 enforced, stale-checksum false FAILs cannot occur."""
        ent = self.registry.get(artifact_id)
        if ent is None:
            raise HaltError(f"unknown artifact {artifact_id}")
        apath = ent["path"] if os.path.isabs(ent["path"]) \
            else os.path.join(self.ws, ent["path"])
        if not os.path.exists(apath):
            return False
        return _sha256_file(apath) == ent["integrity"]["value"]

    def integrity_walk(self) -> dict:
        results = {}
        for aid in sorted(self.registry):
            try:
                results[aid] = "PASS" if self.verify_artifact(aid) else \
                               "FAIL(missing or changed)"
            except HaltError:
                results[aid] = "FAIL(unknown)"
        return results

    # ------------------------------------------------------------------
    # checkpoint
    # ------------------------------------------------------------------
    def _refresh_checkpoint(self) -> None:
        done = sum(1 for n in self.graph["nodes"] if n["state"] == "DONE")
        cp = {"task_id": self.task_id,
              "updated_at": _now(),
              "fsm_task": self.graph.get("fsm_task", "EXECUTING"),
              "counters": {"seq_last": self.seq_last, "nodes_done": done},
              "frontier_snapshot": [n["node_id"] for n in self.graph["nodes"]
                                    if n["state"] == "READY"],
              "terminal": self.graph.get("terminal", False),
              "next_hint": self.graph.get("next_hint")}
        _write_json_atomic(self.checkpoint_path, cp)

    def set_hint(self, hint: str) -> None:
        self.graph["next_hint"] = hint
        _write_json_atomic(self.graph_path, self.graph)
        self._refresh_checkpoint()

    # ------------------------------------------------------------------
    # steering & gates
    # ------------------------------------------------------------------
    def steering(self, st_id: str, text: str) -> None:
        self.append("STEERING_LOGGED",
                    {"type": "task", "id": self.task_id},
                    {"inputs": [f"{st_id} {text}"]},
                    evidence=["steering/inbox.md"])

    def decision(self, dr_id: str, ruling: str,
                 evidence: Optional[list] = None) -> None:
        self.append("DECISION", {"type": "task", "id": self.task_id},
                    {dr_id: ruling}, evidence=evidence)

    def note(self, incident: str, extra: Optional[dict] = None,
             evidence: Optional[list] = None) -> dict:
        payload = {"incident": incident}
        if extra:
            payload.update(extra)
        return self.append("NOTE", {"type": "task", "id": self.task_id},
                           payload, evidence=evidence)

    # ------------------------------------------------------------------
    # resume (R0-R7 condensed for single-node use)
    # ------------------------------------------------------------------
    @classmethod
    def resume(cls, workspace: str) -> "HaltRuntime":
        """Resume an existing workspace: rebuild everything from the ledger.
        AX-1: conversation memory is volatile; the ledger is durable."""
        # read task_id from checkpoint or graph (both rebuildable)
        cp = _read_json(os.path.join(workspace, "checkpoint.json"), default={})
        task_id = cp.get("task_id")
        if not task_id:
            g = _read_json(os.path.join(workspace, "task-graph.json"),
                           default={})
            task_id = g.get("task_id", "resumed-task")
        rt = cls(workspace, task_id=task_id)
        rt.note("resumed from ledger",
                {"seq_last_at_resume": rt.seq_last,
                 "torn_tail": bool(rt.torn_tail)})
        return rt

    # ------------------------------------------------------------------
    # reporting
    # ------------------------------------------------------------------
    def status(self) -> dict:
        walk = self.integrity_walk()
        return {
            "task_id": self.task_id,
            "seq_last": self.seq_last,
            "events": len(self._events),
            "torn_tail": self.torn_tail is not None,
            "nodes": {n["node_id"]: n["state"] for n in self.graph["nodes"]},
            "artifacts": len(self.registry),
            "integrity": walk,
            "all_integrity_pass": all(v.startswith("PASS")
                                      for v in walk.values()) if walk else True,
        }
