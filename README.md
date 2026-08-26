# HALT — Hierarchical Automaton for Long-horizon Tasks

**Version 1.0.2 · Status: Stable**

A process specification for running long-horizon tasks with AI agents — interruptible at any point, persistently memorized, arbitrarily nestable.

> A task is a directed graph of nodes driven by journaled transactional state machines; progress exists only where write→verify→commit has completed; any agent — new or old, human or machine — resumes by asking *"where is my last provably stable position?"* and recomputing what may legally run next.

## What's here

| Path | Contents |
|---|---|
| `00-index.md` | Entry point & document map |
| `01`–`11` | The specification: core model, lifecycle FSMs, SOP interface, persistence layout, recovery, nesting, parallel dispatch, roles, human gates, memory store, conformance |
| `12-validation-report.md` | Field-run validation: incident register, per-clause verdicts, amendments, fixture map |
| `glossary.md` | Authoritative definitions |
| `provenance.md` | Source mapping (papers / field practice) + Evidence Matrix |
| `runtime/` | v1.1 minimal reference runtime (single-node, stdlib-only Python) + 8 fixture tests — all passing |
| `zh/` | Chinese edition of the core document |

## Highlights

- **Field-validated**: every mechanism carries an evidence class (paper / practice / design) and a field-test flag; the four v1.0.2 amendments (seq tail-derivation, path-checksum immutability, artifact-presence verification, audit recomputability) each trace to a real incident they now prevent.
- **Falsifiable**: incidents from the validation run are replayable as automated fixtures against the reference runtime.
- **Executor-agnostic**: the same spec has been executed by a human-coordinated LLM agent, by plain Python, and packaged as an agent skill.

## Quick start

```bash
cd runtime
python test_halt_rt.py     # 8 passed
```

```python
from halt_rt import HaltRuntime

rt = HaltRuntime("./my-task-ws", task_id="my-task")   # fresh workspace
# ... crash happens ...
rt = HaltRuntime.resume("./my-task-ws")               # rebuild from ledger
```

## Reading paths

- **Just the idea**: `00-index.md` → `01-core-model.md`
- **Implement it**: `04-persistence-layout.md` → `runtime/README.md`
- **Trust it**: `12-validation-report.md` → `provenance.md` (Evidence Matrix)
- **中文读者**: `zh/01-core-model.md`

## Status

Single-node scope is stable. Multi-node parallel dispatch, process-kill benchmark suite (HALT-Bench), and cross-task memory store are specified but not yet runtime-implemented.
