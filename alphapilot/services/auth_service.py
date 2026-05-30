from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


JWT_ALGORITHM = "HS256"


def create_access_token(user: dict[str, Any], secret_key: str, expire_minutes: int = 1440) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> dict[str, Any]:
    return jwt.decode(token, secret_key, algorithms=[JWT_ALGORITHM])
