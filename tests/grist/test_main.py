import app.main as main


class _FakeClient:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None


def test_sync_order(monkeypatch):
    """Schema, then rows, then prices — each step needs the previous one."""
    calls: list[str] = []

    monkeypatch.setattr(main, "check_grist", lambda: calls.append("check_grist"))
    monkeypatch.setattr(main, "GristClient", lambda *a, **kw: _FakeClient())
    # Patched so the test never reaches the network.
    monkeypatch.setattr(main, "BazaarClient", lambda *a, **kw: _FakeClient())
    monkeypatch.setattr(
        main,
        "sync_gem_table_schema",
        lambda *a, **kw: calls.append("sync_gem_table_schema"),
    )
    monkeypatch.setattr(
        main,
        "sync_gem_table_records",
        lambda *a, **kw: calls.append("sync_gem_table_records"),
    )
    monkeypatch.setattr(
        main, "sync_gem_prices", lambda *a, **kw: calls.append("sync_gem_prices")
    )

    main.main()

    assert calls == [
        "check_grist",
        "sync_gem_table_schema",
        "sync_gem_table_records",
        "sync_gem_prices",
    ]
