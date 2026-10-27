from datetime import datetime

from app.schemas.base import APIModel


class CreateConversationRequest(APIModel):
    preset: str  # "overall_analysis" | "topic_inspiration" | "video_analysis" | "free_chat"
    content: str | None = None  # user-provided first message (required for free_chat)


class SendMessageRequest(APIModel):
    content: str


class ToolCallInfo(APIModel):
    name: str
    arguments: dict = {}
    result: str | None = None


class MessageResponse(APIModel):
    id: int
    role: str  # "user" | "assistant"
    content: str | None
    tool_calls: list[ToolCallInfo] | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationSummary(APIModel):
    id: int
    preset: str
    title: str | None
    created_at: datetime
    updated_at: datetime | None
    message_count: int = 0

    class Config:
        from_attributes = True


class ConversationDetail(APIModel):
    id: int
    preset: str
    title: str | None
    uid: int | None
    query_id: int | None
    bvid: str | None
    messages: list[MessageResponse]

    class Config:
        from_attributes = True
