from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class AIConversation(Base):
    __tablename__ = "ai_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(Integer, nullable=True)
    query_id = Column(Integer, ForeignKey("queries.id", ondelete="CASCADE"), nullable=True)
    bvid = Column(Text, ForeignKey("videos.bvid", ondelete="CASCADE"), nullable=True)
    preset = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    messages = relationship(
        "AIMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AIMessage.created_at",
    )


class AIMessage(Base):
    __tablename__ = "ai_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(Text, nullable=False)  # system | user | assistant | tool
    content = Column(Text, nullable=True)
    tool_calls = Column(Text, nullable=True)  # JSON serialized
    tool_call_id = Column(Text, nullable=True)
    name = Column(Text, nullable=True)  # function name for role="tool"
    created_at = Column(DateTime, default=func.now())

    conversation = relationship("AIConversation", back_populates="messages")
