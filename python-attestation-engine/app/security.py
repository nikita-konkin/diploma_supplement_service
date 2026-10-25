"""Protection of the attestation service.

- the page opens only after the site login (scrypt hash of the password in the settings);
- sessions live in memory, expire after inactivity, and carry a CSRF token;
- failed logins are limited per client and in total;
- the remembered RITM password is stored with AES-256-GCM; the key is derived from the
  site password at login and kept only in the session, so the vault file alone is useless.
"""

from __future__ import annotations

import base64
import hmac
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

SCRYPT_N = 2 ** 15
SCRYPT_R = 8
SCRYPT_P = 1


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    # cryptography's scrypt, not hashlib's: Python built against LibreSSL (macOS) has none
    return Scrypt(salt=salt, length=32, n=n, r=r, p=p).derive(password.encode("utf-8"))


def hash_password(password: str) -> str:
    """Hash for ATTESTATION_PASSWORD_HASH: scrypt$n$r$p$salt$hash."""
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = encoded.split("$")
        if scheme != "scrypt":
            return False
        actual = _scrypt(password, _unb64(salt), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, _unb64(digest))


def derive_vault_key(password: str, salt: bytes) -> bytes:
    return _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)


@dataclass
class Session:
    token: str
    csrf: str
    vault_key: bytes
    created: float = field(default_factory=time.monotonic)
    last_seen: float = field(default_factory=time.monotonic)


class SessionStore:
    def __init__(self, idle_seconds: int, absolute_seconds: int) -> None:
        self.idle_seconds = idle_seconds
        self.absolute_seconds = absolute_seconds
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, vault_key: bytes) -> Session:
        session = Session(
            token=secrets.token_urlsafe(32),
            csrf=secrets.token_urlsafe(32),
            vault_key=vault_key,
        )
        with self._lock:
            self._sessions[session.token] = session
        return session

    def get(self, token: Optional[str]) -> Optional[Session]:
        if not token:
            return None
        now = time.monotonic()
        with self._lock:
            session = self._sessions.get(token)
            if session is None:
                return None
            if now - session.last_seen > self.idle_seconds or now - session.created > self.absolute_seconds:
                del self._sessions[token]
                return None
            session.last_seen = now
            return session

    def drop(self, token: Optional[str]) -> None:
        with self._lock:
            self._sessions.pop(token or "", None)


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


class Vault:
    """Remembered RITM login and password, encrypted with the session's vault key."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.path = directory / "ritm-vault.json"
        self.salt_path = directory / "vault-salt"

    def salt(self) -> bytes:
        self.directory.mkdir(parents=True, exist_ok=True)
        if not self.salt_path.exists():
            self._write(self.salt_path, secrets.token_bytes(16))
        return self.salt_path.read_bytes()

    def save(self, key: bytes, login: str, password: str) -> None:
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(key).encrypt(nonce, password.encode("utf-8"), login.encode("utf-8"))
        record = {"version": 1, "login": login, "nonce": _b64(nonce), "ciphertext": _b64(ciphertext)}
        self._write(self.path, json.dumps(record).encode("utf-8"))

    def stored_login(self) -> Optional[str]:
        record = self._read()
        return record["login"] if record else None

    def load(self, key: bytes) -> Optional[tuple[str, str]]:
        record = self._read()
        if record is None:
            return None
        try:
            password = AESGCM(key).decrypt(
                _unb64(record["nonce"]), _unb64(record["ciphertext"]), record["login"].encode("utf-8")
            )
        except (InvalidTag, KeyError, ValueError):
            return None
        return record["login"], password.decode("utf-8")

    def forget(self) -> None:
        self.path.unlink(missing_ok=True)

    def _read(self) -> Optional[dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return None

    def _write(self, path: Path, data: bytes) -> None:
        temporary = path.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
