import stat

from app.security import LoginLimiter, SessionStore, Vault, derive_vault_key, hash_password, verify_password


def test_cannot_accept_wrong_site_password():
    assert not verify_password("guess", hash_password("real password")), "Wrong site password was accepted"


def test_cannot_hash_two_passwords_alike():
    assert hash_password("same") != hash_password("same"), "Password hash is not salted"


def test_cannot_accept_malformed_hash():
    assert not verify_password("anything", "md5$abc"), "Malformed hash let a password through"


def test_cannot_store_ritm_password_in_plaintext(tmp_path):
    vault = Vault(tmp_path)
    vault.save(derive_vault_key("site", vault.salt()), "marstu.net\\tester", "ritm-secret-42")
    assert b"ritm-secret-42" not in vault.path.read_bytes(), "Vault stored the RITM password in plaintext"


def test_cannot_open_vault_with_other_site_password(tmp_path):
    vault = Vault(tmp_path)
    vault.save(derive_vault_key("site", vault.salt()), "marstu.net\\tester", "ritm-secret-42")
    assert vault.load(derive_vault_key("other", vault.salt())) is None, "Vault opened with a wrong key"


def test_cannot_swap_login_in_vault(tmp_path):
    vault = Vault(tmp_path)
    key = derive_vault_key("site", vault.salt())
    vault.save(key, "marstu.net\\tester", "ritm-secret-42")
    vault.path.write_text(vault.path.read_text().replace("tester", "intruder"))
    assert vault.load(key) is None, "Vault decrypted a password for a substituted login"


def test_cannot_let_others_read_vault(tmp_path):
    vault = Vault(tmp_path)
    vault.save(derive_vault_key("site", vault.salt()), "marstu.net\\tester", "ritm-secret-42")
    assert stat.S_IMODE(vault.path.stat().st_mode) == 0o600, "Vault file is readable by other users"


def test_cannot_keep_idle_session():
    store = SessionStore(idle_seconds=-1, absolute_seconds=3600)
    session = store.create(b"key")
    assert store.get(session.token) is None, "Idle session stayed valid"


def test_cannot_keep_session_after_logout():
    store = SessionStore(idle_seconds=3600, absolute_seconds=3600)
    session = store.create(b"key")
    store.drop(session.token)
    assert store.get(session.token) is None, "Session survived logout"


def test_cannot_guess_forever_from_one_client():
    limiter = LoginLimiter(per_client=3, total=100, window_seconds=60)
    for _ in range(3):
        limiter.failed("10.0.0.1")
    assert not limiter.allowed("10.0.0.1"), "Limiter allowed a fourth failed login"


def test_cannot_dodge_limit_by_changing_address():
    limiter = LoginLimiter(per_client=100, total=3, window_seconds=60)
    for address in ("10.0.0.1", "10.0.0.2", "10.0.0.3"):
        limiter.failed(address)
    assert not limiter.allowed("10.0.0.4"), "Limiter ignored failures spread over addresses"
