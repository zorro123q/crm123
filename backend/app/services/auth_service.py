"""
Shared authentication helpers.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models import User


INVALID_CREDENTIALS_MESSAGE = "用户名或密码错误"


def normalize_username(username: str) -> str:
    return (username or "").strip()


def validate_username(username: str) -> str:
    normalized = normalize_username(username)
    if not normalized:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    return normalized


def validate_password(password: str) -> str:
    normalized = (password or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="密码不能为空")
    return password


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    normalized = normalize_username(username)
    if not normalized:
        return None

    result = await db.execute(select(User).where(User.username == normalized))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    user = await get_user_by_username(db, username)
    if not user or not verify_password(password, user.password):
        return None

    return user


async def create_user_account(db: AsyncSession, username: str, password: str) -> User:
    normalized_username = validate_username(username)
    raw_password = validate_password(password)

    existing_user = await get_user_by_username(db, normalized_username)
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=normalized_username,
        password=hash_password(raw_password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="用户创建失败，请检查用户名是否重复") from exc

    await db.refresh(user)
    return user
