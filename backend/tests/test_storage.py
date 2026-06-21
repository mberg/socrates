from app.storage import InMemoryObjectStore


def test_in_memory_put_stores_bytes():
    store = InMemoryObjectStore()
    key = store.put("worksheets/x.pdf", b"%PDF-1.4", "application/pdf")
    assert key == "worksheets/x.pdf"
    assert store.objects["worksheets/x.pdf"] == b"%PDF-1.4"
