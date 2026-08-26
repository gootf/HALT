# HALT Glossary

One concept, one definition. All HALT documents use these senses only. (Normative source: HALT-01 §3.)

| Term | ID | Definition (short form) |
|---|---|---|
| Agent | D1 | Any entity executing task steps via Actions: LLM process, human, or group in a role. |
| Task Instance | D2 | One bounded undertaking under one root SOP invocation; id `task_id`; lives in one Workspace. |
| Workspace (W) | D3 | Durable directory tree holding ALL persistent artifacts of a Task Instance. |
| Task Graph (G) | D4 | DAG `(V,E)` of Work Nodes; created at INIT; extend/annotate only. |
| Node | D5 | Minimal schedulable work unit: stable id, Spec, deps, State, attempts, artifacts. |
| Node Spec | D6 | Immutable contract defining "done" for a node; changes only via AMENDMENT event. |
| Action | D7 | One elementary step (tool call / file write / human op) inside a running node. |
| Side Effect | D8 | Change outside the agent's head; classes S0–S3. |
| Journal (J) | D9 | Append-only sequence of committed Events for a task. Immutable lines. |
| Event | D10 | `{seq, tx?, ts, actor, kind, payload, evidence[]}` record. |
| Checkpoint (K) | D11 | Cheap JSON pointer cache over FSM positions/frontier/counters; never source of truth. |
| Artifact | D12 | Produced file/content registered with path + checksum + status. |
| Evidence | D13 | Verifier-obtained observation (read-back, listing, checksum). Carries proof weight. |
| Claim | D14 | Verbal/written assertion without verification. Zero proof weight (AX-3). |
| SOP | D15 | Named, versioned automaton module spec conforming to HALT-03; data, not a process embodiment. |
| SOP Instance | D16 | Runtime occurrence of an SOP bound to a scope; owns graph slice/journal/checkpoint. |
| Frontier | D17 | Set of READY nodes (deps satisfied, gates clear, budget >0); sole legal work source. |
| Interruption | D18 | Unplanned termination at arbitrary point (AX-4). |
| Recovery | D19 | Fixed procedure returning the instance to consistency + legal next step (HALT-05). |
| Memory Store (M) | D20 | Durable cross-task knowledge base of addressed entries (HALT-10). |
| Decision Record | D21 | Journal EVENT capturing options/choice/rationale/authority. |
| Steering Input | D22 | Mid-flight instruction from authority; logged durably before action (HALT-09). |
| Approval Gate | D23 | Explicit wait-for-ruling guard on named transition(s); timeout ≠ consent. |
| Contract | D24 | Complete bounded input package for one executing episode: Spec + evidence pointers + budget + duties. |
| Execution truth | — | Facts about task execution (did an action happen; does an output exist) — what the truth hierarchy ranks. |
| Content truth | — | Intellectual validity of artifact contents (is the claim/theory/strategy correct) — ranked by verification levels V1–V3, never by file existence. |
| Goal evolution | GE | Governed re-scoping: Sponsor-ruling + blast-radius walk + survivor credit + bounded counters (HALT-02 §10). |

Operational shorthand:

| Shorthand | Meaning |
|---|---|
| Stable position | Highest journal prefix whose events all carry verified effects (HALT-01 §5). |
| Skip-by-evidence | Resuming units by checking existing verified outputs before redoing (INV-5). |
| Disk adjudicates | Existence disputes resolved by inspecting workspace, not reports (C-TRUTH). |
| Commit | Completion of write→verify→journal→point cycle (HALT-01 §5). |
| Quarantine | Preserving failed/suspect output as marked history instead of deletion (INV-4). |

Side-effect classes:

| Class | Meaning | Discipline |
|---|---|---|
| S0 | Local additive | Full commit rule |
| S1 | Local destructive | Backup/quarantine first, then act |
| S2 | External replayable | Execute freely; log result |
| S3 | External non-replayable | Gate/receipt mandatory |

Verification levels:

| Level | Meaning |
|---|---|
| V0 | Producer self-check |
| V1 | Mechanical script/checklist |
| V2 | Independent fresh-context audit (read-only) |
| V3 | External/human confirmation |

- **Registry** (`artifacts/registry.json`): artifact ledger mapping ids to (path, checksum). Path content is frozen by checksum (Rule AR-3); supersession uses new ids or versioned paths.

- **Seq derivation (Rule J-4)**: event sequence numbers are derived at append time as `1 + max(seq)` over the journal tail; cached counters across restarts are non-conformant.
