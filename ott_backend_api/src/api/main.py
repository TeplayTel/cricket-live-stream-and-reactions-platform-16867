from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.video_stream import router as video_stream_router
from src.api.auth import router as auth_router

all_openapi_tags = [
    {
        "name": "video-stream",
        "description": "Endpoints for video stream metadata and lifecycle.",
    },
    {
        "name": "auth",
        "description": "Endpoints for user registration, login, JWT auth, and user profile.",
    },
]

app = FastAPI(
    title="OTT Backend API",
    description="Backend service for cricket match live stream, reactions, and AI endpoints.",
    version="0.1.0",
    openapi_tags=all_openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(video_stream_router)

@app.get("/")
def health_check():
    """PUBLIC_INTERFACE
    Health check endpoint for the OTT backend service.

    Returns:
        Dict[str, str]: Simple message confirming service health.
    """
    return {"message": "Healthy"}
