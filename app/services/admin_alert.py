"""운영 알림: 관리자가 빨리 봐야 하는 일을 디스코드로 알린다.

글 내용·작성자·번호 같은 개인정보는 넣지 않고 무슨 일이 있었는지만 보낸다(디스코드는 서비스 밖이라서).
웹후크 주소(ADMIN_ALERT_WEBHOOK)가 비어 있으면 아무것도 하지 않는다. 보내기는 요청과 따로(백그라운드) 돌아서
이용자 요청을 늦추지 않고, 실패해도 요청은 그대로 성공한다. 로그에도 웹후크 주소는 남기지 않는다.
"""
import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)
_pending: set[asyncio.Task] = set()   # 보내는 중인 알림 (끝나기 전에 사라지지 않게 잡아 둔다)


async def _post(text: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.post(settings.ADMIN_ALERT_WEBHOOK, json={"content": text})
        if res.status_code >= 300:
            logger.warning("운영 알림 전송 실패: HTTP %s", res.status_code)
    except Exception as e:   # 네트워크 오류 등. 주소가 담길 수 있는 오류 문구는 남기지 않는다
        logger.warning("운영 알림 전송 실패: %s", type(e).__name__)


def notify(text: str) -> None:
    """알림 하나를 백그라운드로 보낸다. 웹후크가 없으면 조용히 넘어간다."""
    if not settings.ADMIN_ALERT_WEBHOOK:
        return
    task = asyncio.get_running_loop().create_task(_post(text))
    _pending.add(task)
    task.add_done_callback(_pending.discard)
