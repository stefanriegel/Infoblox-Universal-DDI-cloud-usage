"""
Wave 0 xfail scaffold for Phase 36 Calculator Visual Redesign (DESIGN-03, DESIGN-04, DESIGN-05).

All 11 stubs are marked xfail(strict=True) — they define the acceptance criteria that
Plans 02 and 03 will satisfy. Tests fail against the current codebase because the accent
system and card layout changes are not yet implemented.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from starlette.testclient import TestClient

from cloud_usage.dashboard.app import create_app

app = create_app()


# ---------------------------------------------------------------------------
# DESIGN-03: Accent color body class and CSS rules (6 tests)
# ---------------------------------------------------------------------------


def test_cloud_body_has_calc_cloud_class() -> None:
    """GET /cloud response body must contain class=\"calc-cloud\" on the body element."""
    with TestClient(app) as client:
        response = client.get("/cloud")
    assert response.status_code == 200
    assert 'class="calc-cloud"' in response.text


def test_nios_body_has_calc_nios_class() -> None:
    """GET /nios response body must contain class=\"calc-nios\" on the body element."""
    with TestClient(app) as client:
        response = client.get("/nios")
    assert response.status_code == 200
    assert 'class="calc-nios"' in response.text


def test_ad_body_has_calc_ad_class() -> None:
    """GET /ad response body must contain class=\"calc-ad\" on the body element."""
    with TestClient(app) as client:
        response = client.get("/ad")
    assert response.status_code == 200
    assert 'class="calc-ad"' in response.text


def test_app_css_has_calc_cloud_accent() -> None:
    """GET /static/app.css must define .calc-cloud rule with #0066CC accent colour."""
    with TestClient(app) as client:
        response = client.get("/static/app.css")
    assert response.status_code == 200
    assert ".calc-cloud" in response.text
    assert "#0066CC" in response.text


def test_app_css_has_calc_nios_accent() -> None:
    """GET /static/app.css must define .calc-nios rule with #00C389 accent colour."""
    with TestClient(app) as client:
        response = client.get("/static/app.css")
    assert response.status_code == 200
    assert ".calc-nios" in response.text
    assert "#00C389" in response.text


def test_app_css_has_calc_ad_accent() -> None:
    """GET /static/app.css must define .calc-ad rule with #8B5CF6 accent colour."""
    with TestClient(app) as client:
        response = client.get("/static/app.css")
    assert response.status_code == 200
    assert ".calc-ad" in response.text
    assert "#8B5CF6" in response.text


# ---------------------------------------------------------------------------
# DESIGN-04: Wizard step checkmark and calc-accent usage (2 tests)
# ---------------------------------------------------------------------------


def test_app_css_wizard_completed_uses_calc_accent() -> None:
    """GET /static/app.css must use var(--calc-accent) CSS custom property."""
    with TestClient(app) as client:
        response = client.get("/static/app.css")
    assert response.status_code == 200
    assert "var(--calc-accent)" in response.text


def test_app_css_wizard_completed_has_checkmark() -> None:
    r"""GET /static/app.css must contain the Unicode checkmark escape \2713."""
    with TestClient(app) as client:
        response = client.get("/static/app.css")
    assert response.status_code == 200
    assert "\\2713" in response.text


# ---------------------------------------------------------------------------
# DESIGN-05: Card layout on results/complete screens (3 tests)
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="Phase 36 Plan 03 not yet implemented")
def test_nios_complete_has_completion_card() -> None:
    """partials/nios/complete.html must contain the 'completion-card' CSS class."""
    tmpl = (
        Path(__file__).parent.parent
        / "src/cloud_usage/dashboard/templates/partials/nios/complete.html"
    )
    content = tmpl.read_text()
    assert "completion-card" in content


@pytest.mark.xfail(strict=True, reason="Phase 36 Plan 03 not yet implemented")
def test_ad_complete_has_completion_card() -> None:
    """partials/ad/complete.html must contain the 'completion-card' CSS class."""
    tmpl = (
        Path(__file__).parent.parent
        / "src/cloud_usage/dashboard/templates/partials/ad/complete.html"
    )
    content = tmpl.read_text()
    assert "completion-card" in content


@pytest.mark.xfail(strict=True, reason="Phase 36 Plan 03 not yet implemented")
def test_summary_has_token_summary_header() -> None:
    """pages/summary.html must contain the text 'Token Summary'."""
    tmpl = (
        Path(__file__).parent.parent
        / "src/cloud_usage/dashboard/templates/pages/summary.html"
    )
    content = tmpl.read_text()
    assert "Token Summary" in content
