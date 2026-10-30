from fastapi import APIRouter, HTTPException, Response, Depends
from fastapi.responses import JSONResponse
from app.db.session import SessionDep
from app.users.schemas import UserCreate, UserResponse, UserLogin
from app.users.security import hash_password, verify_password
from app.users.models import User
from app.users.jwt import create_access_token
from app.users.dependencies import get_current_user
from sqlalchemy import select, or_
from typing import Annotated

router = APIRouter()

@router.post("/api/auth/register", response_model=UserResponse, status_code=201)
async def post_api_auth_register(user: UserCreate, session: SessionDep) -> UserResponse:
    query = select(User).where(
        or_(
            User.username == user.username,
            User.email == user.email
        )
    )
    result = await session.execute(query)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Такой пользователь уже существует")
    
    password_hash = hash_password(user.password)
    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=password_hash,
    )
    
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user

@router.post("/api/auth/login", response_model=UserResponse)
async def post_api_auth_login(user: UserLogin, session: SessionDep, response: Response) -> UserResponse:
    new_user = await session.execute(
        select(User).where(User.username == user.username)
    )
    result = new_user.scalar_one_or_none()
    if result is None:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    
    if verify_password(user.password, result.hashed_password) is False:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    
    token = create_access_token(result.id)
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=1800,
        httponly=True,
        samesite="lax",
        secure=False
    )
    
    return result


@router.get("/api/users/me", response_model=UserResponse)
async def get_api_users_me(user: Annotated[User, Depends(get_current_user)]):
    return user

@router.post("/api/auth/logout")
async def post_api_auth_logout():
    response = JSONResponse(
        status_code=200,
        content={"message": "Вы успешно вышли"}
    )
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return response