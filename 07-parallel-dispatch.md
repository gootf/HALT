# HALT Parallel Dispatch

- **Spec ID:** HALT-07
- **Version:** 1.0.1 (2026-08-25) — semantics hardening after four external reviews
- **Depends on:** HALT-02 §7 (retry matrix), HALT-04 (ledgers, write partitions), HALT-06 §5 (containment)

Governs one coordinator running many concurrent executors (workers/sub-agents/human helpers) against independent units. All rules here generalize observations from ~40-slot production waves where worker first-death rates swung 25%→75% within an hour.

---

## 1. Preconditions for Parallelizing a Node Set

All MUST hold (else run serially):

- P1 Units are genuinely independent: no shared mutable target files; merge happens later at a defined join point.
- P2 Each unit's output lands in a disjoint write scope (`artifacts/<node>/<unit>` or append-only sharded ledgers).
- P3 Unit Contracts are self-contained (INV-7): worker needs ONLY its contract + pointed evidence — no access to coordinator conversation.
- P4 Join verification exists: a deterministic merger/validator that adjudicates all shards by content keys, not arrival order.

---

## 2. Contract Issuance Rules

- **Rule PD-C1 (self-addressing contracts).** The contract file contains everything: unit inventory, output paths, schema, hard constraints, reporting duties, skip-by-evidence instructions. Worker's first action = read own contract file. Coordinator dispatch messages stay one line ("read X, execute").
- **Rule PD-C2 (generated, never hand-copied).** Contract/unit inventories are rendered by script from the ledger/index (zero-transcription rule). Hand-typed unit lists were twice observed to silently drop items — banned.
- **Rule PD-C3 (generator self-check).** The generator asserts post-write: filenames unique across concurrent batches (composite keys, not bare counters — a bare part number collision once misrouted 12 workers), inventory matches plan, sample re-read matches. Three checks or no dispatch.
- **Rule PD-C4 (bounded payloads).** Per-call output expectations sized so no single step requires heroic effort (C-UNIT); batch workers instructed micro-append cadence with flags per completed unit.

---

## 3. Claiming & Slot Accounting

- Work slots are recorded in checkpoint (`active_contracts[]`) at issuance, BEFORE sending.
- A slot has exactly one owner; duplicate claims resolved by earliest contract id, loser told to stand down (cheap idempotence guard).
- On completion notice (or heartbeat timeout), slot closes after **disk adjudication**: verify outputs exist + pass spot check; only then does the accounting flip (worker self-reports are claims).

---

## 4. Health Monitoring & Adaptive Modes

- Heartbeats: workers append per-unit ledger lines; absence > timeout threshold (Reference Policy default 3× median unit time) ⇒ **SUSPECTED_DEAD** procedure (HALT-02 RT-3): observation journaled, policy conclusion labeled as such, outputs still verified if they later appear.
- **Rolling first-death rate** = fraction of newly dispatched slots failing before any output, measured over trailing window (e.g., last 8 resolutions).
- Mode ladder — thresholds are Reference Policies carried in checkpoint `policy_params` with their measurement window; the *structure* below is normative, the numbers are defaults:

| Mode | Condition (default) | Behavior |
|---|---|---|
| A Normal | rate ≤ `mixed_threshold` (default 0.25) | rolling dispatch; one automatic retry per dead slot (with anti-stall clause) |
| B Mixed | rate > `mixed_threshold` | dead/unfinished slots pulled back to coordinator-executed queue; new dispatch continues only for untouched batches; no blind re-dispatch into the degraded window |
| C Halt-dispatch | `halt_after_consecutive_env_failures` (default 2) | stop issuing; let in-flight land; resume only after health probe passes (RT-1) |

- **Rule PD-H1.** Rate is computed continuously, not at wave end — late detection was a real observed cost.
- **Rule PD-H2.** Environment walls are diagnosed from error signatures (e.g., daily-quota vs rate-limit) BEFORE tuning anything; wrong diagnosis wastes the remaining window.
- **Rule PD-H3 (probe-before-resume).** After any halt, resume with a small probe batch; full rate only after probes survive.

---

## 5. Join & Merge Discipline

- Merger sorts by numeric keys parsed from ids (string sort lies: `W10 < W9`).
- Merge re-keys outputs canonically (parallel writers cannot coordinate sequence numbers by design).
- Unit flags: a unit counts complete iff flag/output present AND validates; partial units contribute their verified subset (ledger granularity), remainder re-dispatched with explicit skip-list.
- In-flight shards are excluded from formal validation passes (validating half-written shards yields false FAILs — observed).
- **Rule PD-J1 (v1.0.2).** *Artifact-presence verification.* A worker's terminal status (`completed`/`done`) is evidence of nothing: it describes the worker's self-report, not the world. A node may transition to DONE only after the coordinator verifies artifact presence on disk (existence, and checksum where the contract declares one). **Silent no-output death** — terminal success with zero artifacts — is a first-class death mode for LLM-type executors, distinct from kill/timeout because no error surface exists; detection is disk-side only. Dispatch contracts SHOULD therefore require incremental writes (skeleton-first, then per-section appends) so that even silent deaths leave recoverable residue on disk. *(Empirical: field run I-7 — three consecutive fan-out rounds returned completed with zero files; reading budget crowded out writing budget.)*

---

## 6. Coordinator Context Protection

Batch completion notices flood coordinator context (real bottleneck >16-way concurrency).

- Notices land in a completion log file; coordinator ingests summaries, not raw transcripts.
- Worker transcripts are discarded after audit-grade extraction (fresh-context principle, LHH).
- Escalation to human carries: slot id, last journal refs, disk findings — never raw dumps.

---

## 7. Mid-flight Steering Recall

When a steering input invalidates in-flight work (HALT-09 §3):

1. Affected slots marked recalled in checkpoint; their scopes annotated (recalled-by-ref).
2. Workers self-terminating gracefully: contract contains recall-check instruction ("if steering/recall file says your batch id, stop and report").
3. Already-landed outputs judged per unit: still-valid units stay (skip-by-evidence protects them); invalidated ones quarantined with reference to the amendment event.
4. Re-dispatch only after specs amended (TG-1) and frontier recomputed (FR-2).

---

## 8. Human Helpers in Parallel Mode

Humans may hold slots: same contract discipline, adjusted budgets/cadence; their completions pass identical disk adjudication (AX-3 applies to humans too, kindly). Gate-waits by humans (approval roles) are tracked like BLOCKED nodes with wake conditions, not like slots.

---

*End of HALT-07. Next: HALT-08 — roles, authority partitioning, team composition.*
