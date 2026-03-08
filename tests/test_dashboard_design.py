"""
Wave 0 test scaffold for Phase 33 Design Foundation (DESIGN-01).

All tests are marked xfail — they define the acceptance criteria that
waves 1 and 2 will satisfy. Tests fail against the current codebase
(PicoCSS still present, design-system.css not yet created).
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


@pytest.mark.xfail(strict=False, reason="Wave 0 scaffold — will pass after implementation")
def test_base_html_no_pico_reference() -> None:
    """GET / response body must NOT contain 'pico.min.css'."""
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "pico.min.css" not in response.text


@pytest.mark.xfail(strict=False, reason="Wave 0 scaffold — will pass after implementation")
def test_base_html_references_design_system() -> None:
    """GET / response body must contain 'design-system.css'."""
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "design-system.css" in response.text


@pytest.mark.xfail(strict=False, reason="Wave 0 scaffold — will pass after implementation")
def test_base_html_no_data_theme() -> None:
    """GET / response body must NOT contain 'data-theme'."""
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "data-theme" not in response.text


@pytest.mark.xfail(strict=False, reason="Wave 0 scaffold — will pass after implementation")
def test_design_system_contains_ib_navy() -> None:
    """GET /static/design-system.css returns 200 and body contains '--ib-navy'."""
    with TestClient(app) as client:
        response = client.get("/static/design-system.css")
        assert response.status_code == 200
        assert "--ib-navy" in response.text


@pytest.mark.xfail(strict=False, reason="Wave 0 scaffold — will pass after implementation")
def test_design_system_contains_ib_accent_green() -> None:
    """GET /static/design-system.css returns 200 and body contains '--ib-accent-green'."""
    with TestClient(app) as client:
        response = client.get("/static/design-system.css")
        assert response.status_code == 200
        assert "--ib-accent-green" in response.text


@pytest.mark.xfail(strict=False, reason="Wave 0 scaffold — will pass after implementation")
def test_design_system_contains_page_bg() -> None:
    """GET /static/design-system.css returns 200 and body contains '--page-bg'."""
    with TestClient(app) as client:
        response = client.get("/static/design-system.css")
        assert response.status_code == 200
        assert "--page-bg" in response.text


@pytest.mark.xfail(strict=False, reason="Wave 0 scaffold — will pass after implementation")
def test_app_css_no_root_variables() -> None:
    """GET /static/app.css returns 200 and body must NOT contain ':root' block with variables."""
    with TestClient(app) as client:
        response = client.get("/static/app.css")
        assert response.status_code == 200
        assert ":root" not in response.text


@pytest.mark.xfail(strict=False, reason="Wave 0 scaffold — will pass after implementation")
def test_no_pico_variable_references() -> None:
    """GET / response body must NOT contain '--pico-' variable references."""
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "--pico-" not in response.text


@pytest.mark.xfail(strict=False, reason="Wave 0 scaffold — will pass after implementation")
def test_inter_fonts_served() -> None:
    """GET /static/inter-variable.woff2 returns 200."""
    with TestClient(app) as client:
        response = client.get("/static/inter-variable.woff2")
        assert response.status_code == 200
