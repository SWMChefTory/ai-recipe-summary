import re
from uuid import uuid4
from typing import Dict
from fastapi import (
    FastAPI,
    status,
    BackgroundTasks,
    HTTPException,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Recipe Summarizer", version="1.0.0")


@app.get("/ping")
async def ping():
    return {"msg": "pong"}


# 유튜브 링크 패턴
_YT_PATTERNS = [
    re.compile(r"^https?://(www\.)?youtube\.com/watch\?v=[\w-]{11}"),
    re.compile(r"^https?://(www\.)?youtu\.be/[\w-]{11}"),
    re.compile(r"^https?://(www\.)?youtube\.com/shorts/[\w-]{11}"),
]

class SummaryRequest(BaseModel):
    video_url: str = Field(..., description="Youtube or Youtube Shorts URL")

    @field_validator("video_url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        if any(p.match(v) for p in _YT_PATTERNS):
            return v
        raise ValueError("Invalid Youtube URL")


TASKS: Dict[str, dict] = {}

async def process_summary(task_id: str, video_url: str) -> None:
    TASKS[task_id] = {
        "status": "done",
        "result": {"summary": "recipe"},
    }


@app.post("/summaries", status_code=status.HTTP_202_ACCEPTED)
async def create_summary(req: SummaryRequest, bg: BackgroundTasks):
    task_id = str(uuid4())
    TASKS[task_id] = {"status": "pending"}

    bg.add_task(process_summary, task_id, req.video_url)

    return {"task_id": task_id}


@app.get("/summaries/{task_id}")
async def get_summary(task_id: str):
    task = TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] != "done":
        return JSONResponse({"status": task["status"]}, status_code=202)
    
    return task["result"]
