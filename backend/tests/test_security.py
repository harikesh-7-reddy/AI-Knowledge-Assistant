from app.security import hash_password, verify_password


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("CorrectHorseBattery!")
    second = hash_password("CorrectHorseBattery!")
    assert first != second
    assert verify_password("CorrectHorseBattery!", first)
    assert not verify_password("WrongPassword", first)


def test_password_minimum_length():
    try:
        hash_password("short")
    except ValueError:
        return
    raise AssertionError("Short password should have been rejected")
