from pydantic import BaseModel, Field, HttpUrl


class YouTubeTranscriptRequest(BaseModel):
    youtube_url: HttpUrl = Field(description='Public YouTube video URL.')
