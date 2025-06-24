import pytest, uuid, asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app

transport = ASGITransport(app=app)

VALID_YT_URL = "https://www.youtube.com/watch?v=I3w8zAFa_G4"

@pytest.mark.asyncio
async def test_create_summary_returns_task_id():
    # Given
    payload = {"video_url": VALID_YT_URL}
    
    # When
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/summaries", json=payload)
    
    # Then
    assert resp.status_code == 202
    uuid.UUID(resp.json()["task_id"])


# YouTube 링크가 아니면 422 Unprocessable Entity가 나와야 한다.
@pytest.mark.asyncio
async def test_create_summary_rejects_non_youtube_url():
    # Given
    payload = {"video_url": "https://example.com/non_youtube"}

    # When
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/summaries", json=payload)

    # Then
    assert resp.status_code == 422


# https://youtube.com/shorts/ 형식도 허용해야 한다 (202).
@pytest.mark.asyncio
async def test_create_summary_accept_shorts_url():
    # Given
    payload = {"video_url": "https://www.youtube.com/shorts/7phQGIl5x2w"}

    # When
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/summaries", json=payload)

    # Then
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_get_summary_returns_404_for_unknown_id():
    # When
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/summaries/tmp")
    
    # Then
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_summary_return_202_when_pending():
    # Given
    payload = {"video_url": VALID_YT_URL}

    # When
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        post = await ac.post("/summaries", json=payload)
        task_id = post.json()["task_id"]

        get = await ac.get(f"/summaries/{task_id}")
        
        # Then
        assert get.status_code in (200, 202)
        if get.status_code == 202:
            assert get.json() == {"status": "pending"}
