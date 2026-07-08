# Session Runtime Migration — off localhost, no human-tended browser

_The design spec for evolving from "a Chrome I keep logged in on my laptop" to "a hydrated, ephemeral,
headless runtime any host can run" — without regressing the proven spine (668 tests). Design-first;
PRs below are the implementation order._

## Verdict on scope (right-sized, honestly)

| Spec piece | Call | Why |
|---|---|---|
| §1 Session capture + storage-state serialization | **BUILD NOW** | The single blocker to leaving localhost. |
| §2 Ephemeral hydrated runtime | **BUILD NOW — as spawn-per-run, not a pool** | Tenant-count = 1. The interface is pool-shaped so a pool is a later drop-in, not a rewrite. |
| §3 Expiry watchdog + Slack re-auth handshake | **FINISH** | Detection already exists (`browser_session_health.py`, `browser_failures.SESSION_EXPIRED`); only the pause + signed re-auth link is missing. |
| §4 `TMSProvider` API-first abstraction | **FORMALIZE LIGHTLY, LATER PR** | The `Actuator` protocol + `build_agent` factory is already this seam de facto. Formalize when the first real API adaptor exists, not before. |
| AWS KMS / Vault, multi-tenant DB, browser pool | **DESIGN-HONORED, DEFERRED** | The encryption contract below is KMS-ready (`kek_provider` + `key_id` fields), so swapping the local key backend for KMS is a config change, not a schema migration. Build it when partner #2–3 signs. |

**One deliberate deviation from the spec: stay pure-CDP — no Playwright/Puppeteer.** The entire proven
stack (actuator, settle, submit-detection, money-field reads) speaks raw CDP. Hydration needs only two
primitives we don't have yet (`Network.getAllCookies`, `Network.setCookie`) — a ~30-line addition to
`cdp_session.py` — plus launching `chrome --headless=new --remote-debugging-port` ourselves. A second
browser-automation framework adds a dependency surface and subtle behavioral drift for zero capability.

---

## 1. Encrypted session storage schema (the SessionVault)

One file per tenant×TMS (not in the workflow DB — different lifecycle, different sensitivity), e.g.
`workspace/sessions/<tenant>.<tms>.session.enc`, `chmod 600`, dir gitignored. Envelope-encrypted JSON:

```json
{
  "v": 1,
  "kek_provider": "local-file",        // -> "aws-kms" | "vault" later; contract unchanged
  "key_id": "neyma-session-kek-01",     // KMS key ARN / Vault path when swapped
  "nonce": "<b64 12B>",
  "ciphertext": "<b64 AES-256-GCM>",    // AAD = "tenant|tms" so a blob can't be replayed cross-tenant
  "tenant": "default",
  "tms": "truckingoffice",
  "status": "ACTIVE",                   // ACTIVE | NEEDS_REAUTH | EXPIRED
  "captured_at": "...", "last_validated_at": "...",
  "fingerprint": "<sha256 of plaintext>"  // change-detection without decryption
}
```

Plaintext payload (never at rest unencrypted): `{"cookies": [Network.getAllCookies output],
"origins": {"https://secure.truckingoffice.com": {"localStorage": {...}}}}`. v1 KEK backend: a random
256-bit key in `~/.neyma/session.key` (600) or macOS Keychain; `cryptography` (AESGCM) is the one new
dependency. **The model/agent never sees this payload** — hydration happens below the actuator, before
the agent's first observe.

Capture flow (`scripts/capture_tms_session.py`): launch a **headed** Chrome on the capture machine →
human does login/MFA/CAPTCHA (we never store credentials or bypass MFA) → poll
`read_browser_session_health` until it reports logged-in → snapshot cookies + localStorage via CDP →
encrypt → vault. Re-auth is the same script, triggered by the Slack handshake link (§3). On a remote
host, capture runs wherever the human is; the encrypted blob is what moves.

## 2. The exact injection hook

Today every live path constructs `CdpBrowserSession(cdp_url=...)` against the long-lived local Chrome
(5 live construction sites: `_build_agent`, `_build_receivables_reader`, `_build_load_amount_resolver`,
`_build_tms_brief_reader` in `run_action_callback_server.py`, plus `propose_ar_from_tms.py`). The hook
is a `SessionRuntime` provider that **yields a cdp_url** — nothing above it changes:

```python
class SessionRuntime(Protocol):
    def cdp_url(self) -> str: ...       # ensure a browser is up + AUTHENTICATED, return its endpoint
    def teardown(self) -> None: ...     # ephemeral mode: kill the instance; attached mode: no-op

class AttachedChromeRuntime:            # today's behavior — the default, zero regression
    # returns the configured http://localhost:9222

class EphemeralHydratedRuntime:         # the new mode (NEYMA_BROWSER_MODE=ephemeral)
    # 1. launch chrome --headless=new --remote-debugging-port=<free port> --user-data-dir=<mkdtemp>
    # 2. decrypt vault -> Network.setCookie for each cookie + localStorage per origin  (BEFORE any nav)
    # 3. navigate to the TMS home; browser_session_health must report logged-in, else -> NEEDS_REAUTH
    # 4. hand the cdp_url to the unchanged CdpBrowserSession/actuator/agent
    # 5. teardown() on completion OR failure/timeout — profile dir deleted, no residue
```

The agent loop, money fence, nav allowlist, browser-lock, and all 668 tests are untouched — hydration
sits entirely below the seam they already use. The browser-lock keeps working because within one
teammate the runtime is shared per-operation exactly as the tab is today.

## 3. Expiry → pause → Slack re-auth handshake

Already built: in-run `SESSION_EXPIRED` classification (corroborated by a password field), health-check
login detection, pilot-readiness NO_GO. To finish:

1. On either signal: mark the vault entry `NEEDS_REAUTH`; engage the existing writes brake
   (`OpsControl`) so the tenant's queue pauses (per-tenant queues arrive with multi-tenancy).
2. Post the Slack alert with a **signed, short-lived, single-use** re-auth link — reusing the existing
   `DeliverySigner` token machinery and callback routes (same properties as approval buttons):
   > 🔐 *TruckingOffice session expired — I've paused TMS work.* [Re-authenticate] (15-min link)
3. The link triggers the capture pipeline (§1); on a fresh `ACTIVE` blob, release the brake and resume.

## 4. `TMSProvider` (API-first) — the seam already exists

`OperatorAgent` drives an `Actuator` protocol injected via `build_agent`; lanes are transport-agnostic
goals. An API-backed provider = an alternate `build_agent`/executor for lanes whose TMS exposes an API,
chosen per tenant×lane in config, browser as the universal fallback. Formalize when the first real API
target exists (the TruckingOffice API check is on the board). No rewrite required — that's the point of
the lane model.

---

## The first 3 PRs (no regression to the 668)

**PR1 — SessionVault + capture (no live-path changes).** `cdp_session.py`: `get_all_cookies()` /
`set_cookies()` primitives. New `session_vault.py` (AESGCM envelope, local KEK backend, KMS-shaped
contract). New `scripts/capture_tms_session.py` (headed capture, health-gated snapshot).
_Tests: AEAD round-trip; tampered blob refuses; AAD binds tenant+tms; no plaintext at rest; capture
gates on logged-in health._ Risk: none — nothing existing imports it yet.

**PR2 — SessionRuntime seam + ephemeral hydrated mode (flag-gated).** `browser_runtime.py` with the two
runtimes; the 5 live construction sites take a runtime (default `AttachedChromeRuntime` — behavior
byte-identical); `NEYMA_BROWSER_MODE=ephemeral` opts in. _Tests: cookies injected BEFORE first
navigation; teardown on success/failure/timeout (no orphan chrome, profile dir gone); hydrated-but-
logged-out → NEEDS_REAUTH not a blind run; attached mode untouched (full suite green)._

**PR3 — Re-auth handshake.** SESSION_EXPIRED/NO_GO → vault `NEEDS_REAUTH` + brake + Slack alert with
signed TTL link → capture → resume. _Tests: detection→pause+alert payload; link TTL/single-use;
resume only on a fresh ACTIVE blob._

Then: **PR4** container packaging (one image: app + chrome, ephemeral mode default) · **PR5**
`TMSProvider` + TruckingOffice API check · **later** KMS backend + per-tenant queues + pool when
tenant-count demands it.

## Distance, honestly

- **"Personal assistant, always on," current architecture:** now — it needs a host that doesn't sleep
  (Mac mini / left-on machine) and nothing else; the keep-alive + self-heal already run it.
- **PR1–PR3 (no human-tended browser; runs on any headless VM; re-auth = a Slack tap):** ≈1.5–2.5
  weeks of build+prove at the current pace.
- **Container-per-tenant external deployments:** +1–2 weeks after that (PR4).
- **KMS/Vault + shared multi-tenant pool:** deliberately deferred; the contracts above make it a
  swap, not a migration.
