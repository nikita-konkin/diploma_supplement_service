"""Protection of the attestation service.

- the page opens only after a login with the RITM portal account: the portal checks the
  password, the service keeps only the portal's session, never the password;
- sessions live in memory, expire after inactivity, and carry a CSRF token;
- failed logins are limited per client and in total, so the site cannot be used to guess
  portal passwords.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Session:
    token: str
    csrf: str
    login: str
    # requests.Session with the portal's cookies; the password itself is not kept
    portal: Any = field(repr=False)
    created: float = field(default_factory=time.monotonic)
    last_seen: float = field(default_factory=time.monotonic)


class SessionStore:
    def __init__(self, idle_seconds: int, absolute_seconds: int) -> None:
        self.idle_seconds = idle_seconds
        self.absolute_seconds = absolute_seconds
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, login: str, portal: Any) -> Session:
        session = Session(
            token=secrets.token_urlsafe(32),
            csrf=secrets.token_urlsafe(32),
            login=login,
            portal=portal,
        )
        with self._lock:
            self._sessions[session.token] = session
        return session

    def _expired(self, session: Session, now: float) -> bool:
        return now - session.last_seen > self.idle_seconds or now - session.created > self.absolute_seconds

    def get(self, token: Optional[str]) -> Optional[Session]:
        if not token:
            return None
        now = time.monotonic()
        with self._lock:
            session = self._sessions.get(token)
            if session is None:
                return None
            if self._expired(session, now):
                del self._sessions[token]
                _close(session)
                return None
            session.last_seen = now
            return session

    def drop(self, token: Optional[str]) -> None:
        with self._lock:
            session = self._sessions.pop(token or "", None)
        if session is not None:
            _close(session)

    def sweep(self) -> int:
        """Forget expired sessions nobody comes back to; returns how many were removed."""
        now = time.monotonic()
        with self._lock:
            expired = [token for token, session in self._sessions.items() if self._expired(session, now)]
            removed = [self._sessions.pop(token) for token in expired]
        for session in removed:
            _close(session)
        return len(removed)


def _close(session: Session) -> None:
    close = getattr(session.portal, "close", None)
    if close is not None:
        close()


class LoginLimiter:
    """Failed logins: per client and in total, so a spoofed address does not help."""

    def __init__(self, per_client: int, total: int, window_seconds: int) -> None:
        self.per_client = per_client
        self.total = total
        self.window_seconds = window_seconds
        self._failures: dict[str, deque] = defaultdict(deque)
        self._all: deque = deque()
        self._lock = threading.Lock()

    def _trim(self, events: deque, now: float) -> None:
        while events and now - events[0] > self.window_seconds:
            events.popleft()

    def allowed(self, client: str) -> bool:
        now = time.monotonic()
        with self._lock:
            self._trim(self._failures[client], now)
            self._trim(self._all, now)
            return len(self._failures[client]) < self.per_client and len(self._all) < self.total

    def failed(self, client: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._failures[client].append(now)
            self._all.append(now)

    def succeeded(self, client: str) -> None:
        with self._lock:
            self._failures.pop(client, None)
