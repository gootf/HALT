# Provenance — Where Each HALT Mechanism Comes From

Every non-trivial mechanism in HALT cites its origin: cited paper (all six read in full from arXiv/ACL PDFs, 2026-08-25), field practice (a prior knowledge-system production run, ~40 parallel worker slots, five-plus dispatch waves), or this design (novel synthesis).

## From Statecharts (Harel 1987) — hierarchy formalism
- SOPs-as-state-machines containing state machines → HALT-06 composition model
- Transition-guard discipline → FSM-N transition table with guards + evidence refs

## From AgentR (arXiv 2608.15264) — durable workflow semantics

> **Mapping-strength note:** AgentR is a small BullMQ/Redis/Postgres prototype evaluated on ~10 projects / ~130 jobs. What transfers here is its *design vocabulary* (FSM properties checklist, failure taxonomy, recovery-precondition pattern), not experimental proof of those patterns at fleet scale.

- Observable/Durable/Recoverable/Auditable as FSM properties checklist → HALT-02 §1 requirements recap
- Six-state processing machine with RE_INITIATED-style resumption → generalized into FSM-N RETRYABLE/BLOCKED paths
- Failure taxonomy (transient/permanent × retry/resume matrix) → HALT-02 §7 retry policy matrix (extended with agent-health dimension)
- Recovery = precondition checks then explicit transition → R4-orphan / R7 handoff shape
- Audit trail via timestamped transitions → journal event contract (though seq, not ts, is ordering authority)

## From MAGE (arXiv 2606.06090, Microsoft) — memory as execution state

> **Mapping-strength note:** MAGE operates on the agent's *context-side* state tree, not on disk artifacts. HALT borrows its structural ideas (boundary compression, validate-before-trust, revise-by-branching); the disk-journal realization is HALT's own, not an algorithm transfer.

- "Reconstruct current execution state; don't similarity-retrieve the past" → the standing-question reframing (HALT-01 §1)
- Two-layer raw/summary tree with boundary compression → INV-7 detail-on-demand; SOP phase compression points
- Grow/Compress/Maintain/Revise operations → commit rule (grow), verify-phase (maintain-before-trust), quarantine-with-successors (revise-as-branch-not-overwrite)
- Monotonic node ids; children expose failed alternatives → INV-4 append-only history; N14 successor references
- Error isolation by branching siblings → S1 quarantine discipline; AP list in HALT-05 §7

## From MemChar (arXiv 2606.06448, Stanford) — systems economics of memory
- Construction cost dominates; hot path must be cheap/deterministic → checkpoint-as-cache design (CK-2); ledger-first recovery (05 §6)
- Background maintenance with admission control → consolidation passes never blocking task hot paths (10 §4)
- Cross-session feasibility as hard constraint → tier budgets; sharded journals for large tasks
- Cost-growth slope awareness → bounded index rule ME-4

## From LongHorizon-Harness (arXiv 2608.01964, Alibaba) — Manage-Execute-Audit
- Task state maintained outside execution context, advanced only by verified facts → INV-2/INV-6 core
- Manager without environment access; executor-only mutation; read-only auditor → role authority partitions (08 §1–2)
- Subtask contracts (goal + acceptance criteria + constraints + evidence) → Contract D24 (03 §4.1)
- Executor report = unverified claim; auditor assigns completion + integrity statuses → VERIFYING state machinery; V-levels; integrity clean/suspect/violation
- ask-route as first-class control outcome → BLOCKED(gate)/ask propagation QA-1..2 (09)
- Fresh-context budget-bounded episodes; trajectories discarded → INV-7 context bounding; coordinator context protection (07 §6)

## From SciBORG (arXiv 2507.00081) — schema-state memory
- Pseudo-FSA memory: state as schema variables/transitions, not narrative → checkpoint/graph JSON schemas over prose; "state initialization before execution" (structured init beat unstructured 85% vs 65%)
- Benchmarking by state progression (output/state/path modalities) → conformance checklist A3 exercises live interruption tests, not paper compliance
- Agents invoking agents as tools; MCP contrasted as stateless → nesting interface (06) requires durable child state, unlike pure message passing

## From HiAgent (ACL 2025) — hierarchical working memory
- Subgoal chunks: full detail within active subgoal, summaries behind → phase-machine granularity; ledger units inside coarse nodes (02 §2.3)
- Summarize-on-completion s_i = S(g_i, …); re-expand on demand → detail-on-demand clause in INV-7
- Cross-trial vs in-trial memory split → W vs M boundary (10 §1)

## From field practice — the scars

> **Evidence status note (added after external review):** the entries in this section are *practitioner evidence from one production run* — internally consistent, externally unreplicable. They justify Reference-Policy defaults (HALT-01 §8b), never Invariants. Where a rule below feeds a MUST-class clause, only its structural content is normative; its numeric parameters are overridable policy.

Each maps to a specific rule:
- Workers stalling in reasoning before first write (5 dead types catalogued) → C-UNIT micro-payload sizing; PD-C4 anti-stall cadence; FSN heartbeat timeouts
- First-death rate swinging 25%→75% within an hour (period variable) → AX-5; PD-H rolling-rate mode ladder A/B/C
- Hand-copied unit lists silently dropping items twice → PD-C2 zero-transcription + PD-C3 generator self-checks
- Bare part-number filename collision misrouting 12 workers → PD-C3 composite-key naming assertion
- Worker completion claims falsified by disk scans (and vice versa: "lost" work found on disk) → truth ladder rank 1; RC-2 disk adjudicates
- Validating in-flight shards producing false FAILs → join exclusion of in-flight shards (07 §5)
- String-sort merging W10 before W9 → numeric-key merge rule
- Steering sent to a session that died before ingestion → ST-2 restatement protocol + durable inbox mandate (09 §2–3b)
- Ledger freshness on external references (mtime changes invalidate citations) → DOC-LEDGER (04 §7) + MEM-R freshness gate generalization
- Three-strike escalation and method switching → FSN-3, RT-2
- Quota-wall misdiagnosis burning a whole window → PD-H2 diagnose-from-signature-before-tuning; probe-before-resume PD-H3

## Novel synthesis (this design, not directly citable)
- The six standing questions mapping (Q1–Q6) as spec spine (HALT-01 §1)
- Truth hierarchy as explicit ranked ladder with tie-breaker (C-TRUTH), plus the execution-truth/content-truth scope separation
- Conformance tiers 0/1/2 as ceremony throttle
- Stable-position definition operationalizing 可接续三条件 (valid record ∧ verifiable effects ∧ explicit next-transition)
- Interrupted-steering normative walkthrough end-to-end (09 §3b)

## External review adjudication (2026-08-25, independent AI critique of a draft)
An external AI reviewed this spec without task context. Verdicts after independent analysis:
- "DAG assumption too strong for iterative work" → partially accepted: mechanism existed (successor chains) but was undocumented; fixed via D4 modeling note (iteration unrolled in time).
- "Open-ended tasks lack verification model" → mostly already covered (V3, VR-1, 11§D-4); operational gap real → VR-3 added.
- "Evidence hierarchy fails for knowledge tasks" → rejected as misreading (ladder ranks execution truth, not content truth) but revealed confusion risk → C-TRUTH scope note added.
- "Missing goal-evolution layer" → partially accepted: authority routing already correct by design; re-scoping formalized as first-class event → HALT-02 §10 GE-1..4.
- "Whole architecture lacks empirical validation" → correct and pre-acknowledged; sharpened into 11§D-6 with explicit future-work statement.

## Source problem document
The source problem document (a compiled requirements discussion): supplied the HSM sketch, transactional-node requirement (Preparing_Checkpoint→Committed), recovery-controller layer, 接续判断三条件, unified-interface requirement (SOP.call…return), and the research survey that motivated reading all six papers. All absorbed above.

## External review round 2 (2026-08-25 evening; 参考1–4, independent AIs)
Adjudicated changes now in v1.0.1:
- "Truth hierarchy misread as knowledge-truth ranking" (参考1/参考2) → renamed **Execution Evidence Ladder** + existence≠provenance≠correctness clause + C-TRUTH-b.
- "Normative strength inflation: heuristics written as MUST" (参考2 P0) → new §8b strength classes; three-strike/25%/heartbeat/D_max demoted to Reference Policies (`policy_params`).
- "presumed dead conflates inference with fact" (参考2 P0) → RT-3 SUSPECTED_DEAD epistemics + optional fencing.
- "Four artifacts are not one transaction" (参考3 §A, strongest finding) → commit rule retitled *recoverable, not atomic*; journal = sole authoritative mutable record; single-writer/lease discipline added; HALT-04 atomicity note; TG-2 contradiction fixed (amendments journaled first).
- "INV-5 conflicts with AX-2 for generative outputs" (参考3 §B) → per-node `resume_policy` (HALT-02 §7b); INV-5 rewritten as evidence-based resumption.
- "V2 independence too weak" (参考2 §16) → I1–I5 verifier-independence levels + VR-0 profile recording.
- "Frontier is a black box" (参考1) → partially rejected (algorithm existed at 02§6) but expanded to full pseudocode with determinism properties.
- Provenance over-claim risk (参考3 §2) → mapping-strength notes on AgentR/MAGE; field practice marked practitioner-evidence-only.
- Roadmap v1.x (runtime+kill tests, HALT-Bench, Evidence Matrix, typed edges, Exec/Judge split, formal annex…) adopted into HALT-11 §8.
Rejected: "frontier algorithm missing" (existed), "add many more papers now" (deferred to roadmap reading list).


---

## v1.0.2 — Field-run amendments (2026-08-26)

Source: validation report `12-validation-report.md` (field run `halt-fieldrun-01`, ledger J-1..87). Four additive amendments; no architecture change.

| ID | File/Clause | Change | Empirical trigger |
|---|---|---|---|
| A-1 | 04 journal, Rule J-4 | Seq derivation at append time (`1 + max(seq)` from journal tail); cached counters non-conformant | I-3 seq-collision storm (26 dups, seqs 5–35) |
| A-2 | 04 registry, Rule AR-3 | (path, checksum) immutability; supersession requires new id or versioned path | I-4 A-N2v2/v3 inversion, 4 false integrity FAILs |
| A-3 | 07 join, Rule PD-J1 | Artifact-presence verification before DONE; silent no-output death added to death typology; incremental-write contracts recommended | I-7 subagent silent deaths ×3 rounds |
| A-4 | 11 §A11 checklist item | Audit records must be independently recomputable | I-8 auditor mis-journaling J-73/J-74 |

Rejected for this round (with reasons): per-writer seq-space partitioning (A-1 sufficient at current scale); mandatory content-hash trees (no incident demanded it). Roadmap impact: 11§8 item 1 partially satisfied at human-executability level; runtime (v1.1) converts the eight incident fixtures of 12§5 into CI tests.

---

## Evidence Matrix (v1.1)

Every mechanism's evidence status at a glance. **E1 = peer-reviewed/arXiv paper (citable)** ·
**E2 = field practice from one production run (practitioner evidence)** ·
**E3 = novel synthesis by HALT itself (design, not citation)** ·
**E4 = validated in the halt-fieldrun-01 field test** (new column — see 12-validation-report).

| Mechanism | HALT clause | Source | Class | E4? |
|---|---|---|---|---|
| Hierarchy formalism | 06 composition | Harel 1987 | E1 | — |
| FSM property checklist | 02 §1 | AgentR | E1 | — |
| Failure taxonomy + retry matrix | 02 §7 | AgentR (extended) | E1+E2 | ✓ |
| Recovery precondition → transition | 05 R4/R7 | AgentR | E1 | ✓ |
| Journal event contract | 04 | AgentR + LHH | E1 | ✓ |
| Reconstruct-state-not-retrieve-past | 01 §1 | MAGE | E1 | ✓ |
| Raw/summary two-layer memory | INV-7 | MAGE/HiAgent | E1 | — |
| Append-only history | INV-4 | MAGE | E1 | ✓ |
| Quarantine-with-successors | S1 / N14 | MAGE | E1 | — |
| Checkpoint-as-cache | CK-2, 05 §6 | MemChar | E1 | ✓ |
| Manage-Execute-Audit separation | 08 §1–2 | LongHorizon-Harness | E1 | ✓ |
| Executor report = unverified claim | VERIFYING machinery | LHH | E1 | ✓ |
| Subtask contracts | D24 (03 §4.1) | LHH | E1 | ✓ |
| ask-route as first-class outcome | BLOCKED/gates (09) | LHH | E1 | ✓ |
| Schema-state memory over prose | graph/checkpoint schemas | SciBORG | E1 | ✓ |
| Live-interruption conformance testing | A3 checklist | SciBORG | E1 | ✓ |
| Subgoal chunking + summarize-on-completion | phase granularity | HiAgent | E1 | — |
| Micro-commit anti-stall cadence | C-UNIT/PD-C4 | Prior field practice | E2 | — |
| Death-rate adaptive dispatch ladder | PD-H mode A/B/C | Prior field practice | E2 | — |
| Zero-transcription contracts | PD-C2/C3 | Prior field practice | E2 | — |
| Seq derivation at append time | 04 Rule J-4 (A-1) | **field run I-3** | E2→rule | ✓ |
| (path, checksum) immutability | 04 Rule AR-3 (A-2) | **field run I-4** | E2→rule | ✓ |
| Artifact-presence verification; silent-death typology | 07 PD-J1 (A-3) | **field run I-7** | E2→rule | ✓ |
| Audit recomputability duty | 11 §A11 (A-4) | **field run I-8** | E2→rule | ✓ |
| Five axioms / D1–D24 core model | 01 | HALT design | E3 | ✓ |
| Commit protocol DO→WRITE→VERIFY→COMMIT→POINT | 01 | HALT design | E3 | ✓ |
| Truth/Evidence ladder semantics | 01 §truth | HALT design | E3 | — |
| Two-tier consolidation (law self-hold vs attention) | n/a (workload doc) | 念位 v5 design | E3 | ✓ |

Reading: an E1 mechanism with E4=✓ has both literature grounding and field validation;
an E2→rule entry means a field-run incident forced a normative rule whose only evidence is that
incident (acceptable: the incident IS the falsification test it survived). No mechanism remains
at "author assertion" without either a source or a test.

This matrix completes roadmap item 11§8-3 ("Evidence Matrix upgrades provenance"). Items 11§8-1
(validation report) and the v1.1 runtime are likewise complete; 11§8-2 (HALT-Bench five suites)
remains open for the multi-node/parallel scope.
