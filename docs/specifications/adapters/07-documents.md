# Adapter Family 07 — Document Storage Adapter *(A11)*

*Registry + defaults apply. Reuses the foundational Evidence primitive — no new store semantics for domain truth.*

**Purpose.** Store/retrieve document artifacts as **content-addressed Evidence**; attach to external systems as gated effects. **Not.** ### **NOT the owner of document CLASSIFICATION or BINDING (those are native Claims); document content is IMMUTABLE.** **Direction.** bidirectional. **Vendors.** S3-class store, TMS doc area (via A4/A15) — same contract.

| Op | class | verification | notes |
|---|---|---|---|
| A11-1 `store_artifact` | `OBSERVATION_ONLY` (retain Evidence) | n/a | ### **content-addressed (`sha256`) — identical bytes DEDUPLICATE; a revised doc is a NEW digest ⇒ a new version (never an edit)** |
| A11-2 `retrieve_artifact` | `INFORMATIONAL_READ` | n/a | by digest |
| A11-3 `file_document` (attach to a load) | ### **`CONSEQUENTIAL_EFFECT`** (`FILE_DOCUMENT`) | ### **READBACK_VERIFIABLE** | CK occ = **content digest**; ### **the runtime supplies the file (document fence); readback confirms the attachment on the target record** |

**Correction.** ### **content immutable; a wrong binding is corrected via `ClaimCorrected` (propagates, retains history — CD-6/CD-7); a re-bind never silently moves the doc.** **Malicious/illegible.** ### **a password-protected/corrupt/handwritten-unreadable file ⇒ `ILLEGIBLE` Document ⇒ Exception (H29); malicious content ⇒ `PromptInjectionSignal`, bounded to a proposal (H11).** **PII.** ### **document bodies (PODs, invoices) are PII — encrypted at rest in the Evidence store; NEVER placed in event payloads (only digests/refs travel).** **Acceptance.** `test_a11_content_addressed_dedup`; `test_a11_file_is_document_fence`; `test_a11_illegible_raises_exception` (H29); `test_a11_rebind_via_correction_retains_history`. **Adversarial.** H11, H29. **Open.** OCR/extraction confidence for handwritten docs — NEEDS VALIDATION (fail-closed to human).
