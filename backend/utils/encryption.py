"""
Encryption utilities for sensitive data.

Uses Fernet (AES-128 symmetric encryption) for encrypting/decrypting
LinkedIn OAuth tokens and other sensitive credentials.
"""

from cryptography.fernet import Fernet
from backend.utils.config import get_settings
import logging

logger = logging.getLogger(__name__)


def get_cipher() -> Fernet:
    """Get Fernet cipher instance using ENCRYPTION_KEY from config."""
    settings = get_settings()
    encryption_key = settings.encryption_key

    if not encryption_key:
        raise ValueError("ENCRYPTION_KEY not configured in environment")

    # Ensure key is in bytes
    if isinstance(encryption_key, str):
        encryption_key = encryption_key.encode()

    return Fernet(encryption_key)


def encrypt_credential(plaintext: str) -> str:
    """
    Encrypt a credential (token, secret, etc.).

    Args:
        plaintext: Unencrypted credential string

    Returns:
        Encrypted credential string (base64 encoded)
    """
    try:
        cipher = get_cipher()
        encrypted = cipher.encrypt(plaintext.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Encryption failed: {str(e)}")
        raise ValueError("Failed to encrypt credential")


def decrypt_credential(encrypted: str) -> str:
    """
    Decrypt a credential.

    Args:
        encrypted: Encrypted credential string (base64 encoded)

    Returns:
        Decrypted credential string
    """
    try:
        cipher = get_cipher()
        decrypted = cipher.decrypt(encrypted.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Decryption failed: {str(e)}")
        raise ValueError("Failed to decrypt credential")


def encrypt_token(token: str) -> str:
    """Convenience wrapper for encrypting OAuth tokens."""
    return encrypt_credential(token)


def decrypt_token(encrypted_token: str) -> str:
    """Convenience wrapper for decrypting OAuth tokens."""
    return decrypt_credential(encrypted_token)
