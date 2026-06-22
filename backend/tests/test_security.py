from app.security import hash_pin, verify_pin


def test_hash_is_not_plaintext_and_verifies():
    h = hash_pin("1234")
    assert "1234" not in h
    assert verify_pin("1234", h) is True
    assert verify_pin("0000", h) is False


def test_no_stored_pin_verifies_open():
    assert verify_pin("anything", None) is True
    assert verify_pin("anything", "") is True


def test_two_hashes_of_same_pin_differ_by_salt():
    assert hash_pin("1234") != hash_pin("1234")  # random salt
