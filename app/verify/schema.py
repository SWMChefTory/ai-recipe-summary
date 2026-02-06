from pydantic import BaseModel, Field

class VerificationRequest(BaseModel):
    video_id: str = Field(..., description="YouTube 영상 ID")

class VerificationResponse(BaseModel):
    file_uri: str = Field(..., description="Gemini File URI")
    mime_type: str = Field(..., description="MIME Type")

class CleanupResponse(BaseModel):
    message: str = Field(..., description="결과 메시지 (success)")
