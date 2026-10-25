from app.security import LoginLimiter, SessionStore


class Closable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_cannot_keep_idle_session():
    store = SessionStore(idle_seconds=-1, absolute_seconds=3600)
    session = store.create("tester", Closable())
    assert store.get(session.token) is None, "Idle session stayed valid"


def test_cannot_keep_session_after_logout():
    store = SessionStore(idle_seconds=3600, absolute_seconds=3600)
    session = store.create("tester", Closable())
    store.drop(session.token)
    assert store.get(session.token) is None, "Session survived logout"


def test_cannot_leave_portal_connection_open_after_logout():
    store = SessionStore(idle_seconds=3600, absolute_seconds=3600)
    portal = Closable()
    store.drop(store.create("tester", portal).token)
    assert portal.closed, "Portal session stayed open after logout"


def test_cannot_keep_abandoned_sessions_in_memory():
    store = SessionStore(idle_seconds=-1, absolute_seconds=3600)
    store.create("tester", Closable())
    assert store.sweep() == 1, "Expired session nobody came back to stayed in memory"


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
