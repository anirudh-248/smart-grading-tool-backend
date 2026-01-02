import os
from dotenv import load_dotenv

load_dotenv()

class Environment:
    DATABASE_URL:str=os.getenv("DATABASE_URL")
    RESEND_API_KEY:str=os.getenv("SG_RESEND_API_KEY")
    JWT_SECRET_KEY:str=os.getenv("SG_JWT_SECRET_KEY")
    GOOGLE_CLIENT_ID:str=os.getenv("SG_GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET:str=os.getenv("SG_GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI:str=os.getenv("SG_GOOGLE_REDIRECT_URI")
    FRONT_END_RESPONSE_URI:str=os.getenv("SG_FRONT_END_RESPONSE_URI")
    GOOGLE_STORAGE_MEDIA_BUCKET:str=os.getenv("SG_GOOGLE_STORAGE_MEDIA_BUCKET")
    GCP_SERVICE_ACCOUNT_JSON:str=os.getenv("SG_GCP_SERVICE_ACCOUNT_JSON")
    AWS_REGION:str=os.getenv("SG_AWS_REGION")
    AWS_ACCESS_KEY_ID:str=os.getenv("SG_AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY:str=os.getenv("SG_AWS_SECRET_ACCESS_KEY")
    AWS_MEDIA_BUCKET:str=os.getenv("SG_AWS_MEDIA_BUCKET")
    REDIS_HOST:str=os.getenv("SG_REDIS_HOST")
    REDIS_PORT:str=os.getenv("SG_REDIS_PORT")
    REDIS_PASSWORD:str=os.getenv("SG_REDIS_PASSWORD")
    LOG_DIR:str=os.getenv("SG_LOG_DIR")

    @classmethod
    def to_dict(cls):
        return {key: value for key, value in cls.__dict__.items() if not key.startswith('__')}

env = Environment()