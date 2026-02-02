from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_SESSION_SALT = "capa-session"


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.required_secret_key, salt=_SESSION_SALT)


def create_session_token(user_id: int, role: str) -> str:
    payload = {"uid": user_id, "role": role}
    return _get_serializer().dumps(payload)


def decode_session_token(token: str, max_age_seconds: int) -> dict[str, str | int] | None:
    serializer = _get_serializer()
    try:
        return serializer.loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
