"""Tests for the item management CLI."""

import pytest
from sqlalchemy import create_engine

from manage_items import main
from resale_price_agent.db import (
    get_all_tracked_items,
    get_tracked_item,
    metadata,
)


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)
    metadata.create_all(eng)
    return eng


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

class TestAdd:
    def test_add_item(self, engine, capsys):
        main(["add", "Jordan 4 Military Black size 10"], engine=engine)
        out = capsys.readouterr().out

        assert "Added item #1" in out
        assert "Jordan 4 Military Black size 10" in out
        items = get_all_tracked_items(engine)
        assert len(items) == 1
        assert items[0]["search_query"] == "Jordan 4 Military Black size 10"

    def test_add_existing_shows_already_tracking(self, engine, capsys):
        main(["add", "Jordan 4"], engine=engine)
        capsys.readouterr()

        main(["add", "Jordan 4"], engine=engine)
        out = capsys.readouterr().out

        assert "Already tracking" in out

    def test_add_multiple(self, engine):
        main(["add", "Item A"], engine=engine)
        main(["add", "Item B"], engine=engine)

        items = get_all_tracked_items(engine)
        assert len(items) == 2


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

class TestList:
    def test_list_empty(self, engine, capsys):
        main(["list"], engine=engine)
        out = capsys.readouterr().out
        assert "No tracked items." in out

    def test_list_shows_items(self, engine, capsys):
        main(["add", "Jordan 4 size 10"], engine=engine)
        main(["add", "Yeezy 350 size 11"], engine=engine)
        capsys.readouterr()

        main(["list"], engine=engine)
        out = capsys.readouterr().out

        assert "#1" in out
        assert "[collecting]" in out
        assert "Jordan 4 size 10" in out
        assert "#2" in out


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_set_active(self, engine, capsys):
        main(["add", "Item A"], engine=engine)
        main(["status", "1", "active"], engine=engine)
        out = capsys.readouterr().out

        assert "active" in out
        assert get_tracked_item(engine, 1)["status"] == "active"

    def test_set_collecting(self, engine, capsys):
        main(["add", "Item A"], engine=engine)
        main(["status", "1", "active"], engine=engine)
        main(["status", "1", "collecting"], engine=engine)
        out = capsys.readouterr().out

        assert "collecting" in out
        assert get_tracked_item(engine, 1)["status"] == "collecting"

    def test_status_nonexistent(self, engine, capsys):
        with pytest.raises(SystemExit, match="1"):
            main(["status", "99", "active"], engine=engine)
        out = capsys.readouterr().out
        assert "Item #99 not found." in out


# ---------------------------------------------------------------------------
# no command
# ---------------------------------------------------------------------------

class TestNoCommand:
    def test_no_args_exits(self, engine):
        with pytest.raises(SystemExit, match="1"):
            main([], engine=engine)
