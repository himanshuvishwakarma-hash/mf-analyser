from pathlib import Path

from app.services.sources import amfi_ter_scraper

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "amfi_ter_page.html"


def test_find_latest_xlsx_url_picks_most_recent_filename():
    html = FIXTURE.read_text(encoding="utf-8")
    url = amfi_ter_scraper.find_latest_xlsx_url(html, base="https://www.amfiindia.com")
    assert url == "https://www.amfiindia.com/sites/default/files/research/TER-2026-05.xlsx"


def test_find_latest_xlsx_url_returns_none_when_no_match():
    url = amfi_ter_scraper.find_latest_xlsx_url("<html><body>no links</body></html>", base="x")
    assert url is None
