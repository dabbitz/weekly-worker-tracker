"""Generate an Argon2 hash for the WorkTrack dashboard password.

Usage:
    python scripts/hash_admin_password.py

The plaintext password is read interactively and is never printed,
logged, or written to disk. Copy the printed hash into
ADMIN_PASSWORD_HASH in the root .env file.
"""

from __future__ import annotations

import getpass
import sys

from argon2 import PasswordHasher
from argon2.exceptions import HashingError


MIN_PASSWORD_LENGTH = 12


def _configure_console() -> None:
    """Avoid cp1252 crashes when Turkish characters are printed."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    _configure_console()
    password = getpass.getpass("Yönetici parolası: ")

    if len(password) < MIN_PASSWORD_LENGTH:
        print(
            "Parola en az "
            f"{MIN_PASSWORD_LENGTH} karakter olmalıdır.",
            file=sys.stderr,
        )
        return 1

    confirmation = getpass.getpass("Parolayı tekrar girin: ")

    if password != confirmation:
        print("Parolalar eşleşmiyor.", file=sys.stderr)
        return 1

    try:
        password_hash = PasswordHasher().hash(password)
    except HashingError as exc:
        print(f"Hash oluşturulamadı: {exc}", file=sys.stderr)
        return 1

    print()
    print("ADMIN_PASSWORD_HASH değeri:")
    print(password_hash)
    print()
    print("Bu değeri .env dosyasına kopyalayın. Parolayı paylaşmayın.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
