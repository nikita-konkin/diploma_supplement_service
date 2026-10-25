"""Hash for ATTESTATION_PASSWORD_HASH in .env: asks for the site password twice, prints the hash.

    python tools/hash_password.py
    docker compose run --rm --no-deps python-attestation-engine python tools/hash_password.py
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.security import hash_password  # noqa: E402


def main() -> int:
    password = getpass.getpass("Пароль для входа в сервис аттестации: ")
    if len(password) < 12:
        print("Нужно не меньше 12 символов.", file=sys.stderr)
        return 1
    if getpass.getpass("Ещё раз: ") != password:
        print("Пароли не совпадают.", file=sys.stderr)
        return 1
    # Single quotes: otherwise docker compose reads each $ in the hash as a variable
    print(f"ATTESTATION_PASSWORD_HASH='{hash_password(password)}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
