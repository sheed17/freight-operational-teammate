# Publication and security review

A review of what a stranger would be able to read if this repository were public, performed on
2026-10-08 against commit `8ee5bf6`. **No secret value is reproduced in this document.** Nothing
was deleted, untracked, rewritten or pushed as part of the review, and repository visibility was
not changed; every item below is a recommendation for the owner.

## Correction, 2026-10-08 (closeout pass)

The review below was written without access to GitHub and assumed the repository was private.
It is not: `sheed17/freight-operational-teammate` is **already public**, with `main` as the
default branch. That changes how three items read.

- **Items 6, 8 and 9 are already published.** `.playwright-mcp/`, `configs/tms/` and
  `eval/tests/test_truckingoffice_write.py` are on `origin/main` today. Pushing this branch
  exposes nothing new. Item 8 is still the owner's call, but it is a clean-up of something
  public, not a gate on publishing.
- **Item 3 is live.** `claude.yml` and `claude-code-review.yml` run on the public repository and
  the `CLAUDE_CODE_OAUTH_TOKEN` secret is set. Disable them if they are not wanted.
- **Item 1 is the only thing between a visitor and this showcase.** `origin/main` is 215 commits
  behind this branch and is an ancestor of it, so it can be fast-forwarded without a rewrite.
  CI was green on this branch at `c4376b9`; the five newer commits are unpushed.

No secret was found in either check. The findings below stand otherwise.

## Summary

**No live credential was found** in the tracked files or in the history reachable from any branch.
The repository is not yet ready to be made public as-is. The showcase is on an unpushed,
non-default branch; there is no licence; one configuration file records a write to a real TMS
account together with a real company's name (item 8), which only the owner can clear; and there
are several hygiene items — personal identifiers, tracked browser logs, AI workflows that would be
exposed to outside users — that should be decided deliberately first.

## What was checked, and how

| Check | Method | Population |
|---|---|---|
| Credential patterns in tracked files | Regular expressions for provider key shapes (OpenAI, Anthropic, Slack, AWS, GitHub, Google), private-key headers and Slack webhook URLs | 879 tracked files |
| Credential patterns in history | The same patterns over `git log --all -p`, output reduced to a masked prefix and a length | every commit reachable from any ref, including local `refs/preserve/*` |
| Secret-bearing files ever committed | `git log --all --diff-filter=A` for `.env*`, `*.pem`, `*.key`, `*credentials*`, `*secret*`, `*token*` | all refs |
| Machine-specific paths | Search for absolute home-directory paths | tracked files |
| Personal data | Email addresses grouped by domain; phone-number shapes; personal-mail domains | tracked files |
| Customer or operational data | Client configuration files, sample data, tracked browser snapshots and images inspected by hand | `configs/`, `data/`, `.playwright-mcp/`, root images |
| Demo artifacts | The new demo script and its captured output checked for paths, money values and identifiers | `docs/portfolio/demo/` |

**Not checked:** the contents of the local, untracked `.env` (deliberately not read); the values in
the tracked `.env.example` (the pattern scan covered it and found nothing, but it was not read by
eye); GitHub-side settings such as repository secrets, visibility, branch protection and Actions
permissions (GitHub was not reachable from the review environment); and binary files beyond the
two root images and the sample PDF's existence.

## Findings

### Clear

- **Tracked files: no credential.** Two pattern hits, both deliberate test fixtures: a short
  placeholder Slack token in `eval/tests/test_first_design_partner.py`, and a string in
  `eval/tests/test_p9_inference_gateway.py` named `KEY_SHAPED` and commented as not a real key,
  which a test uses to prove keys are never logged.
- **`.env` was never committed** on any ref. Only `.env.example` appears in history.
- **Configuration references secrets by environment-variable name only.**
- **Freight fixtures are synthetic.** Email domains are almost all reserved test domains
  (`.test`, `.example`) or placeholders, and no phone numbers were found. The sample invoice PDF is
  produced by `scripts/generate_sample_invoice.py`; the root screenshots and the tracked browser
  snapshots show the invented "Neyma Test Freight LLC". The exceptions are items 8 and 9 below.
- **The demo and its captured output** contain no absolute paths, no money values and no real
  identifiers.

### Decide before publishing

| # | Item | Where | Why it matters | Suggested action |
|---|---|---|---|---|
| 1 | **The showcase is on an unpushed, non-default branch.** | `p5/u5-1-g2-spec-correction` is 4 commits (plus this one) ahead of `origin`; the local `main`, which matches `origin/main`, is 214 commits behind it | A visitor lands on the default branch and sees none of this | `main` is an ancestor of this branch, so it can be fast-forwarded with no merge commit and no rewrite. Or change the default branch. Either is the owner's call. |
| 2 | **No licence file.** | repository root | Public without a licence means all rights reserved. That may be what you want for a portfolio; it should be a choice. | Add a licence, or a one-line note in the README that the code is shared for review only. |
| 3 | **AI workflows would be reachable by outside users.** | `.github/workflows/claude.yml`, `claude-code-review.yml` | They run on issues, comments and pull requests and use a repository secret. On a public repository anyone can open an issue or a pull request. | Before going public, confirm who can trigger them, or disable them. |
| 4 | **Personal email address.** | The git author identity on every commit; also quoted in two historical reports under `docs/implementation/` | Becomes public with the history | Acceptable to most people. If not, switch to GitHub's no-reply address for future commits — existing commits cannot change without rewriting history, which this review does not recommend. |
| 5 | **Local username and directory layout.** | Absolute home-directory paths in six historical review reports and one tracked browser snapshot | Low sensitivity; reveals the machine account name and the existence of a sibling repository | Leave as historical evidence, or redact in a normal follow-up commit. |
| 6 | **Tracked browser-automation logs.** | `.playwright-mcp/` — 7 files, although the directory is in `.gitignore` | Synthetic mock-TMS pages plus console output from visiting a public TMS vendor's website. Noise, and one file carries item 5's path. | `git rm -r --cached .playwright-mcp` in a follow-up commit. |
| 7 | **First name in configuration.** | `configs/clients/*.yaml` operator fields; `docs/FIRST_DESIGN_PARTNER_RASHEED.md` | These read as internal dogfood configurations (the company is "Neyma Test Freight LLC"), but the words "first design partner" could be mistaken for a customer | Fine to keep. Confirm the README's "no customer deployment" wording matches what actually happened. |
| 8 | **A recorded write to a real TMS account.** | `configs/tms/truckingoffice_screen_map.json` (environment labelled `live_design_partner_account`) and `eval/tests/test_truckingoffice_write.py` | The file records that the earlier runtime created one invoice in a TruckingOffice account on 2026-06-27, and includes the amount, a customer record id from that account and a **real brokerage's name** used as the customer. `configs/tms/transporters_io_screen_map.json` similarly names a trial tenant URL. | **Only the owner knows whose account that was.** If it was a personal trial account, consider removing the record id and the real company name. If it belonged to anyone else, do not publish it without their agreement. The README says only that the earlier runtime made "one write to such an account"; correct that wording if it is wrong. |
| 9 | **Third-party products and names.** | `configs/tms/` holds screen maps describing three commercial TMS products' interfaces; `docs/product/freight-discovery.md` names vendors as market research | No private data. Screen maps of vendors' interfaces, gathered by browser automation, may sit awkwardly with those vendors' terms of use. | Review `configs/tms/` and decide whether it belongs in a public repository. |
| 10 | **Stale package description.** | `pyproject.toml` `description` | Describes the project as an invoice-reconciliation engine, which the repository's own guide calls stale | Update it when you next touch packaging. Left alone here to keep this change documentation-only. |
| 11 | **Status authority does not record the pause.** | `docs/implementation/CURRENT.md` | It says the current phase is in progress. The README says development is paused. | Add a dated line to `CURRENT.md` yourself; it is the status authority and was deliberately not edited by this portfolio pass. |
| 12 | **Duplicate image.** | `packet-page-ld560003.png` and `packet-page-ld560003-clean.png` are byte-identical | Clutter at the repository root | Remove one in a follow-up commit. The README references the first. |

### Do not push

- **`refs/preserve/*` — 90 local refs.** These are full snapshots of the working tree taken
  during the phased program, including files that were ignored at the time. Some of them carry an
  older browser console log containing a **third-party website's public Google Maps browser key**
  in a URL. It is not your credential, it is not on any branch, and none of these refs is among
  the remote-tracking refs this clone knows about — but there is no reason to publish it.
  **A normal `git push origin <branch>` does not send these refs. `git push --mirror` or a push of
  `refs/*` would.** Never use those against a public remote.
- **Local branches under `archive/`, `backup/`, `preserve/`, `recovery/` and the rehearsal
  branches** are internal process history. Some are already on `origin`. Decide which belong in a
  public repository before changing visibility; deleting remote branches is reversible only while
  you still hold them locally.

### Commands that should not be presented as examples

The README and the portfolio documents recommend only offline commands on synthetic data. The
repository also contains, from the earlier runtime, scripts that are able to reach real systems
when credentials are configured — for example `scripts/drive_real_tms.py`,
`scripts/enter_tms_payable.py`, `scripts/run_gmail_to_slack_loop.py`, `scripts/pull_imap_mailbox.py`
and `scripts/submit_signed_action.py` — and historical documents under `docs/` that describe
running them (`LIVE_WRITE_PROOF.md`, `CLIENT_1_RUNBOOK.md`, `PRODUCTION_PILOT.md`). Those documents
are already bannered as historical. They need no change, but none of them should be quoted in a
demo, and a reader should not run those scripts against an account they care about. Which entry
points are effect-capable is adjudicated in
[`EFFECT-PATH-INVENTORY.yaml`](../implementation/EFFECT-PATH-INVENTORY.yaml).

## Checklist before changing visibility

- [ ] Re-run the 20 socket-binding tests outside a sandbox and confirm a full green suite
      ([`METRICS.md`](METRICS.md), section 1)
- [ ] Push this branch and confirm CI is green on GitHub
- [ ] Make this work the default branch view (item 1)
- [ ] Decide on a licence (item 2)
- [ ] Confirm or disable the AI workflows (item 3)
- [ ] Untrack `.playwright-mcp/` (item 6)
- [ ] Resolve the recorded TMS write and the real company name (item 8)
- [ ] Decide which archive and process branches stay on the public remote
- [ ] Read `.env.example` once by eye
- [ ] Record the pause in `CURRENT.md` (item 11)
- [ ] Set the GitHub description, topics and social preview; the pinned-repository card shows the
      description, not the README
- [ ] Have one person who has never seen the project try the quick start from a fresh clone
