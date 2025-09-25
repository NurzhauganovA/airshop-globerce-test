import os
from pydantic import Field
from typing import Optional
from pydantic_settings import BaseSettings  # Correct import for Pydantic v2
from dotenv import load_dotenv

# Load environment variables from the .env file.
# This ensures that settings can be managed outside the codebase.
load_dotenv()


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Pydantic's BaseSettings handles type validation automatically.
    """

    # Project Info
    PROJECT_NAME: str = "Saleor Workaround API"
    VERSION: str = "1.0.0"

    # Database Configuration
    # We use Field(...) to indicate that these are required variables.
    DATABASE_URL: str = Field(
        ..., env="DATABASE_URL", description="URL for the application database."
    )

    # New fields to handle Postgres variables passed by Docker Compose
    POSTGRES_USER: str = Field(..., env="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(..., env="POSTGRES_PASSWORD")
    POSTGRES_DB: str = Field(..., env="POSTGRES_DB")

    # Saleor API Configuration
    SALEOR_GRAPHQL_URL: str = Field(
        ..., env="SALEOR_GRAPHQL_URL", description="URL for the Saleor GraphQL API."
    )
    SALEOR_API_TOKEN: str = Field(
        ..., env="SALEOR_API_TOKEN", description="API token for Saleor authentication."
    )

    # Optional: Authentication settings
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "a_very_secret_key_that_should_be_replaced"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Redis Configuration for OTP storage
    REDIS_URL: str = Field(
        "redis://redis:6379/0", env="REDIS_URL", description="URL for Redis."
    )

    # Celery Configuration
    CELERY_BROKER_URL: str = Field(
        "redis://redis:6379/1",
        env="CELERY_BROKER_URL",
        description="URL for Celery message broker.",
    )

    # S3 Storage Configuration
    S3_ENDPOINT_URL: Optional[str] = Field(
        None,
        env="S3_ENDPOINT_URL",
        description="URL for S3-compatible storage like MinIO. Leave empty for AWS S3.",
    )
    S3_ACCESS_KEY_ID: str = Field(..., env="S3_ACCESS_KEY_ID")
    S3_SECRET_ACCESS_KEY: str = Field(..., env="S3_SECRET_ACCESS_KEY")
    S3_BUCKET_NAME: str = Field(..., env="S3_BUCKET_NAME")

    LINK_SALEOR_CHANNEL_ID: str = Field(..., env="LINK_SALEOR_CHANNEL_ID")
    LINK_SALEOR_CATEGORY_ID: str = Field(..., env="LINK_SALEOR_CATEGORY_ID")
    LINK_SALEOR_PRODUCT_TYPE: str = Field(..., env="LINK_SALEOR_PRODUCT_TYPE")

    LINK_FRONT_URL: str = Field(..., env="LINK_FRONT_URL")
    LINK_PATH_PREFIX: str = Field(..., env="LINK_PATH_PREFIX")

    MOCK_OTP: bool = Field(..., env="MOCK_OTP")
    DEFAULT_OTP: str = Field(..., env="DEFAULT_OTP")

    MERCHANT_PRODUCT_TYPE: str = Field(..., env="MERCHANT_PRODUCT_TYPE")

    SALEOR_DEFAULT_WAREHOUSE_SHIPPING_ZONE: str = Field(
        ..., env="SALEOR_DEFAULT_WAREHOUSE_SHIPPING_ZONE"
    )

    IMAGE_PROCESSING_URL: str = Field(..., env="IMAGE_PROCESSING_URL")

    # SMS Configuration:
    SMS_API_URL: str = Field(..., env="SMS_API_URL")
    SMS_API_LOGIN: str = Field(..., env="SMS_API_LOGIN")
    SMS_API_PASSWORD: str = Field(..., env="SMS_API_PASSWORD")
    SMS_API_PHONE_CODE: str = Field(..., env="SMS_API_PHONE_CODE")

    FREEDOM_PAY_PRIVATE_KEY_PEM_PATH: str = Field(
        ..., env="FREEDOM_PAY_PRIVATE_KEY_PEM_PATH"
    )
    FREEDOM_PAY_TEST_MODE: bool = Field(..., env="FREEDOM_PAY_TEST_MODE")
    FREEDOM_PAY_INIT_PAY: str = Field(..., env="FREEDOM_PAY_INIT_PAY")
    FREEDOM_PAY_HOST: str = Field(..., env="FREEDOM_PAY_HOST")
    FREEDOM_PAY_TERMINAL_REGISTRATION_URI: str = Field(
        ..., env="FREEDOM_PAY_TERMINAL_REGISTRATION_URI"
    )
    FREEDOM_PAY_TERMINAL_REGISTRATION_TOKEN: str = Field(
        ..., env="FREEDOM_PAY_TERMINAL_REGISTRATION_TOKEN"
    )
    FREEDOM_PAY_STATUS: str = Field(..., env="FREEDOM_PAY_STATUS")

    FREEDOM_MFO_HOST: str = Field(..., env="FREEDOM_MFO_HOST")
    FREEDOM_MFO_REGISTRATION_URL: str = Field(..., env="FREEDOM_MFO_REGISTRATION_URL")
    FREEDOM_MFO_PERIOD_URL: str = Field(..., env="FREEDOM_MFO_PERIOD_URL")
    FREEDOM_MFO_ACCOUNT_ORGANIZATION: str = Field(
        ..., env="FREEDOM_MFO_ACCOUNT_ORGANIZATION"
    )
    FREEDOM_MFO_ACCOUNT_BIK: str = Field(..., env="FREEDOM_MFO_ACCOUNT_BIK")
    FREEDOM_MFO_KBE: str = Field(..., env="FREEDOM_MFO_KBE")
    FREEDOM_MFO_ENTERPRISE_TYPE: str = Field(..., env="FREEDOM_MFO_ENTERPRISE_TYPE")
    FREEDOM_MFO_CONTRACT_CODE: str = Field(..., env="FREEDOM_MFO_CONTRACT_CODE")

    # IBCC CAS USAGE
    IBCC_AUTH_URL: str = Field(..., env="IBCC_AUTH_URL")
    IBCC_AUTH_CLIENT_ID: str = Field(..., env="IBCC_AUTH_CLIENT_ID")
    IBCC_AUTH_CLIENT_SECRET: str = Field(..., env="IBCC_AUTH_CLIENT_SECRET")
    IBCC_USER_AUTH_URL: str = Field(..., env="IBCC_USER_AUTH_URL")
    IBCC_USER_DEVICE_ID: str = Field(..., env="IBCC_USER_DEVICE_ID")

    BASE_HOST: str = Field(..., env="BASE_HOST")

    FREEDOM_MFO_APPLY_URL: str = Field(..., env="FREEDOM_MFO_APPLY_URL")
    FREEDOM_MFO_SEND_OTP_URL: str = Field(..., env="FREEDOM_MFO_SEND_OTP_URL")
    FREEDOM_MFO_VALIDATE_OTP_URL: str = Field(..., env="FREEDOM_MFO_VALIDATE_OTP_URL")

    FREEDOM_MFO_AUTH_URL: str = Field(..., env="FREEDOM_MFO_AUTH_URL")
    FREEDOM_MFO_USERNAME: str = Field(..., env="FREEDOM_MFO_USERNAME")
    FREEDOM_MFO_PASSWORD: str = Field(..., env="FREEDOM_MFO_PASSWORD")

    FREEDOM_MFO_CHANNEL: str = Field(..., env="FREEDOM_MFO_CHANNEL")
    FREEDOM_MFO_GET_STATUS: str = Field(..., env="FREEDOM_MFO_GET_STATUS")
    FREEDOM_MFO_SET_OFFER_URL: str = Field(..., env="FREEDOM_MFO_SET_OFFER_URL")

    # PUSH Configuration:
    PUSH_CATEGORY: str = Field(..., env="PUSH_CATEGORY")
    PUSH_API_KEY: str = Field(..., env="PUSH_API_KEY")
    PUSH_API_URL: str = Field(..., env="PUSH_API_URL")
    PUSH_API_KEY_HEADER: str = Field(..., env="PUSH_API_KEY_HEADER")
    PUSH_TIMEOUT_SEC: float = Field(..., env="PUSH_TIMEOUT_SEC")

    AIRLINK_PROLONG_DAYS: int = Field(default=14, env="AIRLINK_PROLONG_DAYS")

    FREEDOM_P2P_INIT_PAYMENT_TOKEN: str = Field(..., env="FREEDOM_P2P_INIT_PAYMENT_TOKEN")
    FREEDOM_P2P_CONFIRM_PAYMENT_TOKEN: str = Field(..., env="FREEDOM_P2P_CONFIRM_PAYMENT_TOKEN")
    FREEDOM_P2P_BASE_URL: str = Field(..., env="FREEDOM_P2P_BASE_URL")
    FREEDOM_P2P_INIT_PAYMENT_URL: str = Field(..., env="FREEDOM_P2P_INIT_PAYMENT_URL")
    FREEDOM_P2P_CONFIRM_PAYMENT_URL: str = Field(..., env="FREEDOM_P2P_CONFIRM_PAYMENT_URL")

    class Config:
        """
        Configuration for Pydantic's BaseSettings.
        """

        # This tells Pydantic to look for environment variables
        # when a field is not provided.
        env_file = ".env"
        # Using case-sensitive keys as a best practice
        case_sensitive = True


# Instantiate the settings object to be used throughout the application.
settings = Settings()
