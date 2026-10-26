"""파이·파티·공통 챌린지·문의·공지·알림·12주 화면용 가짜 데이터 (예시)."""

CHAR = {"body": "cat", "color": "#AACDDC", "eye": "#243749", "expr": "smile", "face": "none", "head": "bow"}
CHAR2 = {"body": "bear", "color": "#F0B8C4", "eye": "#6FA3D8", "expr": "basic", "face": "none", "head": "none"}

PIE_HISTORY = {"balance": 120, "total": 6, "items": [
    {"reason": "thanks_first_day", "delta": 200, "created_at": "2026-10-25T01:00:00", "item_key": None},
    {"reason": "shop_buy", "delta": -10, "created_at": "2026-10-24T11:00:00", "item_key": "eye:#E57373"},
    {"reason": "challenge_daily_complete", "delta": 5, "created_at": "2026-10-24T09:00:00", "item_key": None},
    {"reason": "post_write", "delta": 2, "created_at": "2026-10-23T09:00:00", "item_key": None},
    {"reason": "welcome", "delta": 10, "created_at": "2026-10-22T09:00:00", "item_key": None},
    {"reason": "party_all_checkin", "delta": 3, "created_at": "2026-10-22T08:00:00", "item_key": None},
]}

PARTY_HOME = {
    "party": {"party_id": "pt1", "name": "아침걷기", "intro": "같이 걸어요", "invite_code": "K7M3QX", "challenge_code": "ACT-2", "challenge_name": "빠르게 걷기 30분", "started_on": "2026-10-20", "member_count": 4, "max_members": 6},
    "day_number": 6, "streak": 5, "today_all_done": False, "today_remaining": 1,
    "members": [
        {"nickname": "동구리", "character": CHAR, "is_leader": True, "is_me": True, "done_today": True, "days_total": 6, "days_done": 6},
        {"nickname": "몽글이", "character": CHAR2, "is_leader": False, "is_me": False, "done_today": True, "days_total": 6, "days_done": 5},
        {"nickname": "걷는고양이", "character": CHAR, "is_leader": False, "is_me": False, "done_today": True, "days_total": 5, "days_done": 5},
        {"nickname": "하늘이", "character": CHAR2, "is_leader": False, "is_me": False, "done_today": False, "days_total": 4, "days_done": 3},
    ],
}
PARTY_POSTS = {"total": 2, "items": [
    {"post_id": "pp1", "category": "challenge", "title": "오늘도 인증 완료", "preview": "파티원 모두 오늘 걸었어요", "author_nickname": "몽글이", "created_at": "2026-10-25T01:00:00", "like_count": 2, "comment_count": 1, "liked_by_me": False, "mine": False, "hidden": False, "photo_count": 0, "attach": {"kind": "party", "label": "아침걷기", "days": 5}, "notice": None},
    {"post_id": "pp2", "category": "tips", "title": "비 오는 날엔 실내에서", "preview": "제자리 걷기도 인증돼요", "author_nickname": "하늘이", "created_at": "2026-10-24T09:00:00", "like_count": 0, "comment_count": 0, "liked_by_me": False, "mine": False, "hidden": False, "photo_count": 0, "attach": None, "notice": None},
]}

COMMON_LIST = [
    {"challenge_id": "cc1", "title": "하루 7천 보", "proof_type": "steps", "starts_on": "2026-10-20", "ends_on": "2026-10-26", "state": "active", "participants": 12, "max_reward": 300, "joined": True, "my_rank": 2},
    {"challenge_id": "cc2", "title": "물 마시기", "proof_type": "self", "starts_on": "2026-10-27", "ends_on": "2026-11-02", "state": "upcoming", "participants": 3, "max_reward": 300, "joined": False, "my_rank": None},
    {"challenge_id": "cc3", "title": "계단 오르기", "proof_type": "self", "starts_on": "2026-10-10", "ends_on": "2026-10-16", "state": "ended", "participants": 8, "max_reward": 300, "joined": True, "my_rank": 2},
]
COMMON_DETAIL = {**COMMON_LIST[0], "target_steps": 7000, "total_days": 7, "complete_min_days": 5, "rewards": {"first": 300, "second": 200, "third": 100, "complete": 20}, "my_days": 4, "certified_today": False, "finalized": False,
                 "top": [{"rank": 1, "nickname": "몽글이", "days": 5, "is_me": False}, {"rank": 2, "nickname": "동구리", "days": 4, "is_me": True}, {"rank": 3, "nickname": "걷는고양이", "days": 4, "is_me": False}]}

INQUIRIES = [
    {"inquiry_id": "i1", "title": "알림이 안 와요", "created_at": "2026-10-24T10:00:00", "answered": True, "unread": True},
    {"inquiry_id": "i2", "title": "닉네임을 바꾸고 싶어요", "created_at": "2026-10-22T10:00:00", "answered": False, "unread": False},
]
NOTICES = [
    {"notice_id": "n1", "title": "새로운 기능이 추가됐어요 (알림·프로필·눈 색·댓글 좋아요)", "body": "PAEON에 새 기능이 생겼어요.\n- 알림을 받을 수 있어요\n- 댓글 좋아요\n- 프로필 보기\n- 캐릭터 눈 색", "starts_at": "2026-10-24T01:00:00", "ends_at": None},
    {"notice_id": "n2", "title": "알림 받는 방법 (홈 화면에 추가 + 알림 설정)", "body": "아이폰은 홈 화면에 추가해야 알림을 받을 수 있어요.", "starts_at": "2026-10-23T01:00:00", "ends_at": None},
]
PUSH_SETTINGS = {"comment": True, "inquiry": True, "party": True, "challenge": False, "breakfast": True}
