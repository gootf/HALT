# HALT Roles, Authority & Team Composition

- **Spec ID:** HALT-08
- **Version:** 1.0.0 (2026-08-25)
- **Depends on:** HALT-01 (INV-6, INV-10), HALT-02 (V-levels), HALT-03 (interface)

Roles are hats, not beings: any Agent (LLM process, human, group) can wear a role. A role is defined entirely by its authority partition and its duties. This makes the protocol work for pure-agent, mixed, and human teams alike.

---

## 1. Canonical Roles

| Role | Owns / may write | Must NOT | Core duty |
|---|---|---|---|
| **Sponsor** (human/authority) | Task charter; final rulings; S3 approvals | Operate internals directly | Decide what is wanted; adjudicate escalations |
| **Coordinator** (a.k.a. manager) | Task Graph structure; contracts; checkpoint; journal appends; slot accounting | Execute domain work it delegated (except pulled-back slots); trust claims | Maintain truth; drive frontier; contain failures |
| **Executor** (worker) | Its scoped outputs + ledger (+tmp) | Touch other scopes; write shared state artifacts; self-declare DONE anywhere that matters | Do bounded contract; report honestly; die loudly |
| **Verifier/Auditor** | Audit reports (read-only elsewhere) | Modify anything under audit | Produce Evidence-grade verdicts: completion + integrity |
| **Recorder** (optional, Tier-2) | Journal maintenance, mirrors, compaction snapshots | Interpret state | Keep the flight recorder trustworthy |
| **Gatekeeper** (the human behind Approval Gates) | Rulings at gates | — | Answer persisted questions in time |

Notes:

- One entity MAY hold multiple roles across different scopes (coordinator of task A = executor inside task B), but **within one verification act the verifier MUST NOT be the producer** (INV-6). Role separation is per-object, not per-person.
- The LongHorizon-Harness MEA triad maps 1:1: Manager→Coordinator, Executor→Executor, Auditor→Verifier. Their empirical gains (51.8→80.7 WeaveBench etc.) are the evidence base for mandatory separation.

---

## 2. Authority Grants

Every Contract carries explicit `authority_grants` (paths/network/spend):

```
write:artifacts/n-042/*        # scope
network:read                   # capability class
spend:max_usd=5.0              # budget
speak: none                    # external messaging forbidden unless granted
```

**Rule AU-1 (least privilege default).** Unlisted = denied.
**Rule AU-2 (grant escalation path).** Needing more authority ⇒ block(ask) through channels; never "borrow" another scope's write power (observed failure mode: workers "fixing" shared index files and corrupting them).
**Rule AU-3 (verifier hard-mode).** Verifier grants are read-only over protected artifacts by construction; if the harness cannot enforce read-only technically, the verifier's contract forbids writes and its session is audited for mutations (integrity check covers the auditor too).

---

## 3. Team Composition Patterns

- **Solo (coordinator-executes-all).** Legal for small tasks; V1/V2 separation still enforced by fresh-context self-audit where feasible; Tier ≥1 tasks with S3 effects still need an external gatekeeper.
- **Coordinator + workers (fan-out).** Default production pattern (HALT-07).
- **Full MEA team.** Coordinator ≠ executors ≠ auditor as separate entities; required for Tier-2 critical nodes.
- **Human-in-the-loop team.** Humans hold executor or gatekeeper roles under identical journal/accounting rules (HALT-07 §8).

Handoff between entities wearing the same role = normal recovery procedure (R1–R7); nothing special, because nothing depends on persons.

---

## 4. Accountability & Audit Trail

- Every event carries `actor` (role:id). Every artifact carries producing invocation. Every ruling carries authority source (sponsor decision ref / rule citation).
- An audit walk (FINAL_AUDIT, Tier-2 periodic) reconstructs: who did what on whose evidence under what grant — INV-9 satisfied when this walk succeeds without interviewing anyone.

---

## 5. Anti-Patterns

- AP-R1 Executor grades own homework at V≥2 ("I verified it myself" from the producing context).
- AP-R2 Coordinator doing heavy domain execution while parallel workers idle (context poisoning of the coordination station; pull-back mode exists precisely to bound this).
- AP-R3 Invisible admins: changes appearing without actor attribution (any tooling used MUST route through journaled actions).
- AP-R4 Sponsor micromanaging via side channel (bypasses journal; steering must enter through durable inbox, HALT-09).

---

*End of HALT-08. Next: HALT-09 — human gates & steering inputs.*
