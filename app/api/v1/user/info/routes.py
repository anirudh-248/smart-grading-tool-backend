from fastapi import APIRouter, HTTPException, Depends, status, File, UploadFile
from typing import Optional
from app.db.prisma_client import get_prisma
from app.redis.redis_client import redis_handler
from app.cloud.aws.storage import upload_file_to_s3, delete_file_from_s3
from app.utils.success_handler import success_response
from app.api.v1.user.auth.routes.user import get_current_user
from prisma import Prisma
from prisma.enums import Role
from env import env
import logging, json


router = APIRouter()


@router.get("/user", status_code=status.HTTP_200_OK)
async def get_user_info(
    prisma: Prisma = Depends(get_prisma),
    current_user=Depends(get_current_user)
):
    try:
        cache_key = f"user_info_{current_user.id}"
        redis_client = await redis_handler.get_client()
        cached_user = await redis_client.get(cache_key)

        if cached_user:
            return success_response(
                message="User information retrieved from cache",
                data=json.loads(cached_user)
            )

        user = await prisma.user.find_first(
            where={"id": current_user.id, "is_deleted": False}
        )

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_dict = user.model_dump(mode='json')
        await redis_client.setex(cache_key, 3600, json.dumps(user_dict))

        return success_response(
            message="User information retrieved successfully",
            data=user
        )

    except HTTPException as he:
        logging.error("HTTPException in get_user_info: %s", he)
        raise

    except Exception as e:
        logging.error("Unexpected error in get_user_info: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/user", status_code=status.HTTP_200_OK)
async def update_user(
    name: Optional[str] = None,
    phone_number: Optional[str] = None,
    delete_phone_number: Optional[bool] = False,
    profile_pic: Optional[UploadFile] = File(None),
    delete_profile_pic: Optional[bool] = False,
    role: Optional[Role] = None,
    profile_completion: Optional[int] = None,
    is_tutorial_req: Optional[bool] = None,
    is_email_verified: Optional[bool] = None,
    is_phone_verified: Optional[bool] = None,
    is_google_verified: Optional[bool] = None,
    prisma: Prisma = Depends(get_prisma),
    current_user=Depends(get_current_user)
):
    try:
        data = {}

        if name is not None:
            data["name"] = name
        if role is not None:
            data["role"] = role
        if profile_completion is not None:
            data["profile_completion"] = profile_completion
        if is_tutorial_req is not None:
            data["is_tutorial_req"] = is_tutorial_req
        if is_email_verified is not None:
            data["is_email_verified"] = is_email_verified
        if is_phone_verified is not None:
            data["is_phone_verified"] = is_phone_verified
        if is_google_verified is not None:
            data["is_google_verified"] = is_google_verified

        if delete_phone_number:
            data["phone_number"] = None

        if delete_profile_pic:
            await delete_file_from_s3(
                file_url=current_user.profile_pic,
                bucket_name=env.AWS_MEDIA_BUCKET
            )
            data["profile_pic"] = None

        if phone_number is not None:
            data["phone_number"] = phone_number
        
        if profile_pic:
            file_name = profile_pic.filename
            file_content = await profile_pic.read()
            file_url = await upload_file_to_s3(
                file=file_content,
                bucket_name=env.AWS_MEDIA_BUCKET,
                folder_name="user-profile-pics",
                content_type=profile_pic.content_type,
                filename=file_name
            )
            data["profile_pic"] = file_url

        async with prisma.tx(timeout=65000, max_wait=80000) as tx:
            updated_user = await tx.user.update(
                where={"id": current_user.id, "is_deleted": False},
                data=data
            )

            redis_client = await redis_handler.get_client()
            await redis_client.delete(f"user_info_{current_user.id}")

        return success_response(
            message="User updated successfully",
            data=updated_user
        )

    except HTTPException as he:
        logging.error("HTTPException in update_user: %s", he)
        raise

    except Exception as e:
        logging.error("Unexpected error in update_user: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/user", status_code=status.HTTP_200_OK)
async def delete_user(
    prisma: Prisma = Depends(get_prisma),
    current_user=Depends(get_current_user)
):
    try:
        async with prisma.tx(timeout=65000, max_wait=80000) as tx:
            await tx.user.update(
                where={"id": current_user.id},
                data={"is_deleted": True}
            )

            redis_client = await redis_handler.get_client()
            await redis_client.delete(f"user_info_{current_user.id}")

        return success_response(message="User deleted successfully")

    except HTTPException as he:
        logging.error("HTTPException in delete_user: %s", he)
        raise

    except Exception as e:
        logging.error("Unexpected error in delete_user: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
