"""Shared FastAPI dependencies."""

import secrets
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlmodel import Session

from backend.settings import Settings


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


def require_admin_key(
    settings: Annotated[Settings, Depends(get_settings_dep)],
    x_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    """Admin routes need the X-Admin-Key header. With no key configured they are always refused."""
    expected = settings.admin_key
    if not expected or not x_admin_key or not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid admin key")
