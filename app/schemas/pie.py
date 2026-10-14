from datetime import datetime

from pydantic import BaseModel


class PieEntry(BaseModel):
    reason: str           # welcome, post_write, common_challenge_rank, common_challenge_complete ...
    delta: int
    created_at: datetime


class PieSummary(BaseModel):
    balance: int
    recent: list[PieEntry]      # 최근 5건


class PieHistory(BaseModel):
    balance: int
    total: int
    items: list[PieEntry]
