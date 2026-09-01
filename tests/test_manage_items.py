"""Tests for the item management CLI."""

import pytest
from sqlalchemy import create_engine

from manage_items import main
from resale_price_agent.db import (
    add_tracked_item,
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

        assert 'Added item #1: "Jordan 4 Military Black size 10"' in out
        items = get_all_tracked_items(engine)
        assert len(items) == 1
        assert items[0]["search_query"] == "Jordan 4 Military Black size 10"
        assert items[0]["active"] is True

    def test_add_with_target_price(self, engine, capsys):
        main(
            ["add", "Yeezy 350 size 11", "--target-price", "180"],
            engine=engine,
        )
        out = capsys.readouterr().out

        assert "(target: $180.00)" in out
        items = get_all_tracked_items(engine)
        assert items[0]["target_price"] == 180.0

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
        main(["add", "Yeezy 350 size 11", "--target-price", "180"], engine=engine)
        capsys.readouterr()  # clear add output

        main(["list"], engine=engine)
        out = capsys.readouterr().out

        assert "#1" in out
        assert "[active]" in out
        assert "Jordan 4 size 10" in out
        assert "#2" in out
        assert "target=$180.00" in out

    def test_list_shows_paused(self, engine, capsys):
        main(["add", "Item A"], engine=engine)
        main(["pause", "1"], engine=engine)
        capsys.readouterr()

        main(["list"], engine=engine)
        out = capsys.readouterr().out

        assert "[paused]" in out


# ---------------------------------------------------------------------------
# pause / resume
# ---------------------------------------------------------------------------

class TestPauseResume:
    def test_pause(self, engine, capsys):
        main(["add", "Item A"], engine=engine)
        main(["pause", "1"], engine=engine)
        out = capsys.readouterr().out

        assert "Paused item #1." in out
        assert get_tracked_item(engine, 1)["active"] is False

    def test_resume(self, engine, capsys):
        main(["add", "Item A"], engine=engine)
        main(["pause", "1"], engine=engine)
        main(["resume", "1"], engine=engine)
        out = capsys.readouterr().out

        assert "Resumed item #1." in out
        assert get_tracked_item(engine, 1)["active"] is True

    def test_pause_nonexistent(self, engine, capsys):
        with pytest.raises(SystemExit, match="1"):
            main(["pause", "99"], engine=engine)
        out = capsys.readouterr().out
        assert "Item #99 not found." in out

    def test_resume_nonexistent(self, engine, capsys):
        with pytest.raises(SystemExit, match="1"):
            main(["resume", "99"], engine=engine)
        out = capsys.readouterr().out
        assert "Item #99 not found." in out


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------

class TestRemove:
    def test_remove(self, engine, capsys):
        main(["add", "Item A"], engine=engine)
        main(["remove", "1"], engine=engine)
        out = capsys.readouterr().out

        assert "Removed item #1." in out
        assert get_tracked_item(engine, 1) is None

    def test_remove_nonexistent(self, engine, capsys):
        with pytest.raises(SystemExit, match="1"):
            main(["remove", "99"], engine=engine)
        out = capsys.readouterr().out
        assert "Item #99 not found." in out


# ---------------------------------------------------------------------------
# no command
# ---------------------------------------------------------------------------

class TestNoCommand:
    def test_no_args_exits(self, engine):
        with pytest.raises(SystemExit, match="1"):
            main([], engine=engine)
