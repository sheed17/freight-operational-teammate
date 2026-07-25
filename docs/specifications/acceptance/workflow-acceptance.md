# Workflow Acceptance — Master *(AC-WF-*, AC-FC-*)*

*Registry defaults apply. Levels: `WORKFLOW` / `END_TO_END`. Gates: **G5–G9**. Per-loop files: `W1..W11-acceptance.md`.*

## The universal loop oracle
> ### **A loop passes ONLY when the real business obligation is SATISFIED or EXPLICITLY DISPOSITIONED — proved by an authoritative external observation plus a durable closure event carrying a resolving `decision_ref`.**
> ### **A Pipeline Instance reaching `CLOSED` is NOT loop closure (loophole L-12). A Work Item transition is NOT downstream obligation creation (L-13).**

## Per-loop mandatory dimensions *(every W-file asserts all 18)*
canonical entry · complete happy path · **every** valid alternate path · **every** blocking Conflict · **every** Exception path · **every** `UNKNOWN_OUTCOME` path · **every** cancellation · **every** reopening · **every** correction · **every** compensation · **every** cross-loop handoff · **every** closure condition · **every** false-closure condition · owner loss · policy narrowing · brake engagement · degraded integration mode · out-of-band human execution · replay.

## THE SIXTEEN FALSE-CLOSURE NEGATIVES *(AC-FC-001..016 — ALL MERGE-GATING)*
> ### **Each proves closure is STRUCTURALLY REJECTED — not merely "not attempted". The oracle is: drive the loop to the false signal, then assert (a) the Work Item is NOT `CLOSED`, (b) no closure event exists, (c) the downstream obligation state is unchanged, and (d) an attempt to force closure raises an ILLEGAL TRANSITION.**

| ID | False signal | Structural rejection oracle |
|---|---|---|
| **AC-FC-001** | quote created ≠ accepted | W1 Work Item open; no `WorkItemClosed`; forcing ⇒ illegal |
| **AC-FC-002** | quote accepted ≠ covered | ### **W2 `COVER_LOAD` exists and is OPEN — W1 closing does not cover** |
| **AC-FC-003** | carrier assigned ≠ picked up | W4 `DISPATCH_READY` open; no pickup Observation |
| **AC-FC-004** | message sent ≠ received | RECEIPT ≠ delivery; ### **no "delivered" field written** |
| **AC-FC-005** | tracking delivered ≠ POD received | ### **`DELIVERED` claim + packet `INCOMPLETE` ⇒ W6 open, billing blocked** |
| **AC-FC-006** | POD received ≠ valid packet | an `ILLEGIBLE`/ambiguous POD ⇒ packet not `COMPLETE` |
| **AC-FC-007** | packet complete ≠ invoice released | W8 requires approval + checkpoint |
| **AC-FC-008** | invoice released ≠ delivered | issue ≠ send |
| **AC-FC-009** | invoice delivered ≠ paid | ### **`SENT` ≠ `PAID`; only a verified Payment Application closes AR** |
| **AC-FC-010** | payable entered ≠ approved | `RECORDED` requires prior `APPROVED`; a conflicting field blocks |
| **AC-FC-011** | payable approved ≠ paid | `APPROVED` ≠ `PAID` |
| **AC-FC-012** | payment initiated ≠ settled | initiation ⇒ pending; only a bank Observation settles |
| **AC-FC-013** | document uploaded ≠ valid | uploaded + unbound/illegible ⇒ not counted |
| **AC-FC-014** | ### **adapter success response ≠ verified real-world outcome** | ### **the simulator returns 200 but the readback finds nothing (healthy) ⇒ `VERIFIED_FAILURE`; returns 200 + blind readback ⇒ `UNKNOWN_OUTCOME` — a 200 alone NEVER verifies** |
| **AC-FC-015** | ### **Pipeline completion ≠ Work Item closure** | ### **drive a pipeline to `CLOSED` with the obligation unmet (billed-not-paid) ⇒ the Work Item stays OPEN** |
| **AC-FC-016** | ### **Work Item transition ≠ downstream obligation created** | ### **inject a crash between the source transition and the downstream Work Item insert ⇒ the source does NOT advance (atomic handoff); assert no responsibility gap** |

## Cross-loop handoff acceptance *(AC-WF-H01..H10)*
For each of the 10 registry handoffs: ### **the downstream Work Item exists in the SAME COMMIT as the source transition. The oracle: crash between them ⇒ NEITHER happened (atomicity), and the source cannot close. A duplicate handoff dedups on the source `event_id`. Replay recreates the projection with ZERO effects.**
