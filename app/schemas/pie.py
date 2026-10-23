from datetime import datetime

from pydantic import BaseModel


class PieEntry(BaseModel):
    reason: str           # welcome, post_write, common_challenge_rank, common_challenge_complete ...
    delta: int
    created_at: datetime
    item_key: str | None = None   # 아이템을 산 내역이면 산 아이템 (예: body:bear). 다른 내역은 None


class PieSummary(BaseModel):
    balance: int
    recent: list[PieEntry]      # 최근 5건


class PieHistory(BaseModel):
    balance: int
    total: int
    items: list[PieEntry]


class ThanksStatus(BaseModel):
    eligible: bool   # 가입 감사 파이를 받을 수 있는 사람(기간 안에 가입했고 받는 기한 안)
    claimed: bool    # 이미 받았음
    amount: int
