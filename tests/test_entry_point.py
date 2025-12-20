"""Sanity check that the package entry point is correctly registered."""


def test_entry_point_importable():
    """The setup function should be importable."""
    from jupyter_marimo_proxy import setup_marimoserver

    assert callable(setup_marimoserver)


def test_entry_point_registered():
    """Entry point 'marimo' should be registered."""
    from importlib.metadata import entry_points

    try:
        eps = entry_points(group="jupyter_serverproxy_servers")
        names = [ep.name for ep in eps]
    except TypeError:
        eps = entry_points()
        names = [ep.name for ep in eps.get("jupyter_serverproxy_servers", [])]

    assert "marimo" in names
