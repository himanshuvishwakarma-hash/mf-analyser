"""Tests for app.services.sources.amfi_master."""
from pathlib import Path

from app.services.sources import amfi_master

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "navall_sample.txt"


def test_parse_navall_returns_list_of_dicts():
    text = FIXTURE.read_text(encoding="utf-8")
    rows = amfi_master.parse_navall(text)
    assert len(rows) >= 1
    assert {"scheme_code", "scheme_name", "amc", "category"} <= set(rows[0].keys())


def test_parse_navall_extracts_amc_from_section_header():
    text = FIXTURE.read_text(encoding="utf-8")
    rows = amfi_master.parse_navall(text)
    assert all(r["amc"] for r in rows)


def test_parse_navall_extracts_category_from_section_header():
    text = FIXTURE.read_text(encoding="utf-8")
    rows = amfi_master.parse_navall(text)
    assert all(r["category"] for r in rows)
    assert any(r["category"] == "Equity" for r in rows)


def test_parse_navall_detects_direct_plan_in_name():
    text = FIXTURE.read_text(encoding="utf-8")
    rows = amfi_master.parse_navall(text)
    direct = [r for r in rows if "Direct" in r["scheme_name"]]
    assert direct
    assert all(r["plan_type"] == "Direct" for r in direct)


def test_parse_navall_skips_empty_rows():
    text = "\n\n;;;\n\n"
    rows = amfi_master.parse_navall(text)
    assert rows == []
