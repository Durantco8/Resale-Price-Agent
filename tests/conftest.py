"""Shared test fixtures — in-memory DB engine."""

import pytest
from sqlalchemy import create_engine

from resale_price_agent.db import metadata


@pytest.fixture
def engine():
    """In-memory SQLite engine with all tables created."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    metadata.create_all(eng)
    return eng
