# Owner Demand Catalog — everything an owner would run by Neyma inside the TMS

_The master dogfood script. Each line is something an owner would literally say in Slack — built or
not. We drive these angle by angle; every miss is backlog; status flips only when the live conversation
goes right. ✅ works live · 🔸 partial/rough · ⬜ missing._

## 1. Money in — AR / billing (the wedge)
- ✅ "bill load 102" / "invoice Great Lakes for load 105" — record-anchored, amount from the TMS
- ✅ digest: "N loads ready to bill [Approve all]" (batch live-prove pending fresh loads)
- ✅ "record a $184.50 payment on invoice 560003" (proven write)
- ✅ "credit invoice 560009 $50 — they short-paid" (write proven; verify-msg tuning)
- ✅ "who owes us money?" / "who owes us the most?" (terms-aware, honest on unreadable pages)
- ⬜ "ping Global Tranz on their oldest invoice" → drafted dunning email [Send][Edit]
- ⬜ "did anyone pay us today?" (payments-received read)
- ⬜ "send the invoice + POD packet to the customer" (invoice delivery w/ backup docs)
- ⬜ "what did we bill this month vs last?" (billing summary)

## 2. Money out — AP / carrier settlement (the margin guard)
- 🔸 "record the payable to Iron Horse for LD-5, $1,421" (lane built; needs broker TMS to prove)
- 🔸 carrier-invoice vs rate-con reconciliation (engine built + tested; NOT live on the inbox)
- ⬜ "did that carrier bill us right?" — on-demand reconcile of one carrier invoice
- ⬜ "reject this $150 tarp fee we never agreed to" → drafted rejection email [Send][Edit]
- ⬜ "what do we owe carriers this week?" (AP aging)
- ⬜ "hold payment on that carrier until the POD shows up"

## 3. The load lifecycle — dispatch ops
- 🔸 "create a load for Coyote: Dallas→Chicago, picks 7/8, delivers 7/10, $2,500" (multi-entity; safely
  escalates; happy path needs the composite address flow)
- 🔸 "mark load 105 delivered" / "update 88 to dispatched" (routed; live drive pending)
- 🔸 "log a check call on 105 — driver's 50 miles out" (routed; live drive pending)
- ⬜ "where are my loads right now?" exists as status counts; per-load "what's the story on 105?"
  (status + stops + docs + billing state in one answer)
- ⬜ "copy last week's Acme load for tomorrow" (clone-load — how owners actually create loads)

## 4. Paperwork — the documents an owner drowns in
- 🔸 "attach the POD to load 105" (lane + FileSafe mapped; needs a real file source to prove)
- ✅ POD-gate: never bill without delivery proof (list + detail-page check)
- ⬜ "file this rate con against load 88" (email attachment → TMS filing — needs the live inbox)
- ⬜ "do we have signed BOLs for everything delivered this week?" (document audit read)
- ⬜ "send me the paperwork for load 102" (fetch the packet out of the TMS)
- ⬜ "make me a carrier packet for a new carrier" (W9/insurance/authority collection)

## 5. Exceptions & the radar (never let anything fall through)
- 🔸 delivered-but-unbilled surfaces via the digest; missing-POD surfaces as exceptions
- ⬜ "anything about to bite us?" — one radar: unbilled aging, PODs missing, invoices past terms,
  duplicate carrier invoices, insurance expiring
- ⬜ "why hasn't load 88 been billed yet?" (explain a stuck record)
- ⬜ short-pay detection on payments ("they paid $4,300 on a $4,500 invoice — flag it")

## 6. Ask-me-anything / control (the chief of staff)
- ✅ "what's happening?" (pocket brief) · "status" (health) · "what have you done today?" (audit)
- ✅ "pause tms writes" / "resume" (brake) · graduate/supervise (autonomy caps)
- ✅ challenges in an op thread get an answer about THAT op ("why did you do that?")
- 🔸 "how did we do this week?" (ROI exists; owner-grade weekly digest pending)
- ⬜ "remind me Friday to call TQL about the claim" (memos/follow-ups)
- ⬜ proactive 4PM daily digest (scheduled, not just cycle-driven)

## The loop (unchanged)
Owner (either of us) says it in Slack → judge the reply like a boss judges an employee → miss = backlog
here → fix → re-drive the same sentence → flip the status. The 🧪 *Claude-as-owner* cards in the channel
are my sessions; call out anything that reads wrong.
