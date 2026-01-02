import uuid, logging, re, httpx, anyio, tempfile, os
import boto3
from botocore.exceptions import ClientError
from fastapi import status, HTTPException
from urllib.parse import urlparse, unquote
from typing import Optional, Tuple
from env import env


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize S3 client
s3_client = boto3.client(
    's3',
    region_name=env.AWS_REGION or 'ap-south-1',
    aws_access_key_id=env.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=env.AWS_SECRET_ACCESS_KEY
)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "webp", "svg", "mp3", "wav", "ogg", "aac"}


def is_allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


async def upload_file_to_s3(file: bytes, bucket_name: str, folder_name: Optional[str] = None, content_type: Optional[str] = None, filename: Optional[str] = None) -> str:
    try:
        unique_key = str(uuid.uuid4())
        object_key = f"{unique_key}/{filename}" if filename else unique_key
        if folder_name:
            folder_name = folder_name.strip("/")
            if not re.match(r"^[a-zA-Z0-9_\-/]+$", folder_name):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder name can only contain alphanumeric characters, hyphens, underscores, and forward slashes.")
            object_name = f"{folder_name}/{object_key}"
        else:
            object_name = object_key
        
        await anyio.to_thread.run_sync(
            lambda: s3_client.put_object(
                Bucket=bucket_name,
                Key=object_name,
                Body=file,
                ContentType=content_type or 'application/octet-stream'
            )
        )
        
        file_url = f"https://{bucket_name}.s3.amazonaws.com/{object_name}"
        return file_url
    except ClientError as e:
        logger.error("AWS S3 client error: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error uploading file to S3: {str(e)}")
    except Exception as e:
        logger.error("Error uploading file to S3: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error uploading file to S3: {str(e)}")


async def upload_image_from_url(image_url: str, bucket_name: str) -> str:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            if response.status_code != status.HTTP_200_OK:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unable to fetch image from URL")
            if not response.content:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No image content to upload")
        file_url = await upload_file_to_s3(file=response.content, bucket_name=bucket_name, content_type="image/png")
        return file_url
    except HTTPException as http_ex:
        logger.error("HTTP error while uploading image from URL: %s", http_ex)
        raise http_ex
    except Exception as e:
        logger.error("Error uploading image from URL: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error uploading image from URL: {str(e)}")


async def upload_audio_file_to_s3(file: bytes, bucket_name: str, folder_name: Optional[str] = None, content_type: Optional[str] = None) -> str:
    try:
        if content_type and not content_type.startswith("audio/"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type. Only audio files are allowed.")
        file_url = await upload_file_to_s3(file=file, bucket_name=bucket_name, folder_name=folder_name, content_type=content_type)
        return file_url
    except HTTPException as http_ex:
        logger.error("HTTP error while uploading audio file: %s", http_ex)
        raise http_ex
    except Exception as e:
        logger.error("Error uploading audio file to S3: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error uploading audio file to S3: {str(e)}")


async def delete_file_from_s3(file_url: str, bucket_name: str) -> dict:
    try:
        bucket_name, object_key = parse_s3_url(file_url)
        await anyio.to_thread.run_sync(
            lambda: s3_client.head_object(Bucket=bucket_name, Key=object_key)
        )
        await anyio.to_thread.run_sync(
            lambda: s3_client.delete_object(Bucket=bucket_name, Key=object_key)
        )
        return {"message": "File deleted successfully"}
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in S3")
        logger.error("AWS S3 client error while deleting file: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error deleting file from S3: {str(e)}")
    except HTTPException as http_ex:
        logger.error("HTTP error while deleting file from S3: %s", http_ex)
        raise http_ex
    except Exception as e:
        logger.error("Error deleting file from S3: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error deleting file from S3: {str(e)}")


def parse_s3_url(s3_url: str) -> Tuple[str, str]:
    try:
        s3_url = unquote(s3_url.split("?")[0])
        
        # Handle s3:// format
        if s3_url.startswith("s3://"):
            match = re.match(r"s3://([^/]+)/(.+)", s3_url)
            if not match:
                raise ValueError("Invalid S3 URL format")
            return match.group(1), match.group(2)
        
        # Handle https://bucket.s3.amazonaws.com/key format
        elif s3_url.startswith("https://") and ".s3" in s3_url:
            parsed_url = urlparse(s3_url)
            # Extract bucket name from hostname
            if ".s3.amazonaws.com" in parsed_url.netloc:
                bucket_name = parsed_url.netloc.split(".s3.amazonaws.com")[0]
                object_key = parsed_url.path.strip("/")
                return bucket_name, object_key
            else:
                raise ValueError("Invalid S3 URL format")
        
        # Handle https://s3.amazonaws.com/bucket/key format
        elif s3_url.startswith("https://s3"):
            parsed_url = urlparse(s3_url)
            path_parts = parsed_url.path.strip("/").split("/")
            if len(path_parts) < 2:
                raise ValueError("Invalid S3 URL format")
            return path_parts[0], "/".join(path_parts[1:])
        
        # Handle simple bucket/key format
        elif "/" in s3_url:
            parts = s3_url.strip("/").split("/")
            return parts[0], "/".join(parts[1:])
        
        else:
            raise ValueError("Invalid S3 URL format")
    except Exception as e:
        logger.error("Error parsing S3 URL '%s': %s", s3_url, str(e))
        raise ValueError(f"Error parsing S3 URL: {str(e)}")


async def fetch_file_from_s3(s3_url: str) -> str:
    try:
        bucket_name, object_key = parse_s3_url(s3_url)
        
        # Check if object exists
        await anyio.to_thread.run_sync(
            lambda: s3_client.head_object(Bucket=bucket_name, Key=object_key)
        )
        
        temp_dir = tempfile.mkdtemp()
        local_file_path = os.path.join(temp_dir, os.path.basename(object_key))
        
        await anyio.to_thread.run_sync(
            lambda: s3_client.download_file(bucket_name, object_key, local_file_path)
        )
        
        return local_file_path
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in S3")
        logger.error("AWS S3 client error: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching file from S3: {str(e)}")
    except ValueError as e:
        logger.error("Invalid S3 URL: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid S3 URL: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching file from S3: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching file from S3: {str(e)}")


async def generate_signed_url(s3_url: str, expires_in: int = 3600) -> str:
    try:
        bucket_name, object_key = parse_s3_url(s3_url)
        
        signed_url = await anyio.to_thread.run_sync(
            lambda: s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=expires_in
            )
        )
        
        return signed_url
    except ClientError as e:
        logger.error("AWS S3 client error generating signed URL: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating signed URL: {str(e)}")
    except Exception as e:
        logger.error("Error generating signed URL for %s: %s", s3_url, str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


def is_s3_url(url: str) -> bool:
    if not url or len(url) == 0:
        return False
    return "s3.amazonaws.com" in url or url.startswith("s3://")


async def generate_pdf_upload_signed_url(bucket_name: str, filename: str, expires_in: int = 900) -> Tuple[str, str]:
    try:
        if not is_allowed_file(filename) or not filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename. Only PDF files are allowed.")
        
        unique_key = str(uuid.uuid4())
        object_name = f"{unique_key}_{filename}" if filename else unique_key
        
        signed_url = await anyio.to_thread.run_sync(
            lambda: s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': object_name,
                    'ContentType': 'application/pdf'
                },
                ExpiresIn=expires_in
            )
        )
        
        return signed_url, object_name
    except ClientError as e:
        logger.error("AWS S3 client error generating PDF signed URL: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating signed URL: {str(e)}")
    except Exception as e:
        logger.error("Error generating signed URL for PDF upload: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating signed URL: {str(e)}")
