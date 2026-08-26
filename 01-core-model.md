# HALT Core Model — Hierarchical Automaton for Long-horizon Tasks

*An Evidence-Aware Execution & Recovery Protocol for Long-Horizon Agents*

- **Spec ID:** HALT-01
- **Version:** 1.0.1 (2026-08-25) — semantics hardening after four external reviews
- **Status:** Stable
- **Audience:** implementers and operators of long-horizon task systems built on LLM agents; equally applicable to human-only, human+agent mixed, and agent teams.
- **Companion documents:** HALT-00 (index), 02 (lifecycle FSM), 03 (SOP interface), 04 (persistence layout), 05 (recovery), 06 (nesting), 07 (parallel dispatch), 08 (roles), 09 (human gates & steering), 10 (memory store), glossary, provenance.

The key words MUST, MUST NOT, SHOULD, MAY, and REQUIRED are to be interpreted as described in RFC 2119.

A conformance claim for HALT means: all MUST-level rules of HALT-01 through HALT-10 hold for the claimed scope.

---

## 1. Purpose and Design Stance

HALT turns "run a long task with an AI agent" into **operating a durable state machine**. Its premise:

> An agent's context window is RAM (volatile); the workspace is disk (durable). Any important state MUST live on disk. A fresh session MUST be able to resume the task using nothing but the workspace.

HALT answers six questions at every moment of a task's life (this mapping is the spine of the whole specification):

| # | Standing question | Answered by |
|---|---|---|
| Q1 | What state am I in? | Node lifecycle states + journal (HALT-02, HALT-04) |
| Q2 | Under what condition did I enter it? | Transition guards recorded as journal events (HALT-02) |
| Q3 | What irreversible changes exist? | Side-effect classification S0–S3 (§6 here) + receipt records |
| Q4 | Which changes are durably saved? | Commit rule + artifact registry (§5, HALT-04) |
| Q5 | What might be lost? | Uncommitted-tail detection at recovery (HALT-05 §3) |
| Q6 | What am I allowed to do next? | Frontier computation + transition function (HALT-02 §5) |

The operative question of a resuming agent is therefore **never** "where was I?" but always:

> **"Where is my last provably stable position?"**

---

## 2. Execution Model (Axioms)

All HALT rules derive from five axioms about LLM-agent execution environments. They are assumptions, not aspirations: designs that violate them fail in practice.

- **AX-1 Volatility.** An agent's working memory (conversation context) MAY be lost at any moment, without warning, and without the possibility of a graceful goodbye. Only content written to the workspace survives. *(Every Hermes/app crash, quota death, or closed window.)*
- **AX-2 Non-determinism.** Repeating the same action MAY produce different results (model sampling, external service drift, timing).
- **AX-3 Untrusted self-report.** An agent's statement about its own past or others' actions ("I did X", "worker finished Y") has **zero evidential weight** until verified against the workspace or environment. This applies to the agent itself, to sub-agents, and to human reports.
- **AX-4 Arbitrary interruption point.** An interruption MAY occur between any two elementary operations. No multi-step sequence is atomic unless the protocol explicitly makes it recoverable as a unit (INV-3).
- **AX-5 Time variance.** Environmental conditions (API quotas, model health, failure rates) are period variables. Measured failure rates MUST be treated as valid only for their measurement window. *(Empirically: identical templates showed 25% → 75% worker first-death rates within one hour.)*

---

## 3. Definitions

Terms defined here are used with exactly these meanings in all HALT documents. Each concept has exactly one definition; synonymous loose usage is a spec violation.

- **D1 Agent.** Any entity that executes steps of a task by performing Actions: an LLM-agent process, a human, or a group acting in a defined role. HALT rules are role-based, not species-based.
- **D2 Task Instance.** One bounded undertaking governed by one root SOP invocation, uniquely identified by `task_id`, living in exactly one Workspace.
- **D3 Workspace (W).** The durable directory tree holding ALL persistent artifacts of a Task Instance. If W is lost and no replica exists, the task is unrecoverable by definition; W MUST therefore be treated as the task's life.
- **D4 Task Graph (G).** The directed acyclic graph `G = (V, E)` of Work Nodes for a Task Instance. Edges encode dependencies. G is created at task INIT and only ever extended or annotated — completed structure is never deleted (history preservation, MAGE-style branching is expressed through node attributes, not graph rewrites).
  **Modeling note (iterative work).** G is a DAG over *node instances*, and this is sufficient for iterative domains: research loops, revision cycles, and "re-do the analysis after changing the hypothesis" are modeled by *appending successor nodes* (N12 replan / N14 successors), each carrying forward references to what it supersedes. Iteration is thus **unrolled in time** rather than drawn as a cycle — which is precisely what makes each loop turn auditable and resumable independently. A cycle in the *intent* of the work corresponds to a potentially unbounded chain of node instances in the *graph*; budget rules bound the chain.
- **D5 Node (v ∈ V).** A unit of work with: stable `node_id`; a Spec (goal, inputs, acceptance criteria, constraints, budget); dependencies; a lifecycle State; attempt counter; and registered Artifacts. The minimal schedulable unit.
- **D6 Node Spec.** The immutable contract of a node: what "done" means. Written BEFORE execution starts; changed only via an explicit Amendment journal event (never silently).
- **D7 Action.** One elementary step performed by an Agent inside a running node: one tool call, one file write, one human operation.
- **D8 Side Effect.** Any change outside the agent's own head: file writes, deletions, external service calls, messages sent. Classified S0–S3 (§6).
- **D9 Journal (J).** The append-only sequence of committed Events for a Task Instance. Appended records are IMMUTABLE. Corrections are new records that supersede, never edits of old ones. The journal is the task's flight recorder.
- **D10 Event.** One committed journal record: `{seq, tx_id?, ts, actor, kind, payload}`. Kinds include: STATE_TRANSITION, ARTIFACT_REGISTERED, DECISION, AMENDMENT, RECEIPT (proof of external effect), NOTE, HEARTBEAT.
- **D11 Checkpoint (K).** A small, cheap, machine-readable pointer document (JSON): current FSM positions, frontier summary, counters, budgets, mode flags. K is a **cache** regenerated from Journal + disk; it is NEVER the source of truth (INV-2).
- **D12 Artifact.** Any file/content produced by task work, registered in the Artifact Registry with: `artifact_id`, path, producing node, checksum (or size+mtime class), and status.
- **D13 Evidence.** A verifiable observation of disk or environment obtained by the verifier itself: read-back, directory listing, checksum, query result. Contrast D14.
- **D14 Claim.** A verbal/written assertion that something is true or was done. Zero standing as proof (AX-3).
- **D15 SOP.** A named, versioned automaton module conforming to the interface of HALT-03. An SOP is data (specification), not an embodied process: any Agent holding the spec can execute or resume it.
- **D16 SOP Instance.** One runtime occurrence of an SOP bound to a scope (root task or a parent node), owning a subgraph of G, a slice of the Journal namespace, and a Checkpoint slice.
- **D17 Frontier.** The set of nodes whose dependencies are satisfied and whose State permits starting. Computed from the Task Graph; the ONLY legal place to pick new work.
- **D18 Interruption.** Any unplanned termination of an Agent's operation at an arbitrary point (AX-4): crash, killed session, exhausted budget, vanished worker, human closing the app.
- **D19 Recovery.** The fixed procedure (HALT-05) that returns the Task Instance to a consistent state in which a Frontier exists and one node can be legally started.
- **D20 Memory Store (M).** The durable, cross-task knowledge base (entries addressed by stable IDs), governed by HALT-10. Distinct from the Task Instance's own artifacts.
- **D21 Decision Record.** A journal EVENT capturing a choice: options considered, the decision, rationale, and the source of authority (autonomy granted / user ruling / rule citation).
- **D22 Steering Input.** Any instruction arriving during execution from a human or higher authority. It is ALWAYS logged immediately as a journal event (survives interruptions) before being acted upon (HALT-09).
- **D23 Approval Gate.** An explicit wait-for-human guard attached to a specific transition of a specific node or SOP (HALT-09).
- **D24 Contract.** The complete input package handed to an executing agent for one bounded episode: node Spec + relevant evidence pointers + budget + reporting requirements (HALT-07 §4).

---

## 4. The Four Persistent Artifacts

A conforming Task Instance maintains exactly these durable structures in its Workspace (layout in HALT-04):

### 4.1 Task Graph (`task-graph.json`)
Machine-readable DAG of nodes (D5) with Specs, dependencies, states, attempt counts. Created at INIT; extended thereafter. Human-readable companion view optional.

### 4.2 Journal (`journal.jsonl`)
Append-only event log (D9/D10). One JSON object per line. Sequence numbers monotonically increase. Writers append; nobody edits. This is the answer to Q1/Q2 and the raw material for audits.

### 4.3 Artifact Registry (`artifacts.json` + files under `artifacts/`)
Every produced item registered (D12) with checksum-class identity. Registration happens together with the commit (§5). Answers Q3/Q4 together with the journal.

### 4.4 Checkpoint (`checkpoint.json`)
The pointer cache (D11): `{task_id, updated_at, fsm_positions, frontier_ids, counters, budgets, modes, next_hint}`. Cheap to rewrite wholesale on every commit. Losing it is harmless if the journal survives (recovery rebuilds it, HALT-05).

**Rule C-ART.** All four MUST exist for every Task Instance beyond trivial size (see §8 tiering). All four MUST live inside W. Nothing task-critical lives only in conversation context.

---

## 5. The Commit Rule (micro-commit protocol) — recoverable, not atomic

The central operational discipline. Every unit of progress follows:

```
1. DO     perform one Action producing one bounded output
2. WRITE  persist the output (file/artifact)
3. VERIFY read back what was written; compare against intent
          (checksum / size / spot-content — proportionate to criticality)
4. COMMIT append ONE journal Event (with seq, ts, actor, kind, payload refs)
5. POINT  update checkpoint.json (cheap pointer refresh; MAY be batched
          to every N events or T seconds for high-throughput loops)
```

**Terminology precision (normative):** this is a ***recoverable transaction*, not an ACID transaction.** POSIX gives atomicity for single-file rename, not across the four artifacts; an interruption between steps leaves a window that recovery (HALT-05) resolves by replay and adjudication. HALT's claim is: *the window's contents are always classifiable and resolvable* — never "no window exists". Implementations wanting tighter guarantees MAY put journal+registry in one SQLite database (journal as WAL); JSONL remains the canonical interchange/export format.

Consequence of the above (single-writer discipline): **the Journal admits exactly one writer at a time per Task Instance.** At Tier ≥1 where a second session might appear, implementations SHOULD use a coordinator lease (`lease.json` with expiry; holder appends; expired lease ⇒ newcomer must run RECOVERING first and take the lease before writing). Absent a lease mechanism, two concurrent writers is undefined behavior and any deployment allowing it is non-conformant.

- **Rule C-UNIT.** A work unit MUST be small enough that (a) its output fits one write call, (b) losing it in-flight costs at most its own budget. Empirical basis: workers asked to produce large payloads in one step stall in reasoning and die in field use); micro-append protocols survived.
- **Rule C-VERIFY.** Step 3 uses Evidence, not the feeling of having written (AX-3). Read-back is mandatory for S0 outputs feeding downstream nodes; proportionate spot-checks suffice for bulk low-risk data, with full verification deferred to the node's VERIFY phase (HALT-02).
- **Rule C-TX.** A logical change spanning multiple Events shares one `tx_id`. Recovery treats a dangling `tx_id` as: complete it if completion is deterministic from surviving parts; otherwise quarantine the partial parts and mark affected nodes PENDING again (never silently drop).
- **Rule C-NOREWRITE.** Nobody edits journal lines or overwrites registered Artifacts. Supersession is a new Event referencing the old. Failed paths are quarantined (moved aside, marked), not erased — failed experience is an asset (MAGE Revise keeps failed branches as siblings).

**Definition (stable position).** The *last provably stable position* of a Task Instance = the highest journal prefix whose Events all carry verified Effects. Everything after it is *uncommitted tail*: potentially lost, never trusted, examined at recovery (Q5).

---

## 6. Side-effect Classification (answers Q3)

Every Action's Side Effect is classified before execution:

| Class | Kind | Examples | Discipline |
|---|---|---|---|
| **S0** | Local, additive | New files inside W; appends | Full commit-rule coverage; freely redoable |
| **S1** | Local, destructive | Overwrite/delete/move of prior artifacts | Backup-or-quarantine FIRST (`old/` copy + registry note), then act; restore path always exists |
| **S2** | External, replayable | Read-only queries, searches, idempotent fetches | Execute freely; record result as Event; redo is cheap and safe |
| **S3** | External, non-replayable | Sending messages, one-shot purchases, public posts, notifications to humans | MUST pass an Approval Gate OR be designed out; if executed: capture RECEIPT evidence (ID/screenshot/hash) and journal it BEFORE proceeding |

**Rule C-S3.** A conforming design MINIMIZES S3 surface. Any S3 action lacking a receipt path is a spec violation. Interruptions between S3 execution and receipt capture are handled at recovery by treating the effect as *probably-done-unverifiable* and surfacing it for human adjudication (HALT-05 §6).

---

## 7. The Execution Evidence Ladder

When sources disagree about **task execution facts**, lower rank wins:

```
1. Direct Evidence        (verifier's own read-back / disk scan / checksum)
2. Registered Artifacts   (registry + actual files, mutually checked)
3. Journal Events         (committed records)
4. Checkpoint             (pointer cache)
5. Summaries              (progress docs, status reports, dispatch texts)
6. Claims                 (any agent's or human's unverified statement)
```

Three distinct properties this ladder ranks — never conflate them:

> **existence ≠ provenance ≠ correctness.**
> A file existing proves *existence*. A registry chain proves *provenance* (who produced it, under which spec version). Neither proves *content correctness* (see scope note below).

**Rule C-TRUTH.** Conflict resolution ALWAYS walks this ladder. "Disk adjudicates" is the standing tie-breaker for **existence disputes**: when any doubt exists about whether work happened, inspect the Workspace, not anyone's memory or report. *(Battle-tested rule: worker completion claims were repeatedly falsified by disk scans; conversely, "lost" work was repeatedly found on disk after supposedly fatal crashes.)*
**Rule C-TRUTH-b (existence is not attribution).** Recovered unregistered files gain, at most, *quarantined candidate* status until provenance validation succeeds (right producer? right spec version? right inputs? current, not stale?). Disk settles that something exists; only provenance checks settle what it is.

**Scope note (execution truth vs content truth).** The ladder ranks *evidence about the execution state of the task* — did an action happen, does an output exist, who committed what. It deliberately does NOT rank *the intellectual correctness of artifact contents*: "the file exists and is registered" proves provenance and availability, never that a paper's claim, a theory, or a strategic judgment inside it is true. Content-level validity for knowledge work is governed by verification levels (HALT-02 §4) — V1/V2 check structural and provenance properties mechanically; substantive correctness requires domain-appropriate review (V2 audit with rubric or V3 human authority), with residual uncertainty recorded honestly (e.g., in Decision Records and memory-store entries). Conflating the two ladders is a category error this note exists to prevent.

---

## 8. Invariants

These ten invariants are the normative backbone of HALT. Every other rule exists to uphold one or more of them. (Normative-strength classes: see §8b.)

- **INV-1 Durability.** After every commit, the Task Instance's state is fully reconstructible from W alone. No procedure MAY depend on information existing only in some session's context.
- **INV-2 Single Source of Truth.** The Journal is the authoritative mutable record; registered Artifacts are the authoritative content store; checkpoints, summaries, and reports are caches/views. A checkpoint contradicting the journal loses.
- **INV-3 Recoverable Units.** Every multi-step logical change is either (a) reducible to per-step commits under the Commit Rule, or (b) wrapped in a tx_id whose dangling state recovery knows how to resolve (complete deterministically, else quarantine). There is no third option.
- **INV-4 Monotonic History.** Completed work never silently regresses. IDs are permanent. Failures and corrections are new records; history is append-only. Progress may *branch*, never *rewind invisibly*.
- **INV-5 Evidence-based Resumption.** From any stable position, re-driving the Frontier MUST converge to the goal, regardless of how many prior attempts died anywhere. Mechanism: skip-by-evidence under each node's `resume_policy` (HALT-02 §11) — deterministic outputs may be skipped on verified existence; generative/judgment outputs may be skipped only when produced under the *current* spec version and not invalidated by amendments; S3-adjacent and subjective drafts MUST NOT be skipped without explicit policy.
- **INV-6 Evidence-gated advancement.** A node crosses any verification-requiring transition only on Evidence produced by an entity other than its producer, with independence at least at level I1 (fresh context); higher I-levels per HALT-02 §4b. (executor ≠ verifier is the floor, not the definition.)
- **INV-7 Bounded Context.** Every Agent activation consumes a bounded input: the Contract (node Spec + pointed-to evidence), never the whole history. Detail is compressed at segment boundaries and re-expandable on demand (HiAgent pattern). A node whose Spec cannot fit its executor's budget MUST be decomposed further — this is a decomposition error, not an execution error.
- **INV-8 Encapsulated Failure.** A failed child (sub-SOP instance, worker, sub-task) leaves its parent's state CONSISTENT: the parent sees a well-defined child terminal state plus registered partial outputs — never corruption, never silence. Parent decides retry/replan/escalate (HALT-06 §5).
- **INV-9 Auditability.** For any current state there EXISTS a journal walk explaining how the system got here: who acted, when, on what evidence, under what authority. Decisions of consequence are Decision Records (D21).
- **INV-10 Least privilege.** Authority over writes is partitioned by Role (HALT-08): e.g., auditors are read-only over protected artifacts; workers write only their own scoped outputs; only the coordinator mutates the Task Graph structure. Where the runtime can enforce scopes technically it SHOULD; contract-declared scopes alone are a policy control and MUST be labeled as such in Tier ≥1 audits.

## 8b. Normative Strength Classes

Not all normative statements carry equal epistemic weight. Every MUST/SHOULD rule in HALT belongs to exactly one class; conformance claims cite the class:

| Class | Meaning | Examples |
|---|---|---|
| **Invariant** | Logical backbone; violating = protocol broken | INV-1..10 |
| **Normative Rule** | Required procedure; derivable from invariants + field evidence | commit rule steps, R0–R7 order, FSN transitions |
| **Reference Policy** | Default parameter values with stated rationale; MUST be overridable via checkpoint with recorded reason | three-strike cap=3, first-death 25% mode threshold, heartbeat timeout 3× median unit time, D_max=3 |
| **Implementation Heuristic** | Practitioner advice, expected to be tuned per environment | probe batch size, compaction cadence |

Rule: **a parameter cited from a single field observation MUST NOT be classed above Reference Policy.** Reference policies carry their measurement window in the checkpoint (`policy_params` block). This keeps heuristics honest without weakening real invariants.

---

## 9. Conformance Tiers

Not every undertaking needs the full apparatus. HALT defines three tiers; the tier is chosen at INIT and recorded in the checkpoint.

- **Tier 0 — Trivial.** Single-session, low-value, restart-from-scratch is acceptable. MAY skip journal/checkpoint entirely. Exit condition: expected duration > 1 session or value > casual ⇒ upgrade to Tier 1.
- **Tier 1 — Standard.** Full four-artifact set (§4), Commit Rule, side-effect discipline, standard recovery. Default for multi-session tasks.
- **Tier 2 — Critical/Fleet.** Tier 1 PLUS: mandatory tx_id grouping for multi-artifact changes, receipts required for all S2/S3 (not just S3-non-replayable), periodic audit walks (every K commits or T wall-time), and dual-write of the journal (primary + mirror copy flushed per commit) for hostile-environment durability.

---

*End of HALT-01. Next: HALT-02 defines the node/task lifecycle FSMs that these artifacts track.*
