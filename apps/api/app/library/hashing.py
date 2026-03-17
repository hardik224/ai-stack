import hashlib
import secrets

from passlib.context import CryptContext


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_session_token() -> str:
    return secrets.token_urlsafe(48)


def generate_api_key() -> str:
    return f"ask_{secrets.token_urlsafe(40)}"
