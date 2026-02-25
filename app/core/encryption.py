import base64
import hashlib
import json
import logging

from cryptography.fernet import Fernet

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    key = settings.BROKER_ENCRYPTION_KEY
    if not key:
        key = hashlib.sha256(settings.JWT_SECRET_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(key)
    else:
        if isinstance(key, str):
            key = key.encode()
    return Fernet(key)


def encrypt_credentials(credentials: dict) -> str:
    f = _get_fernet()
    raw = json.dumps(credentials).encode("utf-8")
    return f.encrypt(raw).decode("utf-8")


def decrypt_credentials(encrypted: str) -> dict:
    f = _get_fernet()
    raw = f.decrypt(encrypted.encode("utf-8"))
    return json.loads(raw.decode("utf-8"))
