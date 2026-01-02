import uuid, logging, re, httpx, anyio.to_thread, tempfile, os, anyio, json
from google.cloud import storage
from google.oauth2 import service_account
from fastapi import status, HTTPException
from urllib.parse import urlparse, unquote
from typing import Optional, Tuple
from datetime import timedelta
from env import env


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


service_account_info = json.loads(env.GCP_SERVICE_ACCOUNT_JSON)
credentials = service_account.Credentials.from_service_account_info(service_account_info)
storage_client = storage.Client(credentials=credentials)


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "webp", "svg", "mp3", "wav", "ogg", "aac"}


def is_allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


async def upload_file_to_gcs(file: bytes, bucket_name: str, folder_name: Optional[str] = None, content_type: Optional[str] = None, filename: Optional[str] = None) -> str:
    try:
        bucket = storage_client.bucket(bucket_name)
        unique_key = str(uuid.uuid4())
        object_key = f"{unique_key}/{filename}" if filename else unique_key
        if folder_name:
            folder_name = folder_name.strip("/")
            if not re.match(r"^[a-zA-Z0-9_\-/]+$", folder_name):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder name can only contain alphanumeric characters, hyphens, underscores, and forward slashes.")
            object_name = f"{folder_name}/{object_key}"
        else:
            object_name = object_key
        blob = bucket.blob(object_name)
        await anyio.to_thread.run_sync(lambda: blob.upload_from_string(file, content_type=content_type))
        file_url = f"https://storage.googleapis.com/{bucket_name}/{object_name}"
        return file_url
    except Exception as e:
        logger.error("Error uploading file to GCS: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error uploading file to GCS: {str(e)}")


async def upload_image_from_url(image_url: str, bucket_name: str) -> str:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            if response.status_code != status.HTTP_200_OK:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unable to fetch image from URL")
            if not response.content:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No image content to upload")
        file_url = await upload_file_to_gcs(file=response.content, bucket_name=bucket_name, content_type="image/png")
        return file_url
    except HTTPException as http_ex:
        logger.error("HTTP error while uploading image from URL: %s", http_ex)
        raise http_ex
    except Exception as e:
        logger.error("Error uploading image from URL: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error uploading image from URL: {str(e)}")


async def upload_audio_file_to_gcs(file: bytes, bucket_name: str, folder_name: Optional[str] = None, content_type: Optional[str] = None) -> str:
    try:
        if content_type and not content_type.startswith("audio/"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type. Only audio files are allowed.")
        file_url = await upload_file_to_gcs(file=file, bucket_name=bucket_name, folder_name=folder_name, content_type=content_type)
        return file_url
    except HTTPException as http_ex:
        logger.error("HTTP error while uploading audio file: %s", http_ex)
        raise http_ex
    except Exception as e:
        logger.error("Error uploading audio file to GCS: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error uploading audio file to GCS: {str(e)}")


async def delete_file_from_gcs(file_url: str, bucket_name: str) -> dict:
    try:
        bucket_name, object_key = parse_gcs_url(file_url)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_key)
        exists = await anyio.to_thread.run_sync(blob.exists)
        if not exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in GCS")
        await anyio.to_thread.run_sync(blob.delete)
        return {"message": "File deleted successfully"}
    except HTTPException as http_ex:
        logger.error("HTTP error while deleting file from GCS: %s", http_ex)
        raise http_ex
    except Exception as e:
        logger.error("Error deleting file from GCS: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error deleting file from GCS: {str(e)}")


def parse_gcs_url(gcs_url: str) -> Tuple[str, str]:
    try:
        gcs_url = unquote(gcs_url.split("?")[0])
        if gcs_url.startswith("gs://"):
            match = re.match(r"gs://([^/]+)/(.+)", gcs_url)
            if not match:
                raise ValueError("Invalid GCS URL format")
            return match.group(1), match.group(2)
        elif gcs_url.startswith("https://"):
            parsed_url = urlparse(gcs_url)
            path_parts = parsed_url.path.strip("/").split("/")
            if "storage.googleapis.com" in parsed_url.netloc:
                return path_parts[0], "/".join(path_parts[1:])
            else:
                raise ValueError("Invalid GCS URL format")
        elif "/" in gcs_url:
            parts = gcs_url.strip("/").split("/")
            return parts[0], "/".join(parts[1:])
        else:
            raise ValueError("Invalid GCS URL format")
    except Exception as e:
        logger.error("Error parsing GCS URL '%s': %s", gcs_url, str(e))
        raise ValueError(f"Error parsing GCS URL: {str(e)}")


async def fetch_file_from_gcs(gcs_url: str) -> str:
    try:
        bucket_name, object_key = parse_gcs_url(gcs_url)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_key)
        exists = await anyio.to_thread.run_sync(blob.exists)
        if not exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in GCS")
        temp_dir = tempfile.mkdtemp()
        local_file_path = os.path.join(temp_dir, os.path.basename(object_key))
        await anyio.to_thread.run_sync(lambda: blob.download_to_filename(local_file_path))
        return local_file_path
    except ValueError as e:
        logger.error("Invalid GCS URL: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid GCS URL: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching file from GCS: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching file from GCS: {str(e)}")


async def generate_signed_url(gcs_url: str, expires_in: int = 3600) -> str:
    try:
        bucket_name, object_key = parse_gcs_url(gcs_url)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_key)
        signed_url = await anyio.to_thread.run_sync(lambda: blob.generate_signed_url(version="v4", expiration=expires_in, method="GET"))
        return signed_url
    except Exception as e:
        logger.error("Error generating signed URL for %s: %s", gcs_url, str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


def is_gcs_url(url: str) -> bool:
    if not url or len(url) == 0:
        return False
    return "storage.googleapis.com" in url or url.startswith("gs://")


async def generate_pdf_upload_signed_url(bucket_name: str, filename: str, expires_in: int = 900) -> Tuple[str, str]:
    try:
        if not is_allowed_file(filename) or not filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename. Only PDF files are allowed.")
        unique_key = str(uuid.uuid4())
        object_name = f"{unique_key}_{filename}" if filename else unique_key
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        signed_url = await anyio.to_thread.run_sync(lambda: blob.generate_signed_url(version="v4", expiration=timedelta(seconds=expires_in), method="PUT", content_type="application/pdf"))
        return signed_url, object_name
    except Exception as e:
        logger.error("Error generating signed URL for PDF upload: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating signed URL: {str(e)}")
