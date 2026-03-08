"""
Test stubs for Phase 35: Navigation + Breadcrumb.

All tests are marked xfail(strict=True) — they represent behaviors that will
be implemented in Plan 02. Once implementation lands, xfail markers are removed
and tests turn green.

Requirements covered:
  NAV-01: All calculator pages display a breadcrumb "Home > [Calculator Name]"
          at the top of the page; breadcrumb must NOT appear on the home screen.
  NAV-02: Clicking "Home" in the breadcrumb navigates the user back to /.

Test inventory:
  1. test_cloud_page_has_breadcrumb_home_link    — GET /cloud has href="/" and "Home" (NAV-02)
  2. test_nios_page_has_breadcrumb_home_link     — GET /nios has href="/" and "Home" (NAV-02)
  3. test_ad_page_has_breadcrumb_home_link       — GET /ad has href="/" and "Home" (NAV-02)
  4. test_cloud_page_breadcrumb_shows_calculator_name — GET /cloud has "Cloud Calculator" (NAV-01)
  5. test_nios_page_has_breadcrumb               — GET /nios has "NIOS Calculator" (NAV-01)
  6. test_ad_page_has_breadcrumb                 — GET /ad has "AD Calculator" (NAV-01)
  7. test_home_has_no_breadcrumb                 — GET / does NOT have "breadcrumb-nav" (NAV-01)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from cloud_usage.dashboard.app import create_app

app = create_app()


@pytest.mark.xfail(strict=True, reason="Phase 35 Plan 02 not yet implemented")
def test_cloud_page_has_breadcrumb_home_link() -> None:
    with TestClient(app) as client:
        response = client.get("/cloud")
    assert response.status_code == 200
    assert 'href="/"' in response.text
    assert "Home" in response.text


@pytest.mark.xfail(strict=True, reason="Phase 35 Plan 02 not yet implemented")
def test_nios_page_has_breadcrumb_home_link() -> None:
    with TestClient(app) as client:
        response = client.get("/nios")
    assert response.status_code == 200
    assert 'href="/"' in response.text
    assert "Home" in response.text


@pytest.mark.xfail(strict=True, reason="Phase 35 Plan 02 not yet implemented")
def test_ad_page_has_breadcrumb_home_link() -> None:
    with TestClient(app) as client:
        response = client.get("/ad")
    assert response.status_code == 200
    assert 'href="/"' in response.text
    assert "Home" in response.text


@pytest.mark.xfail(strict=True, reason="Phase 35 Plan 02 not yet implemented")
def test_cloud_page_breadcrumb_shows_calculator_name() -> None:
    with TestClient(app) as client:
        response = client.get("/cloud")
    assert response.status_code == 200
    assert "Cloud Calculator" in response.text


@pytest.mark.xfail(strict=True, reason="Phase 35 Plan 02 not yet implemented")
def test_nios_page_has_breadcrumb() -> None:
    with TestClient(app) as client:
        response = client.get("/nios")
    assert response.status_code == 200
    assert "NIOS Calculator" in response.text


@pytest.mark.xfail(strict=True, reason="Phase 35 Plan 02 not yet implemented")
def test_ad_page_has_breadcrumb() -> None:
    with TestClient(app) as client:
        response = client.get("/ad")
    assert response.status_code == 200
    assert "AD Calculator" in response.text


@pytest.mark.xfail(strict=False, reason="Phase 35 Plan 02 not yet implemented — home page already has no breadcrumb-nav, so this passes now and after implementation")
def test_home_has_no_breadcrumb() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "breadcrumb-nav" not in response.text
