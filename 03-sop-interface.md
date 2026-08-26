# HALT Uniform SOP Interface

- **Spec ID:** HALT-03
- **Version:** 1.0.0 (2026-08-25)
- **Depends on:** HALT-01 (D6, D15, D16, D24), HALT-02 (FSM-N, verification levels)

Every SOP — root task controller or nested sub-procedure — presents the SAME interface. This is what makes SOPs composable: a caller cannot tell whether it is invoking a 30-second format check or a 3-week literature survey, and never needs to.

An SOP definition (D15) consists of:

1. **SOP Card** — the identity + contract surface (§2),
2. **Machine** — its internal FSM over named phases (§3),
3. **IO Schemas** — typed input/output documents (§4),
4. **Failure & Escalation Map** — how it fails (§5).

An SOP Instance (D16) additionally owns runtime state: checkpoint slice, journal namespace, artifact scope (all defined in HALT-04/06).

---

## 1. The Function Analogy, Made Precise

The source document's sketch:

```
SOP.call(input, goal, constraints, current_state)
→ { result, files, decisions, new_state, next_action }
```

is retained as *intent* but hardened into two separate channels, because conflating them was the central flaw of naive designs:

- The **control channel** (state machine events) carries lifecycle truth: started / blocked / failed / done — journaled, evidence-gated.
- The **data channel** (Result Document) carries work products: artifacts, findings, decisions — registered, checksummed.

A caller that trusts result content without verifying through the control channel violates INV-6. A caller that ignores the data channel and re-derives results wastes budget. Both channels are mandatory on every invocation.

---

## 2. SOP Card

```yaml
sop_id: research.literature-survey        # reverse-DNS-ish, stable
version: 2.1.0                             # semver; breaking IO changes bump major
title: Literature Survey
purpose: >
  Given a topic brief and source constraints, produce an annotated
  bibliography plus synthesis notes meeting stated acceptance criteria.
inputs:                                    # typed; see §4
  - name: topic_brief          , schema: TopicBrief      , required: true
  - name: source_constraints   , schema: SourcePolicy    , required: false
outputs:
  - name: bibliography         , artifact_class: dataset
  - name: synthesis_notes      , artifact_class: doc
acceptance_criteria:                       # machine-checkable where possible
  - every entry has: source uri, access date, extraction quote, relevance grade
  - coverage: >= N sources per subtopic OR explicit gap declaration
  - V2 audit pass (auditor role)
side_effect_profile: [S0, S2]              # max classes this SOP may touch
verification_level_default: V1             # may be overridden upward by caller
idempotent: true                           # safe to resume/re-run (INV-5 obligations)
budget_hints: {max_units: null, typical_duration: multi-session}
gates:                                     # built-in Approval Gates (HALT-09)
  - event: publish_synthesis , policy: require-human-confirm
escalation_map:                            # see §5
  - on: source_paywall_deadend -> ask_user
  - on: corpus_too_large      -> decompose_and_report
phases: [intake, plan, gather, extract, synthesize, verify, report]
```

Card rules:

- **Rule SC-1.** `side_effect_profile` declares the maximum side-effect classes the SOP may perform. Callers MUST reject dispatching a card whose profile exceeds their own authority.
- **Rule SC-2.** `acceptance_criteria` are written for the verifier, not the executor: each criterion names its check method (script / audit / human).
- **Rule SC-3.** Cards are versioned artifacts stored under `sops/` in the workspace (or a shared library referenced by id+version). A running instance records exactly which version it executes.

---

## 3. Internal Phase Machine

An SOP's `phases` form a small linear-with-skips FSM (keep it simple; complexity belongs to the Task Graph above):

```
intake → plan → [work phases...] → verify → report
```

Normative phase semantics:

| Phase | Obligations |
|---|---|
| `intake` | Validate inputs against schemas; resolve paths; write instance scaffold (checkpoint slice + journal namespace); emit `INSTANCE_STARTED` |
| `plan` | Decompose into units; write unit ledger scaffold; smoke-test one unit end-to-end before committing to batch strategy; emit PLAN event with unit inventory |
| `gather`/`extract`/... | Domain work via Commit Rule per unit; heartbeat cadence |
| `verify` | Run declared verification level; failures loop back into work phases bounded by retry matrix (HALT-02 §7) |
| `report` | Emit Result Document; request parent transition N03; await external verification |

Phase transitions are journaled like any other (`kind: STATE_TRANSITION`, entity = instance id). An interruption during any phase resumes at the phase boundary nearest the last committed unit — never mid-unit redone from scratch unless the unit itself failed verification.

---

## 4. Input/Output Documents

### 4.1 Invocation (caller → SOP)

```json
{
  "invocation_id": "inv-20260825-1940-0007",
  "sop": {"id": "research.literature-survey", "version": "2.1.0"},
  "parent": {"task_id": "T-...", "node_id": "N-042"},
  "inputs": {"topic_brief": {...}, "source_constraints": {...}},
  "budget": {"max_tool_calls": 400, "max_wall_hours": 12, "max_cost_usd": 5.0},
  "authority_grants": ["write:artifacts/n-042/*", "network:read"],
  "reporting": {"heartbeat_min_interval_min": 10, "ledger_required": true},
  "steering_channel": "file:steering/inbox.md"
}
```

### 4.2 Result Document (SOP → caller)

```json
{
  "invocation_id": "inv-20260825-1940-0007",
  "status": "done | done_with_gaps | blocked(ask:<question-id>) | failed(<class>) ",
  "artifacts": [{"name":"bibliography","artifact_id":"A-0912","checksum_sha256":"…"}],
  "decisions": [{"decision_ref": "J-00314", "summary": "excluded preprints; rationale"}],
  "state_summary": {"units_total": 87, "units_ok": 85, "units_skipped_evidence": 2},
  "open_questions": [],
  "next_action_hint": "proceed to N-043",
  "handoff_note": "path to human-readable summary"
}
```

Rules:

- **Rule IO-1.** `status` values are closed-enum. `done_with_gaps` REQUIRES enumerated gaps in `open_questions`. Lying by omission here is the classic failure of naive delegation; gaps are assets, not shame.
- **Rule IO-2.** Every artifact listed MUST already be registered + verified per Commit Rule before the Result Document is emitted. Result emission without commit is a protocol violation (this is "claim ≠ commit", formalized).
- **Rule IO-3.** `blocked(ask:…)` routes through the steering/gate machinery (HALT-09): the question gets persisted FIRST so that even total session loss preserves what must be asked and why.

---

## 5. Failure & Escalation Map

Each SOP declares its failure modes and the escalation route for each:

```yaml
escalation_map:
  - on: transient_env            -> retry_after_probe           # HALT-02 RT-1
  - on: worker_death(x3)         -> method_switch_or_escalate   # FSN-3
  - on: acceptance_unreachable   -> quarantine_and_replan       # N08/N12
  - on: missing_authority        -> block_ask_user              # gate route
  - on: budget_exhausted         -> suspend_with_handoff_note
```

**Rule FE-1.** An SOP MUST NOT swallow a failure class it has no route for. Unmapped failure ⇒ generic route `suspend_with_handoff_note` + parent notification. Silent failure propagation is the single most damaging anti-pattern observed in practice (workers dying quietly, parents assuming progress).

**Rule FE-2.** Child failure reaches the parent ONLY as: child terminal state + registered partial outputs + Result Document (INV-8). Parents MUST NOT infer child internals beyond this interface.

---

## 6. Conformance Checklist for a New SOP Definition

1. Card complete (SC-1..3), acceptance criteria check-method-bearing?
2. Phases cover intake→verify→report with journaling?
3. Units small enough for C-UNIT? Ledger schema defined?
4. Idempotence story: can any unit be safely skipped-by-evidence on rerun?
5. Side effects within declared profile? S3 actions gated with receipts?
6. Escalation map covers all four failure classes of HALT-02 §7?
7. Verification level default appropriate? Auditor independence preserved (V2)?
8. Budget hints honest?

---

*End of HALT-03. Next: HALT-04 fixes the on-disk persistence layout these interfaces assume.*
