"""Shared pytest configuration and fixtures for the cloud usage test suite."""

import pytest


def pytest_configure(config):
    """Register custom pytest marks to suppress PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests requiring external data files "
        "(deselect with '-m \"not integration\"')",
    )
