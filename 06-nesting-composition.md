# HALT Nesting & Composition

- **Spec ID:** HALT-06
- **Version:** 1.0.0 (2026-08-25)
- **Depends on:** HALT-02 (FSM-T/FSM-N), HALT-03 (interface), HALT-05 (recovery)

How SOP Instances nest: the parent-child contract, namespace isolation, failure containment, and depth discipline. This is the Harel-style hierarchy layer — states that contain whole automata — adapted to agents that can die at any instant.

---

## 1. Composition Model

A parent node whose Spec warrants a specialized procedure binds an SOP Instance:

```
Parent Task (SOP instance, FSM-T)
 └─ node N-042  [state: RUNNING]
     └─ Child SOP Instance inv-… (its own FSM-T, own artifacts slice)
         ├─ its own nodes N-042.1 …
         │   └─ grandchild instance (depth ≤ D_max, §6)
```

Key identity rule:

- **Rule NC-1 (fractal uniformity).** Every instance — root or nested — uses the same four-artifact set, same FSMs, same interface. There is no special "sub-SOP mode". A child's `task-graph.json` lives in the parent workspace under a scoped path; formats are identical.

---

## 2. Binding & Lifecycle Coupling

- Parent issues Invocation (HALT-03 §4.1) → child runs FSM-T inside parent node N's `RUNNING` span.
- Child terminal statuses map to parent transitions:

| Child Result status | Parent-side handling |
|---|---|
| `done` / `done_with_gaps` | N: `RUNNING → VERIFYING`; child artifacts enter normal verification (V-level per parent spec). Gaps become explicit parent follow-up items, never silent |
| `blocked(ask:…)` | Question forwarded up the chain (§4); N: `RUNNING → BLOCKED(gate)` |
| `failed(<class>)` | Parent retry matrix applies to N as if the child were an executor death (HALT-02 §7); partial outputs preserved |

**Rule NC-2 (no bypass).** A parent MUST NOT consume child artifacts before the child reached a terminal status AND parent-side verification ran. Reading early for coordination is fine; *committing* early is INV-6 violation.

---

## 3. Namespace & Write Isolation

Child instance scope within parent workspace W:

```
W/
├── task-graph.json              # parent graph; N-042 carries child_ref
├── instances/
│   └── inv-20260825-1940-0007/
│       ├── task-graph.json      # child's own graph (nodes N-042.x)
│       ├── journal.jsonl        # child journal (own seq space)
│       ├── checkpoint.json
│       ├── artifacts/…
│       └── contracts/, steering/inbox.md, docs/…
```

Rules:

- **Rule NS-1 (scoped writes).** The child may write only under its instance directory (+tmp) plus whatever authority_grants explicitly widen. Parent files are read-only to children.
- **Rule NS-2 (id threading).** Child ids are hierarchical (`N-042.3`) but references across boundaries use full invocation-qualified form (`inv-…#N-042.3`) so flat grepping stays unambiguous.
- **Rule NS-3 (journal independence).** Seq numbers are per-journal. Cross-references cite `(invocation_id, seq)`. No global lockstep is required — nesting must not create write-contention between levels.

---

## 4. Questions & Authority Flow (ask propagation)

When a child hits a gate/ask condition:

1. Child persists the question (steering inbox + journal), enters `BLOCKED`.
2. Parent's next frontier/heartbeat pass observes blocked child → forwards via its own channel upward, attaching context breadcrumb (which goal depends on this).
3. Answer arrives top-down through steering channels and is journaled AT THE LEVEL that receives it, then propagated down as AMENDMENT events.

**Rule QA-1.** An unanswered question blocks exactly the dependent subtree, never the whole task by default (parallel branches continue unless dependency-coupled).
**Rule QA-2.** Answers MUST NOT be delivered verbally into a dying session only (AX-1): they go through durable channels; see HALT-09.

---

## 5. Failure Containment (INV-8 mechanics)

- Child death mid-flight = well-defined signal to parent (orphan detection via heartbeat timeout / exit status): parent runs R4-orphan equivalent for that node.
- Partial child outputs remain valid units (skip-by-evidence) IF registered; unregistered fragments get quarantined per R4-tail, not deleted.
- Retry of a failed child = fresh invocation with amended contract referencing prior partials ("skip what verifies").
- Cascades stop at the first level with decision authority: a child NEVER retries its own fatal class beyond strike policy; it reports upward instead (FE-1).

---

## 6. Depth & Complexity Discipline

- **Rule DP-1 (max depth).** Default `D_max = 3` (root → child → grandchild). Deeper requires a Decision Record justifying why flattening won't work. Deep hierarchies multiply recovery surface and context hops; most "need" for depth dissolves into better decomposition.
- **Rule DP-2 (width over depth).** Prefer many small siblings over deep chains when dependencies allow (parallelism + blast-radius reduction).
- **Rule DP-3 (leaf simplicity).** Leaf SOPs SHOULD have linear phase machines; branching sophistication belongs higher where state is visible.

---

## 7. Anti-Patterns

- AP-N1 Parent parses child internals "just this once" (breaks encapsulation; do it via interface fields or don't).
- AP-N2 Child inherits parent conversation context wholesale (INV-7 breach; contracts bound inputs).
- AP-N3 Implicit coupling by file layout luck ("the child happens to write where parent reads") instead of declared artifacts.
- AP-N4 Recursive self-dispatch loops (an SOP invoking itself without progress metric) — forbidden; every nesting edge must reduce distance-to-goal in the parent graph (checked at plan review).

---

*End of HALT-06. Next: HALT-07 — parallel dispatch of many executors.*
