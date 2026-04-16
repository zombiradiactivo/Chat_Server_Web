from abc import ABC, abstractmethod
import os
from typing import Any


class EncryptionPlugin(ABC):
    @abstractmethod
    def encrypt(self, data: str, key: str = None) -> str:
        pass

    @abstractmethod
    def decrypt(self, data: str, key: str = None) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


class DatabaseEncryption(EncryptionPlugin):
    @property
    def name(self) -> str:
        return "database"

    def encrypt(self, data: str, key: str = None) -> str:
        from cryptography.fernet import Fernet
        if key is None:
            from app.config import settings
            key = settings.SECRET_KEY
        f = Fernet(self._derive_key(key))
        return f.encrypt(data.encode()).decode()

    def decrypt(self, data: str, key: str = None) -> str:
        from cryptography.fernet import Fernet
        if key is None:
            from app.config import settings
            key = settings.SECRET_KEY
        f = Fernet(self._derive_key(key))
        return f.decrypt(data.encode()).decode()

    def _derive_key(self, key: str) -> bytes:
        from cryptography.fernet import Fernet
        import hashlib
        return Fernet.generate_key() if len(key) < 32 else hashlib.sha256(key.encode()).digest()


class E2EEncryption(EncryptionPlugin):
    @property
    def name(self) -> str:
        return "e2e"

    def encrypt(self, data: str, key: str = None) -> str:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import base64
        if key is None:
            key = AESGCM.generate_key(bit_length=256)
        else:
            key = base64.b64decode(key)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, data.encode(), None)
        return base64.b64encode(nonce + ciphertext).decode()

    def decrypt(self, data: str, key: str = None) -> str:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import base64
        if key is None:
            raise ValueError("E2E encryption requires a key")
        key_bytes = base64.b64decode(key)
        aesgcm = AESGCM(key_bytes)
        encrypted = base64.b64decode(data)
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        return aesgcm.decrypt(nonce, ciphertext, None).decode()


import os


ENCRYPTION_PLUGINS = {
    "database": DatabaseEncryption(),
    "e2e": E2EEncryption(),
}


def get_encryption_plugin(mode: str) -> EncryptionPlugin:
    return ENCRYPTION_PLUGINS.get(mode, ENCRYPTION_PLUGINS["database"])