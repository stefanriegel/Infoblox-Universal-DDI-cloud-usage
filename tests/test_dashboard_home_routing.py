"""
Test stubs for Phase 34: Home Screen and Routing.

All tests are marked xfail(strict=True) — they represent behaviors that will
be implemented in Plans 02 and 03. Once implementation lands, xfail markers
are removed and tests turn green.

Requirements covered:
  HOME-01: Home screen returns 200 with correct title
  HOME-02: Home screen contains three calculator cards with entry links
  ROUTE-01: /cloud, /nios, /ad routes return 200
  ROUTE-02: Root route renders home.html, not the old tab-dashboard
  DESIGN-02: calculator-card CSS class used on home screen
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from cloud_usage.dashboard.app import create_app

app = create_app()


@pytest.mark.xfail(strict=True, reason="Phase 34: home screen not yet implemented")
def test_home_returns_200_with_title() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Infoblox UDDI Token Calculator" in response.text


@pytest.mark.xfail(strict=True, reason="Phase 34: home screen not yet implemented")
def test_home_contains_three_calculator_cards() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.text.count('class="calculator-card"') == 3


@pytest.mark.xfail(strict=True, reason="Phase 34: home screen not yet implemented")
def test_home_cards_contain_entry_links() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert 'href="/cloud"' in response.text
    assert 'href="/nios"' in response.text
    assert 'href="/ad"' in response.text


@pytest.mark.xfail(strict=True, reason="Phase 34: /cloud route not yet implemented")
def test_cloud_route_returns_200() -> None:
    with TestClient(app) as client:
        response = client.get("/cloud")
    assert response.status_code == 200


@pytest.mark.xfail(strict=True, reason="Phase 34: /nios route not yet implemented")
def test_nios_route_returns_200() -> None:
    with TestClient(app) as client:
        response = client.get("/nios")
    assert response.status_code == 200


@pytest.mark.xfail(strict=True, reason="Phase 34: /ad route not yet implemented")
def test_ad_route_returns_200() -> None:
    with TestClient(app) as client:
        response = client.get("/ad")
    assert response.status_code == 200


@pytest.mark.xfail(strict=True, reason="Phase 34: home screen not yet implemented")
def test_root_is_home_not_tab_dashboard() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert 'hx-get="/tab/progress"' not in response.text


@pytest.mark.xfail(strict=True, reason="Phase 34: home screen not yet implemented")
def test_home_uses_calculator_card_class() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert 'class="calculator-card"' in response.text
