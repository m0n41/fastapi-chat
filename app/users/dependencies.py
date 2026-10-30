from fastapi import Request, HTTPException
from app.config import settings
from app.db.session import SessionDep
from app.users.models import User
from app.users.jwt import decode_access_token
from sqlalchemy import select
import jwt

async def get_current_user(request: Request, session: SessionDep):
    cookie = request.cookies.get("access_token")
    if not cookie:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        sub = decode_access_token(cookie)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = await session.execute(
        select(User).where(User.id == sub)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return user