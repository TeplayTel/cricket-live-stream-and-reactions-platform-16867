from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Literal
from fastapi.security import OAuth2PasswordBearer

# == OAuth2PasswordBearer is used for stub authentication check
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Tags for OpenAPI grouping
openapi_tags = [
    {
        "name": "video-stream",
        "description": "Endpoints for video stream metadata and lifecycle."
    }
]

# PUBLIC_INTERFACE
class StreamMetadata(BaseModel):
    """Model representing metadata for a live video stream."""
    stream_id: str = Field(..., description="Unique identifier for the video stream")
    title: str = Field(..., description="Title of the cricket match stream")
    description: Optional[str] = Field(None, description="Description of the stream")
    is_live: bool = Field(..., description="Whether the stream is currently live")
    stream_url: str = Field(..., description="The video source URL (or HLS/DASH manifest)")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail image URL for the stream")
    current_viewers: int = Field(..., description="Number of concurrent viewers (approximate)")

# PUBLIC_INTERFACE
class StreamLifecycleInfo(BaseModel):
    """Basic lifecycle responses for stream status queries."""
    stream_id: str = Field(..., description="ID of the queried stream")
    status: Literal["not_started", "live", "ended"] = Field(..., description="Lifecycle status of the stream")
    started_at: Optional[str] = Field(None, description="UTC time when stream started (ISO8601)")
    ended_at: Optional[str] = Field(None, description="UTC time when stream ended (ISO8601)")

router = APIRouter(tags=["video-stream"])

# Stub token authentication (replace with real logic or use Security for production)
async def fake_verify_token(token: str = Depends(oauth2_scheme)):
    if not token or token != "testtoken":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"user_id": "demo-user"}


# PUBLIC_INTERFACE
@router.get(
    "/stream/{stream_id}",
    summary="Get live cricket match video stream metadata",
    description="Returns metadata and stream URL for the requested cricket match stream.",
    response_model=StreamMetadata,
    responses={
        200: {"description": "Stream metadata and access info"},
        401: {"description": "Authentication required"},
        404: {"description": "Stream not found"}
    },
)
async def get_stream_metadata(
    stream_id: str,
    user=Depends(fake_verify_token)
):
    """Returns video stream metadata and the (stub) streaming URL for a requested stream ID."""
    # Stub response
    if stream_id != "cric001":
        raise HTTPException(status_code=404, detail="Stream not found")
    return StreamMetadata(
        stream_id="cric001",
        title="India vs Australia - Test Match Live",
        description="Watch the thrilling India vs Australia Test match live!",
        is_live=True,
        stream_url="https://www.example.com/streams/cric001/master.m3u8",
        thumbnail_url="https://www.example.com/streams/cric001/thumbnail.jpg",
        current_viewers=4286
    )


# PUBLIC_INTERFACE
@router.get(
    "/stream/{stream_id}/lifecycle",
    summary="Get stream lifecycle information",
    description="Checks status (not_started/live/ended) and timings for specific stream.",
    response_model=StreamLifecycleInfo,
    responses={
        200: {"description": "Stream lifecycle details"},
        401: {"description": "Authentication required"},
        404: {"description": "Stream not found"}
    },
)
async def get_stream_lifecycle(
    stream_id: str,
    user=Depends(fake_verify_token)
):
    """Provides stubbed basic lifecycle (status/timeline) info for a video stream."""
    if stream_id != "cric001":
        raise HTTPException(status_code=404, detail="Stream not found")
    return StreamLifecycleInfo(
        stream_id="cric001",
        status="live",
        started_at="2024-07-02T09:00:00Z",
        ended_at=None
    )
