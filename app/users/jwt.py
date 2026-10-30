from app.config import settings
from datetime import datetime, timedelta, timezone
import jwt

def create_access_token(user_id: int) -> str:
    secret_key = settings.jwt_secret_key
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return token

def decode_access_token(token: str) -> int:
    secret_key = settings.jwt_secret_key
    token_decode = jwt.decode(
        token,
        secret_key,
        algorithms=["HS256"],
        options={"require": ["exp", "sub"]}
    )
    try:
        return int(token_decode.get("sub"))
    except (TypeError, ValueError):
        raise jwt.InvalidTokenError()