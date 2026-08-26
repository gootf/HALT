# HALT Human Gates & Steering Inputs

- **Spec ID:** HALT-09
- **Version:** 1.0.0 (2026-08-25)
- **Depends on:** HALT-02 (BLOCKED/gates, ask route), HALT-05 §5, HALT-08 (gatekeeper role)

Humans participate in two modes: as **authorities** (gates, steering, adjudication) and as **workers** (HALT-07 §8). This document fixes the mechanics so human participation survives interruption like everything else.

---

## 1. Design Principles

- H1 **Durable-or-nothing.** Any human instruction that matters MUST land in a durable channel before being acted on. Verbal/chat instructions not yet journaled do not exist (AX-1; the motivating incident: correction sent, session died mid-turn, context lost).
- H2 **Questions persist before waiting.** A question asked into void-with-no-record is asked twice after every crash.
- H3 **Blocking is scoped.** Gates stop the minimal dependent set (QA-1), never the world.
- H4 **Authority is explicit.** Which human may rule on what is recorded; agents do not guess who sponsors them.

---

## 2. Steering Inputs (mid-flight corrections)

### 2.1 Ingestion Protocol (receiver side)

```
S1 LOG     append STEERING_LOGGED event {source, verbatim content, ts,
           received_via}; write verbatim copy into steering/inbox.md entry
S2 CLASSIFY
   - clarification (no behavior change)      → NOTE; answer inline
   - amendment (changes specs/constraints)   → AMENDMENT events + TG-1 edits
   - halt/pivot (stop current line)          → recall procedure (HALT-07 §7)
   - question about state                    → answer from evidence; log Q&A pair
S3 PROPAGATE recompute frontier (FR-2); amend affected open contracts;
   record which in-flight slots were recalled/bounded
S4 ACKNOWLEDGE durable ack visible to sponsor ("logged as J-…, applied to …")
```

### 2.2 Rules

- **Rule ST-1.** Classification disputes resolve toward the stronger reading (amendment > clarification) and are surfaced for confirmation rather than silently weakened.
- **Rule ST-2.** Steering received during coordinator death-window (never ingested): sponsor repeats to successor session; successor logs with provenance tag `re-stated`. The system then treats it as native steering. Post-mortem notes the channel gap.
- **Rule ST-3.** Steering that contradicts a committed DONE node does NOT rewrite history: it creates corrective nodes (INV-4); the old path stays auditable.

---

## 3. Approval Gates

### 3.1 Anatomy

A Gate = named guard attached to specific transition(s) (node-level or SOP-card level), with:

```yaml
gate_id: G-publish-synthesis
blocks: [N-077 VERIFYING→DONE]      # or SOP phase edge
question: "Publish synthesis v2? Diff vs v1: deliverables/diff-v1-v2.md"
options: [approve, revise(spec deltas), reject(reason)]
timeout: {after: 48h, fallback: remain-blocked}   # NEVER auto-approve by timeout
```

### 3.2 Mechanics

1. Reaching the guarded transition ⇒ node BLOCKED(gate); question written to steering inbox + journal (H2).
2. Gatekeeper answers via durable reply; answer logged (DECISION event, actor=gatekeeper).
3. Wake condition satisfied ⇒ N09 transition with evidence ref.
4. Timeout never fabricates consent: default stays blocked (S3-adjacent caution).

**Rule GA-1.** All S3 actions REQUIRE a gate OR pre-granted standing authority recorded at INIT (e.g., "may send emails to listed addresses"). Standing authorities are revocable by steering at any time.
**Rule GA-2.** Gate questions come packaged: context + options + consequences + artifact links. Gatekeepers must not need archaeology to rule.

---

## 3b. The Interrupted-Steering Scenario (normative walkthrough)

Requirement origin: user-specified scenario — parallel dispatch running; human sends correction; session dies instantly; new session must cope.

```
t0 coordinator dispatched W1..W8 (contracts logged)
t1 human: "stop using approach Y; require Z flag on all future items"
   → arrives but coordinator dies BEFORE ingestion (worst case)
t2 new session starts → RECOVERING:
   R2 finds no STEERING_LOGGED entry (it never landed)
   → recovery CANNOT invent it; resume summary flags:
     "last known sponsor contact: <none since J-…>; pending inbox empty"
t3 sponsor restates directive to successor (ST-2)
   → successor runs S1–S4: logs, amends specs of N-043+ (not yet run),
     recalls in-flight W1..W8 contracts per HALT-07 §7:
       landed units judged per-unit (valid ones survive skip-by-evidence),
       approach-Y units quarantined with amendment refs,
       re-dispatch with amended contracts
t4 journal now shows: steering → amendments → recalls → re-dispatch chain,
   fully auditable
```

Best case (steering DID land before death): t2 recovery itself executes S3–S4 without bothering the sponsor. Both paths converge; neither loses the directive nor corrupts history.

---

## 4. Adjudication Format (escalations)

Escalation bundle (what the human receives):

```json
{"escalation_id":"E-004","kind":"method_switch_requested",
 "slot":"N-042/w3","attempts":3,"failure_classes":["transient-agent"x3],
 "disk_facts":"units u001-u014 ok; u015 absent; last heartbeat 41min",
 "options":[{"id":"pullback","desc":"coordinator executes remainder"},
            {"id":"switch_model","desc":"re-dispatch pinned non-reasoner"},
            {"id":"decompose","desc":"split u015+ into smaller windows"}],
 "default_if_no_answer":"suspend_with_handoff"}
```

**Rule AD-1.** Escalations always name a safe default-if-unanswered (usually suspend/handoff, never risky action).
**Rule AD-2.** Three-strike escalations carry the three attempts' signatures so the human decides with data (FSN-3 obligation).

---

## 5. Human-as-Worker Adjustments

Contracts for humans use the same schema; budgets become time estimates; heartbeats become status pings at natural milestones; disk adjudication applies unchanged (their file outputs verify identically). Politeness adjustments (no 90-second death checks) are harness courtesies, not protocol differences.

---

*End of HALT-09. Next: HALT-10 — cross-task memory store.*
