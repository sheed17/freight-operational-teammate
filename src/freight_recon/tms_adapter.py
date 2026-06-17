"""TMS adapter contracts and a bounded mock-TMS read adapter."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from .tool_permissions import ToolContext, evaluate_tool_permission, record_tool_permission_decision
from .workflow import WorkflowStore


LOAD_ID_RE = re.compile(r"^[A-Z]{2}-\d{6}$")


class TmsAdapterError(RuntimeError):
    """Raised when a TMS adapter cannot safely complete a bounded operation."""


class TmsChargeReadback(BaseModel):
    name: str
    rate_amount: str | None = None
    invoice_amount: str | None = None
    authorized: bool | None = None
    backup_document: str | None = None


class TmsDocumentReadback(BaseModel):
    doc_type: str
    label: str
    href: str


class TmsLoadReadback(BaseModel):
    source: str = "mock_tms_html"
    source_url: str
    load_id: str
    pro_number: str | None = None
    invoice_number: str
    carrier: str
    customer: str | None = None
    pickup_date: str | None = None
    delivery_date: str | None = None
    equipment: str | None = None
    commodity: str | None = None
    rate_total: str
    invoice_total: str
    payable_status: str
    workflow_state: str | None = None
    workflow_reason: str | None = None
    charges: list[TmsChargeReadback] = Field(default_factory=list)
    documents: list[TmsDocumentReadback] = Field(default_factory=list)


class TmsPayableReadback(BaseModel):
    source: str = "mock_tms_payables_html"
    source_url: str
    load_id: str
    invoice_number: str
    carrier: str
    expected_amount: str
    billed_amount: str
    payable_status: str


class BrowserPageReader(Protocol):
    """Minimal browser-page contract for TMS read adapters.

    A Playwright wrapper, browser-use tool wrapper, or test fake can implement this without
    letting workflow code depend directly on a browser package.
    """

    def goto(self, url: str) -> None:
        ...

    def text(self, selector: str) -> str:
        ...

    def attr(self, selector: str, name: str) -> str | None:
        ...

    def table_rows(self, selector: str) -> list[dict[str, Any]]:
        ...

    def links(self, selector: str) -> list[dict[str, str]]:
        ...


class BrowserMockTmsReadAdapter:
    """Read mock TMS through a bounded browser/page interface.

    This is the adapter shape that real Playwright/browser-use implementations should satisfy.
    It performs no writes and only navigates to allowlisted mock-TMS URLs.
    """

    def __init__(
        self,
        page: BrowserPageReader,
        *,
        base_url: str = "http://localhost:8000/tms",
        allowed_hosts: set[str] | None = None,
    ) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.allowed_hosts = allowed_hosts or {"localhost", "127.0.0.1"}
        self._validate_base_url()

    def read_load(self, load_id: str) -> TmsLoadReadback:
        self._validate_load_id(load_id)
        url = f"{self.base_url}/loads/{load_id}.html"
        self.page.goto(url)
        parsed_load_id = self.page.attr("main[data-load-id]", "data-load-id") or load_id
        if parsed_load_id != load_id:
            raise TmsAdapterError(f"load id mismatch in browser page: requested {load_id}, read {parsed_load_id}")

        fields = {
            "pro_number": self.page.text('[data-field="pro_number"]'),
            "invoice_number": self.page.text('[data-field="invoice_number"]'),
            "carrier": self.page.text('[data-field="carrier"]'),
            "customer": self.page.text('[data-field="customer"]'),
            "pickup_date": self.page.text('[data-field="pickup_date"]'),
            "delivery_date": self.page.text('[data-field="delivery_date"]'),
            "equipment": self.page.text('[data-field="equipment"]'),
            "commodity": self.page.text('[data-field="commodity"]'),
            "rate_total": self.page.text('[data-field="rate_total"]'),
            "invoice_total": self.page.text('[data-field="invoice_total"]'),
            "payable_status": self.page.text('[data-field="payable_status"]'),
            "workflow_state": self.page.text('[data-field="workflow_state"]'),
            "workflow_reason": self.page.text('[data-field="workflow_reason"]'),
        }
        required = ["invoice_number", "carrier", "rate_total", "invoice_total", "payable_status"]
        missing = [field for field in required if not fields.get(field)]
        if missing:
            raise TmsAdapterError(f"browser TMS page missing fields for {load_id}: {', '.join(missing)}")

        return TmsLoadReadback(
            source="mock_tms_browser",
            source_url=url,
            load_id=load_id,
            pro_number=_blank_to_none(fields["pro_number"]),
            invoice_number=fields["invoice_number"],
            carrier=fields["carrier"],
            customer=_blank_to_none(fields["customer"]),
            pickup_date=_blank_to_none(fields["pickup_date"]),
            delivery_date=_blank_to_none(fields["delivery_date"]),
            equipment=_blank_to_none(fields["equipment"]),
            commodity=_blank_to_none(fields["commodity"]),
            rate_total=_money_text(fields["rate_total"]),
            invoice_total=_money_text(fields["invoice_total"]),
            payable_status=fields["payable_status"],
            workflow_state=_blank_to_none(fields["workflow_state"]),
            workflow_reason=_blank_to_none(fields["workflow_reason"]),
            charges=[
                TmsChargeReadback(
                    name=row["name"],
                    rate_amount=_blank_to_none(_money_text(row.get("rate_amount", ""))),
                    invoice_amount=_blank_to_none(_money_text(row.get("invoice_amount", ""))),
                    authorized=_yes_no(row.get("authorized", "")),
                    backup_document=_blank_to_none(row.get("backup_document")),
                )
                for row in self.page.table_rows('table[aria-label="Charge lines"]')
            ],
            documents=[
                TmsDocumentReadback(
                    doc_type=link["doc_type"],
                    label=link["label"],
                    href=link["href"],
                )
                for link in self.page.links("#documents li[data-doc-type] a")
            ],
        )

    def read_payable(self, load_id: str) -> TmsPayableReadback:
        self._validate_load_id(load_id)
        url = f"{self.base_url}/payables.html"
        self.page.goto(url)
        rows = self.page.table_rows('table[data-tms-table="payables"]')
        row = next((item for item in rows if item.get("load_id") == load_id), None)
        if row is None:
            raise TmsAdapterError(f"load not found in browser payable queue: {load_id}")
        return TmsPayableReadback(
            source="mock_tms_browser_payables",
            source_url=url,
            load_id=load_id,
            invoice_number=row["invoice_number"],
            carrier=row["carrier"],
            expected_amount=_money_text(row["expected_amount"]),
            billed_amount=_money_text(row["billed_amount"]),
            payable_status=row["payable_status"],
        )

    def _validate_base_url(self) -> None:
        match = re.match(r"^https?://([^/:]+)(?::\d+)?(?:/|$)", self.base_url)
        if not match or match.group(1) not in self.allowed_hosts:
            raise TmsAdapterError(f"mock browser TMS base URL is not allowlisted: {self.base_url}")

    def _validate_load_id(self, load_id: str) -> None:
        if not LOAD_ID_RE.match(load_id):
            raise TmsAdapterError(f"invalid load id for browser mock TMS adapter: {load_id}")


class MockTmsReadAdapter:
    """Read-only adapter for the generated mock TMS HTML surface.

    This intentionally accepts only a local generated TMS root and load ids matching the synthetic
    corpus format. Later browser adapters should implement the same read contract while adding
    session, timeout, and selector instrumentation.
    """

    def __init__(
        self,
        root_dir: str | Path,
        *,
        base_url: str = "http://localhost:8000/tms",
        store: WorkflowStore | None = None,
        run_id: int | None = None,
        tool_context: ToolContext | None = None,
    ) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.base_url = base_url.rstrip("/")
        self.store = store
        self.run_id = run_id
        self.tool_context = tool_context
        if not self.root_dir.exists():
            raise TmsAdapterError(f"mock TMS root does not exist: {self.root_dir}")

    def read_load(self, load_id: str) -> TmsLoadReadback:
        self._audit_permission("read_tms_load")
        self._validate_load_id(load_id)
        path = self._safe_path("loads", f"{load_id}.html")
        if not path.exists():
            raise TmsAdapterError(f"mock TMS load page not found: {load_id}")

        parser = _LoadDetailParser()
        parser.feed(path.read_text(encoding="utf-8"))
        fields = parser.fields
        parsed_load_id = parser.load_id or load_id
        if parsed_load_id != load_id:
            raise TmsAdapterError(f"load id mismatch in TMS page: requested {load_id}, read {parsed_load_id}")

        required = ["invoice_number", "carrier", "rate_total", "invoice_total", "payable_status"]
        missing = [field for field in required if not fields.get(field)]
        if missing:
            raise TmsAdapterError(f"mock TMS load page missing fields for {load_id}: {', '.join(missing)}")

        readback = TmsLoadReadback(
            source_url=f"{self.base_url}/loads/{load_id}.html",
            load_id=load_id,
            pro_number=_blank_to_none(fields.get("pro_number")),
            invoice_number=fields["invoice_number"],
            carrier=fields["carrier"],
            customer=_blank_to_none(fields.get("customer")),
            pickup_date=_blank_to_none(fields.get("pickup_date")),
            delivery_date=_blank_to_none(fields.get("delivery_date")),
            equipment=_blank_to_none(fields.get("equipment")),
            commodity=_blank_to_none(fields.get("commodity")),
            rate_total=_money_text(fields["rate_total"]),
            invoice_total=_money_text(fields["invoice_total"]),
            payable_status=fields["payable_status"],
            workflow_state=_blank_to_none(fields.get("workflow_state")),
            workflow_reason=_blank_to_none(fields.get("workflow_reason")),
            charges=parser.charges,
            documents=parser.documents,
        )
        self._audit_readback("tms_load_read", readback.model_dump(mode="json"))
        return readback

    def read_payable(self, load_id: str) -> TmsPayableReadback:
        self._audit_permission("read_tms_payable")
        self._validate_load_id(load_id)
        path = self._safe_path("payables.html")
        if not path.exists():
            raise TmsAdapterError("mock TMS payables page not found")

        parser = _PayablesParser(load_id)
        parser.feed(path.read_text(encoding="utf-8"))
        if parser.row is None:
            raise TmsAdapterError(f"load not found in payable queue: {load_id}")

        cells = parser.row["cells"]
        if len(cells) < 8:
            raise TmsAdapterError(f"payable row has unexpected shape for {load_id}")
        readback = TmsPayableReadback(
            source_url=f"{self.base_url}/payables.html",
            load_id=load_id,
            invoice_number=cells[1],
            carrier=cells[3],
            expected_amount=_money_text(cells[4]),
            billed_amount=_money_text(cells[5]),
            payable_status=parser.row["payable_status"],
        )
        self._audit_readback("tms_payable_read", readback.model_dump(mode="json"))
        return readback

    def read_raw_record(self, load_id: str) -> dict[str, Any]:
        """Read generated JSON for test assertions and future readback comparison only."""
        self._validate_load_id(load_id)
        data_path = self._safe_path("data.json")
        records = json.loads(data_path.read_text(encoding="utf-8"))
        for record in records:
            if record.get("load_id") == load_id:
                return record
        raise TmsAdapterError(f"load not found in mock TMS data: {load_id}")

    def _validate_load_id(self, load_id: str) -> None:
        if not LOAD_ID_RE.match(load_id):
            raise TmsAdapterError(f"invalid load id for mock TMS adapter: {load_id}")

    def _safe_path(self, *parts: str) -> Path:
        path = (self.root_dir / Path(*parts)).resolve()
        if path != self.root_dir and self.root_dir not in path.parents:
            raise TmsAdapterError(f"blocked path outside mock TMS root: {path}")
        return path

    def _audit_permission(self, tool_name: str) -> None:
        if self.store is None or self.run_id is None or self.tool_context is None:
            return
        decision = evaluate_tool_permission(tool_name, self.tool_context)
        record_tool_permission_decision(self.store, self.run_id, decision=decision, context=self.tool_context)
        if not decision.allowed:
            raise TmsAdapterError(f"tool blocked: {tool_name}: {decision.reason}")

    def _audit_readback(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.store is None or self.run_id is None:
            return
        self.store.add_audit_event(
            self.run_id,
            event_type,
            actor=self.tool_context.actor if self.tool_context else "system",
            payload=payload,
        )


class _LoadDetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.load_id: str | None = None
        self.fields: dict[str, str] = {}
        self.charges: list[TmsChargeReadback] = []
        self.documents: list[TmsDocumentReadback] = []
        self._field: str | None = None
        self._field_chunks: list[str] = []
        self._charge_name: str | None = None
        self._charge_cells: list[str] = []
        self._cell_chunks: list[str] | None = None
        self._doc_type: str | None = None
        self._doc_href: str | None = None
        self._doc_chunks: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if tag == "main" and attr.get("data-load-id"):
            self.load_id = attr["data-load-id"]
        if attr.get("data-field"):
            self._field = attr["data-field"]
            self._field_chunks = []
        if tag == "tr" and attr.get("data-charge-name"):
            self._charge_name = attr["data-charge-name"]
            self._charge_cells = []
        if tag == "td" and self._charge_name is not None:
            self._cell_chunks = []
        if tag == "li" and attr.get("data-doc-type"):
            self._doc_type = attr["data-doc-type"]
            self._doc_href = None
            self._doc_chunks = []
        if tag == "a" and self._doc_type is not None:
            self._doc_href = attr.get("href", "")

    def handle_data(self, data: str) -> None:
        if self._field is not None:
            self._field_chunks.append(data)
        if self._cell_chunks is not None:
            self._cell_chunks.append(data)
        if self._doc_chunks is not None:
            self._doc_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._field is not None and tag in {"strong", "p"}:
            self.fields[self._field] = _normalize_text("".join(self._field_chunks))
            self._field = None
            self._field_chunks = []
        if tag == "td" and self._cell_chunks is not None:
            self._charge_cells.append(_normalize_text("".join(self._cell_chunks)))
            self._cell_chunks = None
        if tag == "tr" and self._charge_name is not None:
            self.charges.append(_charge_from_cells(self._charge_name, self._charge_cells))
            self._charge_name = None
            self._charge_cells = []
        if tag == "li" and self._doc_type is not None:
            self.documents.append(
                TmsDocumentReadback(
                    doc_type=self._doc_type,
                    label=_normalize_text("".join(self._doc_chunks or [])),
                    href=self._doc_href or "",
                )
            )
            self._doc_type = None
            self._doc_href = None
            self._doc_chunks = None


class _PayablesParser(HTMLParser):
    def __init__(self, target_load_id: str) -> None:
        super().__init__()
        self.target_load_id = target_load_id
        self.row: dict[str, Any] | None = None
        self._capturing_row: dict[str, Any] | None = None
        self._cell_chunks: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if tag == "tr" and attr.get("data-load-id") == self.target_load_id:
            self._capturing_row = {
                "load_id": attr["data-load-id"],
                "invoice_number": attr.get("data-invoice", ""),
                "payable_status": attr.get("data-payable-status", ""),
                "cells": [],
            }
        if tag == "td" and self._capturing_row is not None:
            self._cell_chunks = []

    def handle_data(self, data: str) -> None:
        if self._cell_chunks is not None:
            self._cell_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._cell_chunks is not None and self._capturing_row is not None:
            self._capturing_row["cells"].append(_normalize_text("".join(self._cell_chunks)))
            self._cell_chunks = None
        if tag == "tr" and self._capturing_row is not None:
            self.row = self._capturing_row
            self._capturing_row = None


def _charge_from_cells(name: str, cells: list[str]) -> TmsChargeReadback:
    padded = cells + [""] * (5 - len(cells))
    return TmsChargeReadback(
        name=name,
        rate_amount=_money_text(padded[1]) if padded[1] != "-" else None,
        invoice_amount=_money_text(padded[2]) if padded[2] != "-" else None,
        authorized=_yes_no(padded[3]),
        backup_document=_blank_to_none(padded[4]),
    )


def _normalize_text(value: str) -> str:
    return " ".join(value.replace("\u2014", "-").split())


def _money_text(value: str) -> str:
    return _normalize_text(value).replace("$", "").replace(",", "")


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _normalize_text(value)
    return normalized or None


def _yes_no(value: str) -> bool | None:
    normalized = _normalize_text(value).lower()
    if normalized == "yes":
        return True
    if normalized == "no":
        return False
    return None
