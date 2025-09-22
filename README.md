# Fast api application for [SALEOR](https://saleor.io/)
## Implements custom butique marketplace format for AIRSHOP
### How we work
1) [app](app/) directory - locates all project code
2) [app/api](app/api) directory - contains REST METHODS
3) [app/controllers](app/controllers/) directory - controllers to create db based models
4) [app/core](app/core/) - basic configuration
5) [app/graphql](app/graphql/) - client for saleor and codegen
6) [app/schemas](app/schemas/) - pydantic schemas
7) [app/services](app/services/) - services for handling external services logic

### How to use codegen 
```
ariadne-codegen client --config codegen-config.toml  
```

### How to start project
Create env file
```
# .env
POSTGRES_USER=airshop_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=airshop_db

# Replace with your actual Saleor details
SALEOR_GRAPHQL_URL=https://saleor.dev.airshop.kz/graphql/
SALEOR_API_TOKEN=1hTcgxUpr7MzBGSIqv3aNWC7wawlMQ

# Generate a strong, random key
SECRET_KEY=a_long_and_random_string_of_characters

# Redis URL for OTP and caching
REDIS_URL=redis://localhost:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/1

# S3 Storage Configuration (e.g., for MinIO or AWS S3)
# For AWS S3, you can leave S3_ENDPOINT_URL empty.
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=your_s3_access_key
S3_SECRET_ACCESS_KEY=your_s3_secret_key
S3_BUCKET_NAME=airshop-media

# SALEOR_PRESETS:
LINK_SALEOR_CHANNEL_ID="Q2hhbm5lbDoy"
LINK_SALEOR_CATEGORY_ID="Q2F0ZWdvcnk6Mg=="
LINK_SALEOR_PRODUCT_TYPE="UHJvZHVjdFR5cGU6Mg=="

# SMS Configuration:
SMS_API_URL=https://api.smstraffic.ru/multi.php
SMS_API_LOGIN=airshop
SMS_API_PASSWORD=viZz94uY
SMS_API_PHONE_CODE=8


FREEDOM_MFO_APPLY_URL="https://back-preprod.ffin.credit/ffc-api-public/universal/apply/apply-lead"
FREEDOM_MFO_SEND_OTP_URL="https://back-preprod.ffin.credit/ffc-api-public/universal/general/send-otp"
FREEDOM_MFO_VALIDATE_OTP_URL="https://back-preprod.ffin.credit/ffc-api-public/universal/general/validate-otp”"

# PUSH Configuration:
PUSH_CATEGORY=shop
PUSH_API_KEY=10891ad8-06a8-437f-a788-9d0c4310a338
PUSH_API_URL="https://ibul.trafficwave.kz/producer/notification/write"
PUSH_API_KEY_HEADER=X-API-KEY
PUSH_TIMEOUT_SEC=5.0
```

Run
``` 
docker compose up -d 
```
