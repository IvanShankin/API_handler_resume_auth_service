from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update, func, cast, Boolean, delete
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends, HTTPException, status, APIRouter, Query
from srt.data_base.data_base import get_db

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta

from srt.schemas.response import TokenResponse
from srt.tokens import create_access_token, create_refresh_token, get_current_user, oauth2_scheme
from srt.data_base.models import User
from srt.data_base.data_base import get_db


router = APIRouter()

@router.post('/login', response_model=TokenResponse)
async def login()