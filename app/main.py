# app/main.py
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.admin.initialize import initialize_admin_page
from app.api.v1.endpoints import (
    auth,
    customers,
    uploads,
    merchants,
    notification,
    integrations,
    common,
)
from app.core.config import settings
from app.core.database import SessionLocal, get_db, engine


# Define a startup event to connect to the database (or other services)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for application startup and shutdown events.
    This ensures that resources like database connections are handled properly.
    """
    print("Application starting up...")

    # We'll use the environment variable 'DATABASE_URL' for the connection.
    # We check for it here to ensure it's set before proceeding.
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print(
            "DATABASE_URL environment variable is not set. The application may not function correctly."
        )

    # Optional: We can add a health check on startup to ensure the database is accessible.
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        print("Database connection successful.")
        db.close()
    except Exception as e:
        print(f"Failed to connect to the database on startup: {e}")
        # In a production environment, you might want to raise an exception here
        # to prevent the application from starting if the database is critical.

    print("Application has started.")
    yield

    # Any shutdown logic can be placed here, e.g., closing connections.
    print("Application shutting down.")


# Create the main FastAPI application instance
# We'll use the lifespan context manager for startup/shutdown events.
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="An internal API to manage product, order, and user data, serving as a Saleor workaround.",
    version=settings.VERSION,
    lifespan=lifespan,
)

initialize_admin_page(app, engine)
add_pagination(app)

# Add CORS middleware to allow requests from the frontend applications
# You will need to configure the `allow_origins` list to match the URLs
# of your storefront and merchant apps.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific origins like ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create a master API router that will group all other routers
api_router = APIRouter(prefix="/api/v1")

# Include all the individual endpoint routers
# This modular approach keeps the main file clean and organized.
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(customers.router, tags=["Customer"])
api_router.include_router(uploads.router, tags=["Uploads"])
api_router.include_router(merchants.router, tags=["Merchant"])
api_router.include_router(integrations.router, tags=["Integrations"])
api_router.include_router(notification.router, tags=["Notification"])
api_router.include_router(common.router, tags=["Common"])
# api_router.include_router(common.router, tags=["Common"])

# Add the master router to the main application
app.include_router(api_router)


# Root endpoint for a simple health check
@app.get("/", tags=["Health"])
async def read_root():
    return {"message": "Saleor Workaround API is up and running!"}


# A test endpoint that requires a database connection
@app.get("/db-test", tags=["Health"])
async def db_test(db: Session = Depends(get_db)):
    """
    Tests the database connection by executing a simple query.
    """
    try:
        db.execute(text("SELECT 1"))
        return {"message": "Database connection is live."}
    except Exception as e:
        return {"message": f"Database connection failed: {e}"}
