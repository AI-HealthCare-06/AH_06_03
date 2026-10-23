"""웹 푸시: 구독 등록·해제, 종류별 설정, 발송.
발송은 원래 요청(댓글 저장 등)이 commit된 뒤에 부르고, 실패해도 원래 요청은 성공으로 둔다(오류는 로그만).
알림에는 문의·댓글 내용을 넣지 않는다(잠금 화면 노출 방지)."""
import asyncio
import json
import logging
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import utcnow
from app.models.push import PushSetting, PushSubscription
from app.schemas.push import PushSettings

log = logging.getLogger(__name__)
KINDS = ("comment", "inquiry", "party", "challenge", "breakfast")


@dataclass
class SendResult:
    """한 사람에게 보낸 결과 (기기 수). sent가 1 이상이면 받은 것으로 본다."""
    sent: int = 0      # 보낸 기기
    gone: int = 0      # 만료돼서 지운 구독
    failed: int = 0    # 그 밖의 이유로 실패한 기기


# ---------------------------------------------------------------- 구독
async def subscribe(db: AsyncSession, user_id: str, endpoint: str, p256dh: str, auth: str) -> None:
    """같은 기기(endpoint)가 다시 등록하면 갱신한다. 다른 사람이 같은 기기로 등록하면 그 사람으로 넘어간다."""
    sub = (await db.execute(select(PushSubscription).where(PushSubscription.endpoint == endpoint))).scalar_one_or_none()
    if sub is None:
        db.add(PushSubscription(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth, created_at=utcnow()))
    else:
        sub.user_id, sub.p256dh, sub.auth = user_id, p256dh, auth
    await db.commit()


async def unsubscribe(db: AsyncSession, user_id: str, endpoint: str) -> None:
    """내 기기만 해제한다 (남의 구독이거나 없으면 아무 일도 없음)."""
    await db.execute(delete(PushSubscription).where(
        PushSubscription.endpoint == endpoint, PushSubscription.user_id == user_id))
    await db.commit()


# ---------------------------------------------------------------- 설정
async def get_settings(db: AsyncSession, user_id: str) -> PushSettings:
    row = await db.get(PushSetting, user_id)
    return PushSettings(**{k: getattr(row, k) for k in KINDS}) if row else PushSettings()


async def update_settings(db: AsyncSession, user_id: str, changes: dict) -> PushSettings:
    row = await db.get(PushSetting, user_id)
    if row is None:
        row = PushSetting(user_id=user_id, **PushSettings().model_dump(), updated_at=utcnow())
        db.add(row)
    for k, v in changes.items():
        if k in KINDS and v is not None:
            setattr(row, k, v)
    row.updated_at = utcnow()
    await db.commit()
    return PushSettings(**{k: getattr(row, k) for k in KINDS})


# ---------------------------------------------------------------- 발송
def _webpush(sub: PushSubscription, payload: str) -> None:
    from pywebpush import webpush   # 시험·개발 환경에서는 VAPID가 없어 여기까지 오지 않는다
    webpush(
        subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
        data=payload,
        vapid_private_key=settings.VAPID_PRIVATE_KEY,
        vapid_claims={"sub": settings.VAPID_SUBJECT},
        ttl=60 * 60 * 12,
    )


async def send(db: AsyncSession, user_id: str, kind: str, title: str, body: str, url: str) -> SendResult:
    """한 사람의 모든 기기로 알림을 보낸다 (kind는 설정 이름: comment / inquiry / party / challenge / breakfast).
    내용은 {title, body, url}만 보낸다. VAPID 키가 없거나 그 종류를 꺼 뒀으면 보내지 않는다.
    만료된 구독(404·410)은 지운다. 오류로 멈추지 않는다(원래 요청은 그대로 성공)."""
    result = SendResult()
    if not settings.VAPID_PRIVATE_KEY:
        return result
    try:
        if not getattr(await get_settings(db, user_id), kind):
            return result
        subs = (await db.execute(select(PushSubscription).where(PushSubscription.user_id == user_id))).scalars().all()
        payload = json.dumps({"title": title, "body": body, "url": url}, ensure_ascii=False)
        gone = []
        for sub in subs:
            try:
                await asyncio.to_thread(_webpush, sub, payload)   # pywebpush는 동기라 이벤트 루프를 막지 않게
                result.sent += 1
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status in (404, 410):
                    gone.append(sub.push_subscription_id)          # 기기에서 알림을 끄거나 앱을 지운 경우
                else:
                    result.failed += 1
                    log.warning("푸시 발송 실패 (%s): %s", kind, status or type(e).__name__)
        if gone:
            await db.execute(delete(PushSubscription).where(PushSubscription.push_subscription_id.in_(gone)))
            await db.commit()
            result.gone = len(gone)
        return result
    except Exception:
        log.exception("푸시 발송 중 오류 (%s)", kind)
        result.failed += 1
        return result