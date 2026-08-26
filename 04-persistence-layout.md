# HALT Persistence Layout & Formats

- **Spec ID:** HALT-04
- **Version:** 1.0.1 (2026-08-25) — semantics hardening after four external reviews
- **Depends on:** HALT-01 §4–5 (four artifacts, commit rule)

This document fixes the canonical on-disk layout and the exact formats of the four persistent artifacts, plus supporting registers. Conforming implementations MAY add files but MUST NOT relocate or re-format these.

> **Atomicity note (from HALT-01 §5):** the four artifacts are NOT a single atomic unit under POSIX; the journal is the authoritative record and every other file is a rebuildable projection. On any cross-file inconsistency, run recovery (HALT-05) — never hand-reconcile by editing multiple files to "match".

---

## 1. Canonical Workspace Tree

```
W/                                  # workspace root = one Task Instance (D2/D3)
├── task-graph.json                 # artifact 1: DAG + node records        (§3)
├── journal.jsonl                   # artifact 2: append-only event log     (§2)
├── checkpoint.json                 # artifact 3: pointer cache             (§4)
├── artifacts/                      # artifact 4 root: produced content
│   ├── registry.json               #   the Artifact Registry               (§5)
│   ├── <node_id>/                  #   per-node output scope
│   │   ├── ledger.jsonl            #   unit ledger for batch nodes         (§6)
│   │   └── ...
│   └── old/                        # S1 quarantine area (superseded copies)
├── contracts/                      # issued Contracts (D24), one JSON per dispatch
│   └── inv-….json
├── steering/
│   └── inbox.md                    # durable steering/question channel      (HALT-09)
├── sops/                           # SOP Cards used/referenced by this task (HALT-03 §2)
├── docs/                           # human-facing working documents
│   ├── task-plan.md                # goals/phases/decision log (human view; derived)
│   ├── progress.md                 # narrative session log w/ NEXT pointer (derived)
│   └── DOC-LEDGER.md               # working-doc register w/ minute timestamps (§7)
└── tmp/                            # scratch; disposable; MUST NOT hold committed state
```

Rules:

- **Rule PL-1.** Everything under `docs/` is a *view* (truth rank 5). Everything at top level plus `artifacts/` is *state* (ranks 2–4). Never promote a view to state without registering it.
- **Rule PL-2.** `tmp/` contents are exempt from registry BUT any `tmp/` file a future reader would need must be listed in DOC-LEDGER.md with purpose + minute-level mtime (empirical rule: undocumented temp files become archaeology puzzles after interruptions).
- **Rule PL-3.** Node scopes (`artifacts/<node_id>/`) are write-partitioned by INV-10: an executor dispatched for node X writes ONLY inside its scope (+tmp). Cross-scope writes require coordinator authority.
- **Rule PL-4.** Paths inside all formats are workspace-relative POSIX-style; implementations translate to OS-native at IO time. IDs never encode absolute paths (workspaces must stay relocatable).

---

## 2. Journal Format (`journal.jsonl`)

One JSON object per line, UTF-8, no trailing commas, lines independent (a torn final line = uncommitted tail; recovery truncates it after inspection).

```json
{"seq":1042,"ts":"2026-08-25T19:41:32+08:00","actor":"coord:T-main",
 "kind":"STATE_TRANSITION","tx":null,
 "entity":{"type":"node","id":"N-042"},
 "payload":{"from":"READY","to":"RUNNING",
            "contract":"contracts/inv-20260825-1940-0007.json"},
 "evidence":["J-1039"]}
```

Field contract:

| Field | Rules |
|---|---|
| `seq` | monotonically increasing integer, gapless within this task; assigned by the single writer (coordinator) |
| `ts` | ISO-8601 with offset; informational only — ordering authority is `seq` |
| `actor` | `role:id` form (see HALT-08); every event names its author |
| `kind` | enum: `STATE_TRANSITION \| ARTIFACT_REGISTERED \| DECISION \| AMENDMENT \| RECEIPT \| NOTE \| HEARTBEAT \| INSTANCE_STARTED \| INSTANCE_ENDED \| STEERING_LOGGED` |
| `tx` | tx_id grouping multi-event logical changes (INV-3); null for singletons |
| `evidence` | list of refs (journal seqs / artifact ids / receipt ids / paths) backing the event |

- **Rule J-1.** Writers append only. A conforming tool NEVER rewrites earlier lines; corrections are superseding events referencing their targets.
- **Rule J-2.** Tier-2 tasks maintain `journal-mirror.jsonl`, flushed synchronously per commit batch; recovery treats primary/mirror disagreement as suspect-region boundary (inspect both, prefer the longer prefix that internally verifies).
- **Rule J-3.** Compaction, if ever needed, produces an ARCHIVED snapshot segment + continues numbering; live history is never deleted (INV-4).
- **Rule J-4 (v1.0.2).** *Seq derivation at append time.* `seq` MUST be computed as `1 + max(seq over existing journal lines)`, derived by reading the journal tail immediately before each append batch. Counters cached in process memory across instance restarts are non-conformant: a recovery or backfill stream that reuses a stale counter produces seq collisions, which corrupt the ordering authority while leaving content intact — the worst failure mode because it is silent. *(Empirical: field run J-5..35, three writer streams shared one namespace after coordinator death.)*

---

## 3. Task Graph Format (`task-graph.json`)

```json
{
  "task_id": "T-20260825-longform-report",
  "created": "2026-08-25T19:00:00+08:00",
  "tier": 1,
  "goal_statement": "…one paragraph…",
  "acceptance": ["report exists at deliverables/report.md", "all claims carry source refs"],
  "nodes": [
    {
      "node_id": "N-001",
      "title": "Stage corpus",
      "spec": {"goal": "…", "inputs": [...], "acceptance_criteria": [
          {"check": "script: count==118", "level": "V1"}],
       "constraints": [...], "budget": {...}},
      "deps": [],
      "state": "DONE",
      "attempts": 1,
      "failure_class": null,
      "artifacts": ["A-0001"],
      "priority": 10,
      "verification_level": "V1",
      "notes_ref": "J-0021"
    }
  ],
  "edges_implicit_via_deps": true
}
```

- **Rule TG-1.** Node Specs immutable post-first-dispatch except via `AMENDMENT` events; the graph file then carries `"amended_by": ["J-…"]`.
- **Rule TG-2.** State fields here are coordinator-maintained projections of journal truth. At any disagreement: recompute from the journal (this file is rebuilt, not patched by hand). **Amendments are journaled first** (AMENDMENT event) and only then reflected here; a graph edit without its journal event is a defect to be caught at recovery (the journal wins, INV-2).
- **Rule TG-3.** New nodes get fresh ids; quarantined work keeps its id forever (N14 successors reference it).

---

## 4. Checkpoint Format (`checkpoint.json`)

Wholesale-rewritten pointer cache (cheap; ≤ a few KB):

```json
{
  "task_id": "T-…",
  "updated_at": "2026-08-25T19:45:02+08:00",
  "fsm_task": "EXECUTING",
  "active_contracts": [{"invocation_id":"inv-…","node":"N-042","executor":"worker:w7"}],
  "frontier_snapshot": ["N-043","N-047"],
  "counters": {"seq_last": 1042, "nodes_done": 12, "nodes_open": 31},
  "budgets": {"tool_calls_used": 8113, "wall_started": "2026-08-24T09:12:00+08:00"},
  "modes": {"dispatch_mode": "A", "first_death_rate_window": [0.25, "wave9"]},
  "next_hint": "resume N-042 units u031+ (ledger says u030 ok)",
  "terminal": false
}
```

- **Rule CK-1.** Regeneration procedure documented (HALT-05 §4): losing this file must cost minutes, not information.
- **Rule CK-2.** Update cadence: at minimum on every state transition and every N unit commits (N ≈ 10–50 depending on throughput); high-frequency loops may lag behind journal — that's what it's for (MemChar hot/cold split).

---

## 5. Artifact Registry (`artifacts/registry.json`)

```json
{
  "A-0912": {
    "path": "artifacts/n-042/bibliography.jsonl",
    "kind": "dataset",
    "produced_by_node": "N-042",
    "produced_by_invocation": "inv-…",
    "integrity": {"algo": "sha256", "value": "…", "size_bytes": 88214,
                   "checked_at": "2026-08-25T19:44:51+08:00"},
    "status": "current",           // current | superseded(by:A-…) | quarantined
    "commit_event": 1043
  }
}
```

- **Rule AR-1.** Registration is part of the commit step: artifact written → read back → checksummed → registered → THEN the commit event may cite it. Order is normative.
- **Rule AR-2.** Supersession chains preserve every generation (old file physically moved to `artifacts/old/<id>-<n>/` when cheap, else checksum-identified) — rollback always has a target (S1 discipline).
- **Rule AR-3 (v1.0.2).** *(path, checksum) immutability.* A registered path's content is frozen by its checksum. Registering new content on an already-registered path MUST either use a NEW artifact id (preferred) or a versioned path (`<name>.v2.<ext>`); overwriting in place is non-conformant because it retroactively invalidates the earlier entry's checksum, turning every integrity walk into false FAILs and forcing precedence to be reconstructed from insertion order — which is not evidence. `status: superseded(by:…)` is set on the old entry at supersession time, never inferred later. *(Empirical: field run I-4 — A-N2v2/v3 inversion; 4 false integrity FAILs.)*

---

## 6. Unit Ledger Format (`ledger.jsonl`, per batch node)

```json
{"unit_id":"u0031","status":"ok","artifact":"u0031.jsonl","lines_appended":9,"ts":"…"}
{"unit_id":"u0032","status":"skip-evidence","reason":"flag present from prior attempt","ts":"…"}
```

- **Rule UL-1.** Append-only like the journal; it is the skip-by-evidence index (INV-5) and doubles as heartbeat stream.
- **Rule UL-2.** For extraction-style work where downstream merges occur, unit outputs embed stable keys (source coordinates) so merge tools can dedupe/re-number mechanically — parallel writers MUST NOT coordinate sequence numbers among themselves (empirical: collision-by-design, resolved at merge).

---

## 7. Working-Doc Register (`docs/DOC-LEDGER.md`)

Human-facing table of every working document: path, purpose, last-updated timestamp **precise to the minute**, and status. External read-only references (files outside W used as inputs) are also listed with observed mtimes — a changed mtime ⇒ must re-read before citing (freshness check before reliance).

---

## 8. Encoding, Names, Robustness Notes (implementation guidance)

- UTF-8 everywhere; LF line endings preferred; if Windows CRLF appears in data files, parsers MUST tolerate.
- Filenames ASCII-safe where possible; when source material forces Unicode filenames, record the mapping in the ledger rather than renaming sources (never mutate inputs).
- Sorting by name is forbidden for ordering semantics — sort by numeric keys parsed from ids (`W10 > W9`; string order lies).
- All readers MUST tolerate unknown extra fields (forward compatibility), missing optional fields, and trailing whitespace.
- Checksums: sha256 when available; fallback identity class = size+mtime recorded honestly as such (weaker, flagged `weak:true`).

---

*End of HALT-04. Next: HALT-05 — the Recovery procedure that consumes these formats.*
