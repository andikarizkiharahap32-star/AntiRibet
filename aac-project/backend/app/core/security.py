from cryptography.fernet import Fernet, MultiFernet
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from app.core.config import settings
import base64
import logging

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class CredentialEncryption:
    def __init__(self):
        self.primary = Fernet(settings.fernet_key_bytes)
        if settings.fernet_key_new_bytes:
            self.secondary = Fernet(settings.fernet_key_new_bytes)
            self.multi = MultiFernet([self.primary, self.secondary])
        else:
            self.multi = None

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string to base64 encoded ciphertext."""
        if not plaintext:
            return ""
        token = self.primary.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(token).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt base64 encoded ciphertext to plaintext string."""
        if not ciphertext:
            return ""
        try:
            token = base64.urlsafe_b64decode(ciphertext.encode())
            if self.multi:
                plaintext = self.multi.decrypt(token)
            else:
                plaintext = self.primary.decrypt(token)
            return plaintext.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt credential")

    def re_encrypt(self, ciphertext: str) -> str:
        """Re-encrypt ciphertext with new key (for key rotation)."""
        if not self.multi:
            return ciphertext
        plaintext = self.decrypt(ciphertext)
        return self.encrypt(plaintext)


credential_encryption = CredentialEncryption()


def encrypt_password(password: str) -> str:
    return credential_encryption.encrypt(password)


def decrypt_password(encrypted_password: str) -> str:
    return credential_encryption.decrypt(encrypted_password)


# Password hashing functions
def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


# JWT token functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=settings.JWT_REFRESH_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str, expected_type: str = "access") -> Optional[dict]:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        token_type: str = payload.get("type")
        if token_type != expected_type:
            return None
        return payload
    except JWTError:
        return None