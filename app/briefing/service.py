import asyncio
import logging

from app.briefing.client import BriefingClient
from app.briefing.generator import BriefingGenerator
from app.briefing.schema import BriefingResponse


class BriefingService:
    def __init__(self, client: BriefingClient, generator: BriefingGenerator):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.generator = generator

    async def get(self, video_id: str) -> BriefingResponse:
        comments = await asyncio.to_thread(
            self.client.get_video_comments, video_id
        )

        return await asyncio.to_thread(
            self.generator.generate_briefing_from_comments, comments
        )