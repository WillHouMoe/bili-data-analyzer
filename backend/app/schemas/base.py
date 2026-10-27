from datetime import datetime

from pydantic import BaseModel, field_serializer

from app.core.time import as_china_time


class APIModel(BaseModel):
    @field_serializer("*", when_used="json")
    def _serialize_china_time(self, value):
        if isinstance(value, datetime):
            return as_china_time(value).isoformat(timespec="seconds")
        return value
