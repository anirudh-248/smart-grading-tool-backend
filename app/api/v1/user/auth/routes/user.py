from fastapi import APIRouter, HTTPException, Depends, status
from passlib.context import CryptContext
from app.db.prisma_client import get_prisma
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from jose import jwt, JWTError, ExpiredSignatureError
from app.api.v1.user.auth.models.user import Register, OTPVerify, Login, ResetPassword, EmailOnlyRequest
from app.api.v1.user.auth.mails.templates import sign_up_template, forgot_password_template
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.utils.mail_handler import send_mail
from app.utils.success_handler import success_response
from prisma import Prisma
from prisma.enums import Role
from env import env
import logging, random


# Config
SECRET_KEY = env.JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

bearer_scheme = HTTPBearer()


# JWT Utils
def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


router = APIRouter()


# Auth Dependencies
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme), prisma: Prisma = Depends(get_prisma)):
    try:
        token = credentials.credentials
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        email = payload.get("email")
        user_id = payload.get("id")
        if not email or not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims")

        user = await prisma.user.find_first(where={"email": email, "id": user_id, "is_deleted": False})
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user

    except HTTPException as he:
        logging.error("HTTPException: %s", he)
        raise he
    except Exception as e:
        code = getattr(e, 'code', getattr(e, 'status_code', 500))
        logging.error("Error Code: %s, Message: %s", code, str(e), exc_info=True)
        raise HTTPException(status_code=code, detail=str(e))


async def get_current_admin(current_user=Depends(get_current_user)):
    if current_user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin access only !")
    return current_user


# APIs
@router.post("/register", status_code=201)
async def register(request: Register, prisma: Prisma = Depends(get_prisma)):
    try:
        async with prisma.tx(timeout=65000, max_wait=80000) as tx:
            existing = await tx.user.find_first(where={"email": request.email})
            if existing:
                if not existing.is_deleted:
                    raise HTTPException(400, "User already registered")
                raise HTTPException(409, "Account deleted. Restore?")

            await tx.otpsession.delete_many(where={"email": request.email, "type": "signup"})
            otp = str(random.randint(100000, 999999))
            session = await tx.otpsession.create(data={
                "name": request.name,
                "email": request.email,
                "hashed_password": get_password_hash(request.password),
                "otp": otp,
                "type": "signup"
            })
            await send_mail([request.email], "SmartGrader: Verify Your Account", sign_up_template(otp))
            return success_response("OTP sent", {"session_id": session.session_id})

    except HTTPException as he:
        logging.error("HTTPException: %s", he)
        raise he
    except Exception as e:
        code = getattr(e, 'code', getattr(e, 'status_code', 500))
        logging.error("Error Code: %s, Message: %s", code, str(e), exc_info=True)
        raise HTTPException(code, str(e))


@router.put("/verify/otp")
async def verify_otp(request: OTPVerify, prisma: Prisma = Depends(get_prisma)):
    try:
        async with prisma.tx(timeout=65000, max_wait=80000) as tx:
            session = await tx.otpsession.find_first(where={"session_id": request.session_id})
            if not session or session.otp != request.otp:
                raise HTTPException(400, "Invalid session or OTP")

            existing = await tx.user.find_first(where={"email": session.email})
            if existing:
                raise HTTPException(409 if existing.is_deleted else 400, "User exists or deleted")

            await tx.user.create(data={
                "name": session.name,
                "email": session.email,
                "hashed_password": session.hashed_password,
                "is_email_verified": True
            })
            await tx.otpsession.delete_many(where={"session_id": session.session_id})
            return success_response("OTP verified")

    except HTTPException as he:
        logging.error("HTTPException: %s", he)
        raise he
    except Exception as e:
        code = getattr(e, 'code', getattr(e, 'status_code', 500))
        logging.error("Error Code: %s, Message: %s", code, str(e), exc_info=True)
        raise HTTPException(code, str(e))


@router.post("/resend-otp")
async def resend_otp(session_id: str, prisma: Prisma = Depends(get_prisma)):
    try:
        async with prisma.tx(timeout=65000, max_wait=80000) as tx:
            session = await tx.otpsession.find_first(where={"session_id": session_id})
            if not session:
                raise HTTPException(400, "Session not found")

            otp = str(random.randint(100000, 999999))
            await tx.otpsession.update(where={"session_id": session_id}, data={"otp": otp})
            await send_mail([session.email], "SmartGrader: Verify Your Account", sign_up_template(otp))
            return success_response("OTP resent", {"session_id": session_id})

    except HTTPException as he:
        logging.error("HTTPException: %s", he)
        raise he
    except Exception as e:
        code = getattr(e, 'code', getattr(e, 'status_code', 500))
        logging.error("Error Code: %s, Message: %s", code, str(e), exc_info=True)
        raise HTTPException(code, str(e))


@router.post("/login")
async def login(request: Login, prisma: Prisma = Depends(get_prisma)):
    try:
        user = await prisma.user.find_first(where={"email": request.email})
        if not user:
            raise HTTPException(404, "User not registered")
        if not verify_password(request.password, user.hashed_password):
            raise HTTPException(400, "Incorrect password")
        if user.is_deleted:
            raise HTTPException(409, "Account is soft-deleted")

        token = create_access_token({"id": user.id, "email": user.email})
        return success_response("Login successful", {"access_token": token})

    except HTTPException as he:
        logging.error("HTTPException: %s", he)
        raise he
    except Exception as e:
        code = getattr(e, 'code', getattr(e, 'status_code', 500))
        logging.error("Error Code: %s, Message: %s", code, str(e), exc_info=True)
        raise HTTPException(code, str(e))


@router.post("/refresh-token")
async def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme), prisma: Prisma = Depends(get_prisma)):
    try:
        try:
            payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        except JWTError:
            raise HTTPException(401, "Invalid token format")

        email, user_id = payload.get("email"), payload.get("id")
        if not email or not user_id:
            raise HTTPException(401, "Invalid token claims")

        user = await prisma.user.find_first(where={"email": email, "id": user_id, "is_deleted": False})
        if not user:
            raise HTTPException(401, "User not found or inactive")

        new_token = create_access_token({"id": user.id, "email": user.email})
        return success_response("Token refreshed", {"access_token": new_token})

    except HTTPException as he:
        logging.error("HTTPException: %s", he)
        raise he
    except Exception as e:
        code = getattr(e, 'code', getattr(e, 'status_code', 500))
        logging.error("Error Code: %s, Message: %s", code, str(e), exc_info=True)
        raise HTTPException(code, str(e))


@router.post("/forgot-password/{email}")
async def forgot_password(email: str, prisma: Prisma = Depends(get_prisma)):
    try:
        async with prisma.tx(timeout=65000, max_wait=80000) as tx:
            user = await tx.user.find_first(where={"email": email})
            if not user:
                raise HTTPException(404, "User not found")

            await tx.otpsession.delete_many(where={"email": email, "type": "password_reset"})
            otp = str(random.randint(100000, 999999))
            session = await tx.otpsession.create(data={"email": email, "otp": otp, "type": "password_reset", "hashed_password": user.hashed_password})
            await send_mail([email], "SmartGrader: Password Reset", forgot_password_template(otp))
            return success_response("OTP sent", {"session_id": session.session_id})

    except HTTPException as he:
        logging.error("HTTPException: %s", he)
        raise he
    except Exception as e:
        code = getattr(e, 'code', getattr(e, 'status_code', 500))
        logging.error("Error Code: %s, Message: %s", code, str(e), exc_info=True)
        raise HTTPException(code, str(e))


@router.post("/reset-password")
async def reset_password(request: ResetPassword, prisma: Prisma = Depends(get_prisma)):
    try:
        async with prisma.tx(timeout=65000, max_wait=80000) as tx:
            session = await tx.otpsession.find_first(where={"email": request.email})
            if not session or session.otp != request.otp:
                raise HTTPException(400, "Invalid OTP")

            await tx.user.update(where={"email": request.email}, data={"hashed_password": get_password_hash(request.new_password)})
            await tx.otpsession.delete_many(where={"email": request.email, "type": "password_reset"})
            return success_response("Password reset successful")

    except HTTPException as he:
        logging.error("HTTPException: %s", he)
        raise he
    except Exception as e:
        code = getattr(e, 'code', getattr(e, 'status_code', 500))
        logging.error("Error Code: %s, Message: %s", code, str(e), exc_info=True)
        raise HTTPException(code, str(e))


@router.post("/restore-account")
async def restore_account(request: Login, prisma: Prisma = Depends(get_prisma)):
    try:
        user = await prisma.user.find_first(where={"email": request.email})
        if not user:
            raise HTTPException(404, "User not found")
        if not user.is_deleted:
            raise HTTPException(400, "Account already active")
        if not verify_password(request.password, user.hashed_password):
            raise HTTPException(400, "Incorrect password")

        await prisma.user.update(where={"id": user.id}, data={"is_deleted": False})
        token = create_access_token({"id": user.id, "email": user.email})
        return success_response("Account restored", {"access_token": token})

    except HTTPException as he:
        logging.error("HTTPException: %s", he)
        raise he
    except Exception as e:
        code = getattr(e, 'code', getattr(e, 'status_code', 500))
        logging.error("Error Code: %s, Message: %s", code, str(e), exc_info=True)
        raise HTTPException(code, str(e))


@router.post("/restore-account/google")
async def restore_account_google(request: EmailOnlyRequest, prisma: Prisma = Depends(get_prisma)):
    try:
        user = await prisma.user.find_first(where={"email": request.email})
        if not user:
            raise HTTPException(404, "User not found")
        if not user.is_deleted:
            raise HTTPException(400, "Account already active")

        await prisma.user.update(where={"id": user.id}, data={"is_deleted": False, "is_google_verified": True})
        token = create_access_token({"id": user.id, "email": user.email})
        return success_response("Account restored", {"access_token": token})

    except HTTPException as he:
        logging.error("HTTPException: %s", he)
        raise he
    except Exception as e:
        code = getattr(e, 'code', getattr(e, 'status_code', 500))
        logging.error("Error Code: %s, Message: %s", code, str(e), exc_info=True)
        raise HTTPException(code, str(e))
