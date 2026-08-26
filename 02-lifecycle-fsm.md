# HALT Lifecycle Finite State Machines

- **Spec ID:** HALT-02
- **Version:** 1.0.1 (2026-08-25) — semantics hardening after four external reviews
- **Depends on:** HALT-01 (terms D1–D24, invariants INV-1…10)

This document defines the normative automata of a Task Instance:

- FSM-N: the **node** lifecycle (a transactional state machine, §2),
- FSM-T: the **task-instance** lifecycle (§5),
- the transition-journal contract binding states to durable evidence (§3),
- frontier computation — the ONLY legal work-selection procedure (§6),
- verification levels (§4), retry policy (§7), and suspension (§8).

Notation: transitions are written `SOURCE --[event/guard]--> TARGET`. Every transition MUST emit one journal `STATE_TRANSITION` Event naming `(entity, from, to, evidence_ref)`.

---

## 1. Design Requirements Recap

From the source problem statement and HALT-01:

1. Interruption may hit anywhere (AX-4): no transition may rely on "we'll finish the sequence".
2. Only committed positions are stable (Q4); recovery asks "last provably stable position", never "where was I" (HALT-01 §1).
3. Producers' claims do not advance shared state (INV-6, LongHorizon-Harness MEA).
4. Failure must be encapsulated, not silent (INV-8).
5. Human input is a legitimate, first-class trigger (ask route), including mid-flight steering after which the session may die instantly (HALT-09).

---

## 2. FSM-N — Node Lifecycle

### 2.1 States

| State | Meaning | Invariant while here |
|---|---|---|
| `PENDING` | Exists in graph; dependencies incomplete | Nothing may start it |
| `READY` | All dependencies `DONE`; Spec complete; in current **Frontier** | May be contracted to an executor |
| `RUNNING` | A Contract is active with exactly one executor | Executor writes only its own scoped outputs; heartbeat expected on long units |
| `VERIFYING` | Executor reports finished; independent verification in progress | Verifier ≠ producer of the claim (INV-6) |
| `BLOCKED` | Execution paused awaiting an external condition: Approval Gate, missing user input, upstream failure, resource wall | Block reason recorded; wake condition recorded |
| `DONE` | Verified + committed (Commit Rule completed for its outputs) | Terminal-positive. Its artifacts are registry-stable |
| `RETRYABLE` | Attempt failed; retry policy says try again | Attempt counter already incremented; failure diagnosed in journal |
| `QUARANTINED` | Failed permanently OR superseded path kept for history | Partial outputs preserved (INV-4); successor node references it |
| `CANCELLED` | Removed from pursuit by authority decision | Reason recorded; no deletion of artifacts |

### 2.2 Transition Table

| # | Transition | Guard / Trigger | Required journal payload |
|---|---|---|---|
| N01 | `PENDING → READY` | all deps `DONE` | dep list snapshot |
| N02 | `READY → RUNNING` | Contract issued to executor | contract_id, executor id, budget |
| N03 | `RUNNING → VERIFYING` | executor claims completion | executor report ref (**Claim**, weight 6) |
| N04 | `RUNNING → RETRYABLE` | executor died / budget exhausted / hard error | death signature, attempts+1 |
| N05 | `RUNNING → BLOCKED` | gate hit / ask route chosen / resource wall | block reason, wake condition |
| N06 | `VERIFYING → DONE` | verification PASS on Evidence | verifier id, check list, artifact refs |
| N07 | `VERIFYING → RETRYABLE` | verification FAIL, fixable by re-execution | diff/diagnosis, attempts+1 |
| N08 | `VERIFYING → QUARANTINED` | verification FAIL non-fixable locally, or 3rd strike | quarantine manifest |
| N09 | `BLOCKED → READY` | wake condition satisfied (user answer, gate approval, upstream fixed) | satisfying evidence |
| N10 | `BLOCKED → CANCELLED` | user cancels while waiting | authority ref |
| N11 | `RETRYABLE → RUNNING` | re-dispatch (new contract, amended if needed) | new contract_id |
| N12 | `RETRYABLE → READY` | replan: node split/re-scope decided | amendment ref |
| N13 | `READY → QUARANTINED` | node obsolete after replan | replacement pointer |
| N14 | `QUARANTINED → PENDING*` | successor node(s) created referencing it | successor ids (*new nodes, never un-quarantine) |
| N15 | any → `CANCELLED` | root authority cancels task branch | decision record D21 |

**Rules:**

- **Rule FSN-1 (no teleport).** Only listed transitions exist. Any observed state not reachable by journaled transitions is *suspect*: at recovery it is corrected by disk adjudication (HALT-05), not trusted.
- **Rule FSN-2 (single executor).** `RUNNING` implies exactly one active Contract. Re-dispatch requires passing through N04/N07 (or proving the old executor dead via absence-of-heartbeat timeout).
- **Rule FSN-3 (escalation on retry-budget exhaustion).** Entering `RETRYABLE` a number of times reaching the node's retry budget (Reference Policy default: 3) MUST escalate: either change the execution method (different model, different decomposition, coordinator-executed) or ask the user (HALT-09 ask route). Blind identical retries beyond budget are violations.
- **Rule FSN-4 (claims don't commit).** N03 does NOT mark progress anywhere else. Only N06 (evidence-based) may create downstream `PENDING → READY` effects.
- **Rule FSN-5 (interrupt-safe by construction).** Every state above is durable within ≤2 commits of entering it (commit rule step 4–5). There is no "in-between" worth protecting because the journal IS the protection.

### 2.3 Micro-states inside RUNNING (mandatory discipline)

Inside `RUNNING`, the executor follows the Commit Rule (HALT-01 §5) per unit. For batch-type nodes the executor maintains a **unit ledger** (`artifacts/<node>/ledger.jsonl`): one line per unit item `{unit_id, status: ok|skip|fail, artifact_ref, ts}`. This makes partial progress addressable at resume ("skip-by-evidence", INV-5) without touching the task graph. Ledger writes follow S0 discipline; the node-level transition journal stays coarse.

---

## 3. Binding States to Evidence

- Each `STATE_TRANSITION` event MUST carry `evidence_ref`: journal seq / artifact id / receipt id supporting the guard. Guards evaluated on Claims alone are invalid (weight ladder, HALT-01 §7).
- Heartbeats: long-running executors SHOULD emit `HEARTBEAT` events (or ledger appends acting as heartbeats) at interval ≈ unit cadence. Absence > 3× median unit time ⇒ presumed-dead protocol (HALT-07 §6).
- Time stamps are ISO-8601 local-with-offset; clocks need not be globally synchronized — ordering authority is `seq`, not `ts`.

---

## 4. Verification Levels

Chosen per node at Spec time (D6), recorded in the contract:

| Level | Name | Procedure | Applies to |
|---|---|---|---|
| V0 | Self-check | Producer runs own read-back; verifier = same agent | Tier-0 tasks, S0 scratch outputs |
| V1 | Mechanical | Deterministic script/checklist: existence, checksum, schema, spot content, acceptance criteria | default for Tier-1 |
| V2 | Independent audit | Different agent (fresh context, read-only) audits against contract acceptance criteria | critical nodes, cross-node integration, all Tier-2 |
| V3 | External/human | User or outside system confirms | gates (D23), S3 effects, subjective-quality deliverables |

### 4b. Verifier Independence Levels

`executor ≠ verifier` is only the floor. "Different agent" can still fail identically: same stale SOP, same corrupted source, same model bias, same poisoned evidence. Independence is therefore a graded property; a Spec or audit requirement names the minimum level:

| Level | Independence axis | Requirement |
|---|---|---|
| **I1 Context** | Fresh context; no shared in-flight reasoning with producer | mandatory floor for all V2 (this is what "different agent" meant) |
| **I2 Process** | Different execution path / method from producer | SHOULD for correctness-critical nodes |
| **I3 Model** | Different underlying model/provider | SHOULD where common-mode model bias is plausible (judgment-heavy outputs) |
| **I4 Evidence** | Verifier acquires its evidence directly from the environment, not via producer-generated summaries | MUST whenever the claim under test is "the environment is in state X" |
| **I5 Authority** | Verifier answers to a different authority than the producer | MUST for Tier-2 and wherever incentives could align |

**Rule VR-0.** A verification claim MUST record which I-levels it satisfied. An audit that cannot state its independence profile did not happen as an audit.

**Rule VR-1.** The Spec names its level. Upgrading level at verify-time is allowed; downgrading is a Decision Record requiring authority (usually user).
**Rule VR-2.** Independent audit (V2) MUST run with write authority removed (INV-10) and MUST record integrity status `clean/suspect/violation` alongside completion status (LHH auditor pattern).
**Rule VR-3 (open-ended deliverables).** Where acceptance is inherently judgment-based (prose quality, theoretical soundness, strategy, art), the Spec MUST additionally name: (a) the judging authority (which role, filled by whom); (b) the rubric or exemplar anchors the judge applies; (c) a bounded number of revise rounds before escalation becomes mandatory; (d) the default ruling if the judge goes unreachable. V3 then operates as a journaled gated loop: draft → judged → revise* → accept | escalate — with the revise count capped by (c).

---

## 5. FSM-T — Task Instance Lifecycle

| State | Meaning |
|---|---|
| `INIT` | Workspace created; four artifacts initialized |
| `DECOMPOSING` | Building/extending the Task Graph; writing node Specs |
| `EXECUTING` | Driving the frontier: contract → run → verify loop |
| `RECOVERING` | Post-interruption reconstruction pass (HALT-05); entered automatically whenever resuming |
| `SUSPENDED` | Deliberate pause; workspace consistent; resume = enter RECOVERING |
| `FINAL_AUDIT` | All nodes terminal-positive; whole-task verification walk |
| `ARCHIVED` | Deliverables handed over; memory store updated; workspace sealed (read-only recommendation) |

Transitions:

```
INIT --[graph scaffold written]--> DECOMPOSING
DECOMPOSING --[frontier non-empty]--> EXECUTING
EXECUTING --[interruption detected]--> RECOVERING        (T-INT, automatic)
EXECUTING --[clean pause ordered]--> SUSPENDED           (only at commit boundary)
SUSPENDED --[resume ordered]--> RECOVERING
RECOVERING --[consistency restored, frontier exists]--> EXECUTING
EXECUTING --[no READY nodes & none pending]--> FINAL_AUDIT
EXECUTING --[decomposition gap found]--> DECOMPOSING     (extend graph; normal, repeatable)
FINAL_AUDIT --[defects found]--> DECOMPOSING             (repair nodes appended)
FINAL_AUDIT --[pass]--> ARCHIVED
```

**Rules:**

- **Rule FST-1.** Every entry into `EXECUTING` from elsewhere passes through `RECOVERING` first — even after a clean pause. Recovery is not an anomaly handler; it is the standard door (AX-1 pessimism).
- **Rule FST-2.** `DECOMPOSING` is re-enterable at any time: discovering missed work mid-task is normal (do not pretend plans were complete; log an Amendment).
- **Rule FST-3.** `ARCHIVED` requires: final audit pass, memory-store write-back done (HALT-10 §5), hand-off note written, checkpoint marked `terminal`.
- **Rule FST-4 (nested instances).** A child SOP Instance runs its own FSM-T inside one parent node's `RUNNING→VERIFYING` span. Parent-visible child states are exactly: `running / done / blocked(ask) / failed(quarantined)` (see HALT-06 §4–5).

---

## 6. Frontier Computation (work selection)

The **Frontier** (D17) is recomputed — never incrementally assumed — whenever selecting work, i.e., at every `EXECUTING` iteration start and after every recovery.

```
FUNCTION frontier(G):
  input : task graph G (node records: deps, states, specs, priorities)
          journal-backed state map σ (from last rebuild / live commits)
          open_gates set, budget b
  output: ordered runnable list R

  R ← [ v ∈ G.nodes :
          σ[v] = READY                                   # deps DONE per journal
        ∧ spec_complete(v) ∧ ¬superseded(v)              # spec present, not quarantined-away
        ∧ ¬blocked_by_open_gate(v)                       # no unanswered Approval Gate upstream
        ∧ b > 0 ]

  order R by:
    1. priority(v) descending                            # set at Spec time
    2. else longest remaining critical path first        # keeps options open
    3. else cheapest first                               # flush frontier under parallelism limits
  return R
```

Properties (normative):

- **Determinism given inputs:** two coordinators holding the same (σ, gates, b) compute the same ordered R. Ordering ties break on `(priority, critical_path_len, unit_cost_estimate, node_id)` — total order, no coin flips.
- **Journal-backed inputs only:** σ comes from committed transitions (rank 3), never from reports.
- **Recompute-not-update:** after any amendment, gate change, or recovery, R is recomputed from scratch; there is no incremental "frontier patch" that could drift from truth.

Selection among frontier nodes beyond the ordering above (e.g., affinity to a warm executor) is a Reference Policy decision, journaled when it deviates from the default order.

**Rule FR-1.** Work MAY NOT be started from any source other than a computed Frontier (no "while I'm at it" side-quests; they become nodes or don't happen).
**Rule FR-2.** After any Steering Input that changes goals, the Frontier MUST be recomputed before the next dispatch (correction propagation, HALT-09 §2).

---

## 7. Retry Policy Matrix

Failure classification happens at N04/N07 time, recorded as `failure_class`:

| Class | Signature | Retry? | Resume partial output? | Cap (Reference Policy, overridable via `policy_params`) |
|---|---|---|---|---|
| Transient-environment | quota wall, network flap, model outage (AX-5 period variable!) | Yes, after environment health re-check | Yes (skip-by-evidence) | until env window ends, then escalate to user |
| Transient-agent | worker died mid-node, stall/timeout | Yes, fresh contract; consider method switch per strike count | Yes | `retry_budget` default 3 strikes |
| Permanent-spec | acceptance criteria unsatisfiable, contradiction found | No | n/a | → QUARANTINED + replan (N12) or ask user |
| Permanent-resource | missing tool/permission/cost cap | No | n/a | → BLOCKED with wake condition, ask route |

**Rule RT-1.** Before any retry of transient classes, run the environment health probe appropriate to the class (one cheap probe call / disk check). Never retry blind into a dead window (empirical: repeated dispatch into quota walls produced zero yield).
**Rule RT-2.** Strike counting is per-node, per-method. Changing method resets method-specific counters but the node total persists (visible to escalation logic).
**Rule RT-3 (failure detection is inference, not fact).** A heartbeat timeout or exit-signature match yields **SUSPECTED_DEAD**, never "dead" as a recorded fact: the journal records the *observation* (no heartbeat for T) and the *policy conclusion* (`presumed_dead=true under policy P`). Consequence handling differs by what follows:
  - If the suspected worker later produces output in its own scope, outputs still verify normally (skip-by-evidence protects them); duplicate-output risk is absorbed by deterministic merge keys + registry first-writer-wins.
  - Escalating to RETRYABLE requires the observation evidence, not just the label.
  - Where a runtime supports fencing (dispatch-time lease/epoch token that workers echo), a stale writer's commits after its lease expired MUST be quarantined rather than merged. Fencing is RECOMMENDED at Tier ≥1 when coordinator death is plausible; without it, SUSPECTED_DEAD handling above is mandatory.

## 7b. Resume Policy (per-node skip semantics)

INV-5 is conditioned on how a node's output relates to truth:

```yaml
resume_policy: one of
  skip_if_checksum      # deterministic S0/S2 work: verified existence ⇒ skip
                        # (extraction, conversion, compilation, fetch)
  reverify_if_amended   # generative work: skip only if produced under current
                        # spec version AND no amendment touches it; else re-verify
                        # before reuse (default for analysis/writing nodes)
  never_skip            # S3-adjacent actions and subjective drafts: every attempt
                        # re-runs unless an explicit Decision Record says otherwise
```

The Spec names the policy (default `reverify_if_amended`). This closes the gap between "output exists" (existence) and "output is still valid under current intent" (validity) — AX-2 makes them differ for generative work even without any goal change.

---

## 8. Suspension Semantics

A clean pause (`EXECUTING → SUSPENDED`) is legal ONLY at a commit boundary: no dangling tx_ids, no in-flight contracts. If urgent, prefer killing the process abruptly (AX-4 path) over "wait a second" — recovery handles both, but the abrupt path is honest about what it is. `SUSPENDED` writes one NOTE event with a handoff summary (what would you tell a replacement engineer) — this is the human-readable courtesy copy; the machine truth remains journal+checkpoint.

---

## 9. Worked Micro-Example (normative flavor)

100-paper extraction node `N-extract`, batch type:

```
N-extract: PENDING→READY (deps: corpus staged)
READY→RUNNING (contract: extract 100 abstracts → artifacts/n-extract/, ledger.jsonl)
  units u001..u100 processed via commit rule; ledger lines ok:u001..u030
INTERRUPTION (process killed after u030)
... later ... RECOVERING:
  scan ledger: ok up to u030; spot-read u030 artifact ✓
  → resume contract issued: "units u031..u100; skip any unit whose line status=ok"
RUNNING again ... u100 ok
RUNNING→VERIFYING (claim)
VERIFYING: V1 script: 100 lines ok, 100 files exist, checksums match, schema valid → PASS
VERIFYING→DONE (evidence refs)
downstream N-synthesis flips PENDING→READY (FR computation picks it up)
```

At no point did any step depend on conversation memory; the interruption between u030/u031 cost nothing.

---

## 10. Goal Evolution (changing what is wanted, legally)

Long tasks outrun their original goals. HALT treats goal change as a governed event, not a drift:

- **Authority.** Only the Sponsor may redefine `goal_statement` / top-level acceptance (08). Agents surface the *need* for redefinition; they do not self-authorize it. The standing route: Decision Record + steering channel + explicit Sponsor ruling.
- **GE-1 Re-scoping event.** An approved goal change is journaled as a GOAL_AMENDED event carrying: old vs new statement, rationale, and a **blast-radius walk** — which node Specs are affected (amend via TG-1), which DONE nodes remain valid, which need re-verification under new criteria, which are quarantined-as-superseded.
- **GE-2 Survivors keep credit.** Nodes whose outputs satisfy both old and new goals stay DONE (no punitive redo); only genuinely invalidated work is quarantined. This preserves budget and morale alike — and follows directly from INV-4/INV-5.
- **GE-3 Bounded evolution.** Each goal amendment increments an evolution counter in the checkpoint. Frequent amendments (>N per window) trigger escalation: either the decomposition is structurally wrong or the sponsor's intent is unstable — both need a conversation, not more replanning.
- **GE-4 Detection duty.** The coordinator SHOULD watch for goal-debt signals during FINAL_AUDIT and frontier stalls: acceptance criteria repeatedly unmeetable, chronic N12 replans on the same subtree, gates asking questions the Spec should have answered. These are surfaced as re-scoping proposals rather than silently absorbed.

What the external review called a "goal evolution layer" is thus not a separate subsystem: it is the composition of authority routing (08), amendment machinery (TG-1, ST-1..S4), survivor classification (this section), and bounded counters — already distributed through the protocol where each concern belongs.

---

*End of HALT-02. Next: HALT-03 defines the uniform SOP interface that any conforming module implements.*


---

## Note (v1.0.2)

Seq ordering for all transitions is governed by journal Rule J-4 (append-time derivation `1+max(seq)`); the FSM assumes a collision-free sequence — guaranteed by the runtime, checked by conformance A11.
