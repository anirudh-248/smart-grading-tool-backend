from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode
from app.utils.success_handler import success_response
from app.db.prisma_client import get_prisma
from app.redis.redis_client import redis_handler
from typing import Optional
from app.api.v1.user.auth.routes.user import create_access_token
from env import env
import httpx, logging


router = APIRouter()


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://accounts.google.com/o/oauth2/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get("/google/login")
async def google_login():
    try:
        params = {
            "client_id": env.GOOGLE_CLIENT_ID,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": env.GOOGLE_REDIRECT_URI,
            "prompt": "select_account"
        }
        url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
        return success_response(message="Redirecting to Google login", data={"google_auth_url": url})

    except HTTPException as he:
        logging.error("HTTPException during Google login: %s", he)
        raise he

    except Exception as e:
        error_code = getattr(e, 'code', 500)
        error_code = getattr(e, 'status_code', error_code)
        logging.error("Error Code: %s, Message: %s", error_code, str(e), exc_info=True)
        raise HTTPException(
            status_code=error_code,
            detail=str(e)
        )


@router.get("/google/callback")
async def google_callback(code: Optional[str] = None, error: Optional[str] = None):
    try:
        if error or not code:
            redirect_url = f"{env.FRONT_END_RESPONSE_URI}?success=false"
            return RedirectResponse(url=redirect_url)

        data = {
            "code": code,
            "client_id": env.GOOGLE_CLIENT_ID,
            "client_secret": env.GOOGLE_CLIENT_SECRET,
            "redirect_uri": env.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(GOOGLE_TOKEN_URL, data=data)

        if response.status_code != 200:
            logging.error("Failed to retrieve token from Google. Status: %s, Response: %s", response.status_code, response.text)
            redirect_url = f"{env.FRONT_END_RESPONSE_URI}?success=false"
            return RedirectResponse(url=redirect_url)

        access_token = response.json().get("access_token")

        async with httpx.AsyncClient() as client:
            user_info_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )

        if user_info_response.status_code != 200:
            logging.error("Failed to fetch user info from Google. Status: %s, Response: %s", user_info_response.status_code, user_info_response.text)
            redirect_url = f"{env.FRONT_END_RESPONSE_URI}?success=false"
            return RedirectResponse(url=redirect_url)

        user_info = user_info_response.json()
        prisma = await get_prisma()

        user_exist = await prisma.user.find_first(where={"email": user_info['email']})

        if user_exist:
            if user_exist.is_deleted:
                redirect_url = str(env.FRONT_END_RESPONSE_URI) + '?' + str(urlencode({
                    'success': 'false',
                    'email': user_exist.email
                }))
                return RedirectResponse(url=redirect_url)

            if not user_exist.is_google_verified:
                user_exist = await prisma.user.update(
                    where={"id": user_exist.id},
                    data={"is_google_verified": True}
                )
        else:
            user_exist = await prisma.user.create(data={
                "name": user_info['name'],
                "email": user_info['email'],
                "is_email_verified": True,
                "is_google_verified": True
            })

        cache_key = f"user_info_{user_exist.id}"
        redis_client = await redis_handler.get_client()
        await redis_client.delete(cache_key)

        access_token = create_access_token(data={"email": user_exist.email, "id": user_exist.id})

        redirect_url = str(env.FRONT_END_RESPONSE_URI) + '?' + str(urlencode({
            'success': 'true',
            'access_token': access_token
        }))
        return RedirectResponse(url=redirect_url)

    except httpx.HTTPStatusError as e:
        logging.error("HTTPStatusError during Google callback: %s", e)
        redirect_url = f"{env.FRONT_END_RESPONSE_URI}?success=false"
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logging.error("Unhandled exception in Google callback: %s", e, exc_info=True)
        redirect_url = f"{env.FRONT_END_RESPONSE_URI}?success=false"
        return RedirectResponse(url=redirect_url)
