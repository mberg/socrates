import pytest

from app.storage import InMemoryObjectStore


def test_in_memory_put_stores_bytes():
    store = InMemoryObjectStore()
    key = store.put("worksheets/x.pdf", b"%PDF-1.4", "application/pdf")
    assert key == "worksheets/x.pdf"
    assert store.objects["worksheets/x.pdf"] == b"%PDF-1.4"


def test_in_memory_get_returns_stored_bytes():
    from app.storage import InMemoryObjectStore
    store = InMemoryObjectStore()
    store.put("prints/abc.pdf", b"%PDF-data", "application/pdf")
    assert store.get("prints/abc.pdf") == b"%PDF-data"


def test_in_memory_get_missing_raises_keyerror():
    import pytest
    from app.storage import InMemoryObjectStore
    with pytest.raises(KeyError):
        InMemoryObjectStore().get("nope")
