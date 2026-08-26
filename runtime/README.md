# HALT v1.1 — Minimal Reference Runtime

Single-node reference implementation of the HALT v1.0.2 core mechanisms.
~460 lines, standard library only, no dependencies.

## What it makes impossible-by-construction

| Field-run incident (see `../12-validation-report.md`) | Mechanism that now prevents it |
|---|---|
| I-3 seq-collision storm | `append()` derives seq from journal tail at call time — Rule J-4 in code, not in discipline |
| I-1 registry torn write | Registry is atomic-write + auto-rebuilt from the journal when missing/empty/corrupt |
| I-4 same-path version inversion | `register_artifact()` refuses new content on a taken path (Rule AR-3) |
| I-7 silent worker death masking DONE | `register_artifact()` refuses missing files; DONE requires disk evidence (Rule PD-J1) |
| Concurrent writers | Single-writer lease file; second writer raises loudly |
| Illegal state jumps | FSM legality table checked before any transition |

## API sketch

```python
import os
from halt_rt import HaltRuntime

with HaltRuntime(workspace, task_id="my-task") as rt:   # fresh; lease held inside the block
    rt.add_node("N1", "do thing")
    rt.transition("N1", "READY")
    rt.transition("N1", "RUNNING")

    # Content must hit disk BEFORE registration (PD-J1: no disk, no DONE).
    # Paths are workspace-relative (PL-4), so join them onto the workspace root:
    out = os.path.join(workspace, "artifacts", "N1", "n1-out.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write("node N1 output")

    rt.register_artifact("A-N1", "artifacts/N1/n1-out.md", kind="doc", node_id="N1")
    rt.transition("N1", "VERIFYING", evidence=["A-N1"])
    rt.transition("N1", "DONE", evidence=["A-N1 verified"])
# lease released at block exit

# ... crash happens ...
rt = HaltRuntime.resume(workspace)                 # rebuild from ledger

rt.steering("ST-001", "...")       # durable steering inbox event
rt.decision("DR-1", "...")         # decision record
rt.note("incident ...")            # free-form ledger note

print(rt.status())                  # seq/nodes/integrity at a glance
```

Run as a context manager to guarantee lease release: `with HaltRuntime(ws, tid) as rt: ...`

## Tests

`test_halt_rt.py` contains the eight fixtures from the validation report §5:

```
python test_halt_rt.py        # 8 passed, 0 failed
```

## Scope & non-goals

Single-node, single-writer only. Parallel fan-out coordination, nested
workspaces, and cross-task memory are future work (they map to HALT-06/07/10,
none exercised by the field run). The runtime is a *reference*: it favours
loud refusal over clever recovery wherever the spec says "undefined".
