"""At-rest encryption for secrets stored in the database.

Currently one user: per-user LinkedIn app credentials (backend/models/user.py,
backend/api/integrations_routes.py). Anything else that needs to store a
secret client-side value should use this rather than adding a second scheme.

The Fernet key is derived from SECRET_KEY rather than requiring a dedicated
env var, so this doesn't add a new secret an operator has to generate and
rotate on day one. That is a real trade-off: rotating SECRET_KEY (which also
signs every session token) now also re-derives this key and makes existing
ciphertext unreadable. Set ENCRYPTION_KEY explicitly to decouple the two once
that matters; until then this keeps setup to the variables the app already
requires.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from backend.utils.config import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    material = settings.encryption_key or settings.secret_key
    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise ValueError("Ciphertext does not decrypt with the current key") from e
