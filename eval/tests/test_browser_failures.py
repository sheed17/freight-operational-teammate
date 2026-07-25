"""Tests for the in-run browser failure taxonomy — high-confidence classification, no false trips."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.browser_failures import FailureClass, classify_page  # noqa: E402


def test_login_url_with_password_field_is_session_expired():
    obs = {"url": "https://tms.test/users/sign_in", "inputs": [{"type": "password"}], "body_text": ""}
    cls, reason = classify_page(obs)
    assert cls == FailureClass.SESSION_EXPIRED and "log in" in reason.lower()


def test_session_expiry_text_with_password_is_session_expired():
    obs = {"url": "https://tms.test/x", "inputs": [{"type": "password"}],
           "body_text": "Your session has expired. Please sign in to continue."}
    assert classify_page(obs)[0] == FailureClass.SESSION_EXPIRED


def test_a_sign_in_LINK_on_a_normal_page_does_not_false_trip():
    # a healthy page that merely has a "Sign in" link in a header must NOT be called session-expired
    obs = {"url": "https://tms.test/invoices", "inputs": [{"type": "text"}],
           "body_text": "Invoices Dashboard Sign in Help", "errors": []}
    assert classify_page(obs)[0] == FailureClass.NONE


def test_permission_text_is_permission_denied():
    obs = {"url": "https://tms.test/x", "body_text": "Access denied: you are not allowed to view this."}
    assert classify_page(obs)[0] == FailureClass.PERMISSION_DENIED


def test_error_banners_are_validation_error():
    obs = {"url": "https://tms.test/new", "errors": ["Amount can't be blank", "Customer is required"]}
    cls, reason = classify_page(obs)
    assert cls == FailureClass.VALIDATION_ERROR
    assert "blank" in reason


def test_healthy_page_is_none():
    obs = {"url": "https://tms.test/invoices", "inputs": [{"type": "text"}], "body_text": "Invoices", "errors": []}
    assert classify_page(obs)[0] == FailureClass.NONE
