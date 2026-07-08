"""Owner-onboarding readiness gate for the live Slack-controlled teammate.

This is the operator-facing preflight before Rasheed (or a design partner) starts using Neyma from
Slack. It intentionally checks the same seams that matter in production: credentials, delivery config,
workspace/DB wiring, Slack owner/channel allowlist, browser session readiness, and optional signed
callback command reachability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import urlparse

from .channels import load_delivery_config, verify_delivery_config
from .teammate_health import read_pilot_readiness


ProbeFn = Callable[[str, bytes, str, str, str], tuple[int, str]]


@dataclass
class OnboardingCheck:
    name: str
    ok: bool
    detail: str


@dataclass
class OwnerOnboardingReadiness:
    ready: bool
    checks: list[OnboardingCheck] = field(default_factory=list)
    dry_run: bool = False


def evaluate_owner_onboarding(
    *,
    workspace: str | Path,
    client_config: str | Path,
    env: Mapping[str, str],
    allowed_slack_users: tuple[str, ...] = (),
    allowed_slack_channel: str | None = None,
    require_running: bool = False,
    cdp_url: str | None = None,
    operation_url_filter: str | None = None,
    callback_url: str | None = None,
    require_public_ingress: bool = False,
    probe: ProbeFn | None = None,
) -> OwnerOnboardingReadiness:
    checks: list[OnboardingCheck] = []
    ws = Path(workspace)
    db_path = ws / "workflow.sqlite3"

    config = load_delivery_config(client_config)
    if config is None:
        checks.append(OnboardingCheck("delivery_config", False, f"no delivery block found in {client_config}"))
        return OwnerOnboardingReadiness(False, checks)

    checks.extend(_credential_checks(client_config=client_config, env=env))
    for channel_check in verify_delivery_config(config, env=env):
        missing = f" missing env: {', '.join(channel_check.missing_secrets)}" if channel_check.missing_secrets else ""
        issues = f" issues: {'; '.join(channel_check.issues)}" if channel_check.issues else ""
        checks.append(
            OnboardingCheck(
                f"channel:{channel_check.channel.value}",
                channel_check.ok,
                f"{'enabled' if channel_check.enabled else 'disabled'}{missing}{issues}".strip(),
            )
        )

    slack = config.slack
    if slack is None or not slack.enabled:
        checks.append(OnboardingCheck("slack_ui", False, "Slack delivery is not enabled; owner UI is not available."))
    else:
        checks.append(
            OnboardingCheck(
                "slack_channel",
                bool(allowed_slack_channel and (slack.default_channel_id == allowed_slack_channel or allowed_slack_channel in slack.routing.values())),
                f"allowed channel {allowed_slack_channel or '<missing>'} must match configured Slack routing/default.",
            )
        )
        checks.append(
            OnboardingCheck(
                "slack_owner_allowlist",
                bool(allowed_slack_users),
                f"{len(allowed_slack_users)} allowed owner user(s) configured.",
            )
        )

    if operation_url_filter:
        checks.append(OnboardingCheck("tms_url_filter", True, f"TMS browser pinned to {operation_url_filter!r}."))
    else:
        checks.append(OnboardingCheck("tms_url_filter", False, "missing operation URL filter; browser agent is not pinned to a TMS domain."))

    if require_running:
        readiness = read_pilot_readiness(
            ws,
            db_path=db_path,
            cdp_url=cdp_url if operation_url_filter else None,
            url_filter=operation_url_filter,
        )
        checks.append(
            OnboardingCheck(
                "runtime_readiness",
                readiness.healthy,
                f"{readiness.status}: " + " | ".join(check.detail for check in readiness.checks),
            )
        )
    else:
        checks.append(
            OnboardingCheck(
                "runtime_readiness",
                True,
                "not required for dry preflight; run with --require-running after run_teammate is started.",
            )
        )

    if callback_url and probe:
        checks.append(_public_ingress_check(callback_url, require_public=require_public_ingress))
        if slack is None:
            checks.append(OnboardingCheck("slack_callback_probe", False, "Slack config missing."))
        else:
            secret = env.get(slack.signing_secret_env)
            if not secret:
                checks.append(OnboardingCheck("slack_callback_probe", False, f"missing {slack.signing_secret_env}."))
            elif not allowed_slack_users or not allowed_slack_channel:
                checks.append(OnboardingCheck("slack_callback_probe", False, "missing allowed Slack user/channel."))
            else:
                status, reply = probe("status", secret.encode(), callback_url, allowed_slack_users[0], allowed_slack_channel)
                checks.append(
                    OnboardingCheck(
                        "slack_callback_probe",
                        status == 200 and "Pilot readiness" in reply,
                        f"[{status}] {reply.splitlines()[0] if reply else '<empty reply>'}",
                    )
                )

    return OwnerOnboardingReadiness(all(check.ok for check in checks), checks, dry_run=not require_running)


def render_owner_onboarding(readiness: OwnerOnboardingReadiness) -> str:
    if readiness.dry_run:
        head = f"Owner onboarding dry preflight: {'READY' if readiness.ready else 'NOT READY'}"
        if readiness.ready:
            head += " (live use still requires --require-running)"
    else:
        head = f"Owner onboarding readiness: {'READY' if readiness.ready else 'NOT READY'}"
    lines = [head]
    for check in readiness.checks:
        lines.append(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.detail}")
    return "\n".join(lines)


def _public_ingress_check(callback_url: str, *, require_public: bool) -> OnboardingCheck:
    if not require_public:
        return OnboardingCheck("slack_ingress_url", True, f"callback probe target: {callback_url}")
    parsed = urlparse(callback_url)
    host = (parsed.hostname or "").lower()
    ok = parsed.scheme == "https" and host not in ("localhost", "127.0.0.1", "::1")
    return OnboardingCheck(
        "slack_ingress_url",
        ok,
        (
            f"public Slack callback URL configured: {callback_url}"
            if ok else
            f"owner-ready Slack ingress must be public HTTPS, not {callback_url!r}"
        ),
    )


def _credential_checks(*, client_config: str | Path, env: Mapping[str, str]) -> list[OnboardingCheck]:
    problems: list[str] = []
    if not (env.get("NEYMA_IMAP_USERNAME") or env.get("NEYMA_SMTP_USERNAME")):
        problems.append("IMAP username missing (set NEYMA_IMAP_USERNAME).")
    if not (env.get("NEYMA_IMAP_PASSWORD") or env.get("NEYMA_SMTP_PASSWORD")):
        problems.append("IMAP app password missing (set NEYMA_IMAP_PASSWORD).")
    if not env.get("OPENAI_API_KEY"):
        problems.append("OPENAI_API_KEY missing.")
    config = load_delivery_config(client_config)
    if config is None:
        problems.append(f"no delivery config found at {client_config}.")
    else:
        if not env.get(config.action_token_secret_env):
            problems.append(f"action-token secret missing (set {config.action_token_secret_env}).")
        if config.slack is not None:
            if config.slack.signing_secret_env and not env.get(config.slack.signing_secret_env):
                problems.append(f"Slack signing secret missing (set {config.slack.signing_secret_env}).")
            if config.slack.bot_token_env and not env.get(config.slack.bot_token_env):
                problems.append(f"Slack bot token missing (set {config.slack.bot_token_env}).")
    if not problems:
        return [OnboardingCheck("runtime_credentials", True, "required mail/OpenAI/action/Slack secrets are present.")]
    return [OnboardingCheck("runtime_credentials", False, " | ".join(problems))]
