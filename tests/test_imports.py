"""Smoke tests: verify all entry points import without error.

These catch stale imports (renamed/removed functions) that would crash
at startup but might not be exercised by any unit test.
"""


def test_root_poller_imports():
    import poller  # noqa: F401


def test_manage_items_imports():
    import manage_items  # noqa: F401


def test_dev_server_imports():
    import dev_server  # noqa: F401


def test_package_poller_imports():
    from resale_price_agent import poller  # noqa: F401


def test_package_app_imports():
    from resale_price_agent import app  # noqa: F401


def test_package_price_drop_imports():
    from resale_price_agent import price_drop  # noqa: F401


def test_package_notifier_imports():
    from resale_price_agent import notifier  # noqa: F401
