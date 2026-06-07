import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def encrypt_data(data: bytes, password: str) -> bytes:
    """Encrypts raw bytes with a password."""
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    f = Fernet(key)
    ciphertext = f.encrypt(data)
    # prepend salt so it can be extracted during decryption
    return salt + ciphertext

def decrypt_data(packed_data: bytes, password: str) -> bytes:
    """Decrypts raw bytes (salt + ciphertext) with a password."""
    try:
        if len(packed_data) < 16:
            return None
        salt = packed_data[:16]
        ciphertext = packed_data[16:]
        
        key = _derive_key(password, salt)
        f = Fernet(key)
        return f.decrypt(ciphertext)
    except Exception as e:
        return None
