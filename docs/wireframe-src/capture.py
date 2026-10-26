"""서비스(frontend/) 화면을 가짜 서버 데이터로 채워 390px 폭으로 캡처한다 → docs/wireframe-src/shots/*.png
와이어프레임 왼쪽 모바일 화면에 그대로 넣는다(서비스 화면과 똑같이 보이게).
가짜 데이터의 닉네임·글은 모두 예시이고 실제 사용자 정보는 쓰지 않는다.
실행: (frontend 폴더에서 python -m http.server 5500 을 켠 뒤)  python docs/wireframe-src/capture.py [화면이름...]
"""
import json
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

import mock_more as M
import mock_admin as A
import mock_existing as E

HERE = pathlib.Path(__file__).parent
OUT = HERE / "shots"
OUT.mkdir(exist_ok=True)
BASE = "http://localhost:5500/"
API = "http://127.0.0.1:8000"

# ------------------------------------------------------------------ 가짜 서버 데이터 (예시)
POSTS = [
    {"post_id": "p1", "category": "challenge", "title": "인증합니다", "preview": "오늘 술 안 마셨어요 다들 챌린지 파이팅!", "author_nickname": "동구리", "created_at": "2026-10-25T01:00:00", "like_count": 4, "comment_count": 3, "liked_by_me": False, "mine": False, "hidden": False, "photo_count": 0, "attach": {"kind": "fixed", "label": "절주: 마신 날도 남 2잔 · 여 1잔 이하", "days": 1}, "notice": None, "body": "오늘 술 안 마셨어요 다들 챌린지 파이팅!"},
    {"post_id": "p2", "category": "diet", "title": "국물 반만 먹기", "preview": "건더기 먼저 먹고 국물은 한 숟갈만 먹었어요", "author_nickname": "몽글이", "created_at": "2026-10-24T20:00:00", "like_count": 3, "comment_count": 2, "liked_by_me": True, "mine": False, "hidden": False, "photo_count": 0, "attach": None, "notice": None, "body": "건더기 먼저 먹고 국물은 한 숟갈만 먹었어요"},
    {"post_id": "p3", "category": "exercise", "title": "오늘 30분 걷기 완료", "preview": "퇴근길에 한 정거장 먼저 내려서 걸었어요", "author_nickname": "걷는고양이", "created_at": "2026-10-24T09:00:00", "like_count": 1, "comment_count": 0, "liked_by_me": False, "mine": False, "hidden": False, "photo_count": 0, "attach": None, "notice": None, "body": "퇴근길에 한 정거장 먼저 내려서 걸었어요"},
]
COMMENTS = [
    {"comment_id": "c1", "body": "저도 오늘 시작했어요! 같이 힘내요", "author_nickname": "몽글이", "created_at": "2026-10-25T01:10:00", "mine": False, "parent_id": None, "deleted": False, "like_count": 3, "liked_by_me": False},
    {"comment_id": "c2", "body": "응원 감사해요 :)", "author_nickname": "동구리", "created_at": "2026-10-25T01:20:00", "mine": True, "parent_id": "c1", "deleted": False, "like_count": 0, "liked_by_me": True},
    {"comment_id": "c3", "body": "화이팅이에요", "author_nickname": "걷는고양이", "created_at": "2026-10-25T01:30:00", "mine": False, "parent_id": None, "deleted": False, "like_count": 1, "liked_by_me": False},
]
EYES = [("#243749", "검정", 0), ("#6FA3D8", "파랑", 0), ("#6BB58E", "초록", 0), ("#A9794F", "갈색", 0), ("#9B87D6", "보라", 0), ("#E57373", "빨강", 10), ("#F19AB5", "분홍", 10), ("#E0B84C", "금색", 10)]


def slot(name, items):
    return {"slot": name, "items": [{"key": k, "label": l, "price": p, "owned": p == 0} for k, l, p in items]}


ITEMS = [
    slot("body", [("mongle", "몽글이", 0), ("bobo", "동글이", 0), ("rabbit", "말랑이", 0), ("cat", "뾰족이", 0), ("square", "네모", 30), ("bear", "곰돌이", 40), ("dino", "공룡이", 50), ("ghost", "유령이", 60)]),
    slot("color", [("#AACDDC", "하늘", 0), ("#81A6C6", "파랑", 0), ("#C9BEE6", "라벤더", 0), ("#F0B8C4", "분홍", 0), ("#F2C6A8", "살구", 0), ("#F5DE8F", "노랑", 0), ("#F28B82", "코랄", 20), ("#E8C14A", "골드", 40)]),
    slot("eye", EYES),
    slot("expr", [("basic", "기본", 0), ("smile", "웃음", 0), ("sleepy", "졸림", 0), ("wow", "놀람", 0), ("wink", "윙크", 0), ("cry", "눈물", 20), ("angry", "화남", 20), ("heart", "하트", 30), ("sparkle", "반짝", 40)]),
    slot("face", [("none", "없음", 0), ("glasses", "안경", 0), ("shades", "선글라스", 0), ("mask", "마스크", 0), ("whiskers", "고양이수염", 20), ("freckles", "주근깨", 20), ("mustache", "콧수염", 30), ("eyepatch", "안대", 40)]),
    slot("head", [("none", "없음", 0), ("sprout", "새싹", 0), ("crown", "왕관", 0), ("bow", "리본", 0), ("flower", "꽃", 30), ("star", "별", 40), ("halo", "천사링", 50), ("horns", "뿔", 40), ("party", "고깔", 30)]),
]
ME_CHAR = {"body": "cat", "color": "#AACDDC", "eye": "#243749", "expr": "smile", "face": "none", "head": "bow"}
PROFILE = {"nickname": "몽글이", "mine": False, "fame": 12, "fame_given_by_me": False, "post_count": 3,
           "posts": [POSTS[1]], "comments": [{"comment_id": "c1", "post_id": "p1", "post_title": "인증합니다", "body": "저도 오늘 시작했어요! 같이 힘내요", "created_at": "2026-10-25T01:10:00"}]}


CUR = ""


def mock_admin(path):
    table = [("/users/me", A.ME, True), ("/admin/challenges", A.CATALOG, True), ("/admin/users", A.USERS, False), ("/admin/stats", A.STATS, False),
             ("/admin/audit", A.AUDIT, False), ("/admin/inquiries", A.INQ, False), ("/admin/guest-inquiries", A.GUEST, False),
             ("/admin/notices", A.NOTICES, False), ("/admin/reports", A.REPORTS, False), ("/admin/community/posts", A.POSTS, False),
             ("/admin/common-challenges", A.CC, False)]
    for prefix, data, exact in table:
        if path == prefix or (not exact and path.startswith(prefix)):
            return {"data": data}
    return None


def mock_existing(path):
    if re.match(r"/challenges/cycles/[^/]+/review", path):
        return {"data": E.REVIEW}
    table = {"/challenges/cycles/current": E.CYCLE, "/challenges/cycles": E.CYCLES, "/challenges/recommendations": E.RECO,
             "/challenges/program/review": E.PROGRAM, "/challenges/participants": [], "/home/summary": E.SUMMARY, "/badges": E.BADGES,
             "/users/me": E.ME, "/users/me/consents": E.CONSENTS, "/challenges/demo": {"enabled": False, "ended": False, "ends_on": None, "has_result": False}}
    if path in table:
        return {"data": table[path]}
    return None


def mock(url, method):
    """URL(경로)과 방법으로 가짜 응답을 돌려준다. 없으면 빈 데이터."""
    path = re.sub(r"^.*/v1", "", url)
    r = (mock_existing(path) if CUR in EXIST else None) or mock_admin(path) or mock_existing(path)
    if CUR in EXIST and path == "/notices":
        return {"data": []}
    if r is not None:
        return r
    if path.startswith("/community/posts?"):
        return {"data": {"items": POSTS, "total": len(POSTS)}}
    if re.match(r"/community/posts/p\d+/comments", path):
        return {"data": COMMENTS}
    m = re.match(r"/community/posts/(p\d+)$", path)
    if m:
        return {"data": next(p for p in POSTS if p["post_id"] == m.group(1))}
    if path == "/community/me":
        return {"data": {"nickname": "동구리", "pie_gift": 0}}
    if path == "/community/attachable":
        return {"data": [{"mission_code": "ALC-1", "common_challenge_id": None, "kind": "fixed", "label": "절주: 마신 날도 남 2잔 · 여 1잔 이하", "days": 1}]}
    if path.startswith("/community/users/"):
        return {"data": PROFILE}
    if path == "/characters/items":
        return {"data": {"balance": 25, "slots": ITEMS}}
    if path == "/characters/me":
        return {"data": ME_CHAR}
    if path.startswith("/characters/by-nickname/"):
        return {"data": ME_CHAR}
    if path == "/parties/me":
        return {"data": M.PARTY_HOME}
    if path.startswith("/parties/me/posts"):
        return {"data": M.PARTY_POSTS}
    if path == "/parties/challenges":
        return {"data": [{"challenge_code": "ACT-2", "challenge_name": "빠르게 걷기 30분"}, {"challenge_code": "DIET-1", "challenge_name": "국물 반만 먹기"}, {"challenge_code": "ALC-1", "challenge_name": "절주"}]}
    if path.startswith("/pie/history"):
        return {"data": M.PIE_HISTORY}
    if re.match(r"/common-challenges/cc\d", path):
        return {"data": M.COMMON_DETAIL}
    if path.startswith("/common-challenges"):
        return {"data": {"items": [c for c in M.COMMON_LIST if f"state={c['state']}" in path] or M.COMMON_LIST, "total": 3}}
    if path == "/inquiries":
        return {"data": {"unread": 1, "items": M.INQUIRIES}}
    if path == "/push/settings":
        return {"data": M.PUSH_SETTINGS}
    if path == "/pie":
        return {"data": {"balance": 120, "recent": []}}
    if path == "/pie/thanks":
        return {"data": {"eligible": False, "claimed": True, "amount": 200}}
    if path == "/notices":
        return {"data": M.NOTICES}
    return {"data": {}}


# ------------------------------------------------------------------ 캡처할 화면: 이름 → (주소, 화면 높이, 추가 동작)
SCREENS = {
    "W13": ("feed.html", 780),
    "W14": ("write.html", 780),
    "W15": ("post.html?id=p1", 780),
    "W16": ("profile.html?nick=몽글이", 780),
    "W17": ("character.html", 780),
    "W18": ("pie.html", 780),
    "W19": ("party-home.html", 780),
    "W19-2": ("party-start.html", 780),
    "W19-3": ("party-create.html", 780),
    "W19-4": ("party-feed.html", 780),
    "W20": ("common-challenges.html", 780),
    "W20-2": ("common-challenge.html?id=cc1", 780),
    "W21": ("inquiries.html", 780),
    "W21-2": ("guest-inquiry.html", 780),
    "W21-3": ("notices.html", 780),
    "W22": ("notifications.html", 780),
    "W22-2": ("menu.html", 780),
    "W23": ("plan.html", 780),
}
# 기존 화면 W01~W12: 이름 → (주소, 높이, 로그인 여부)  — 씨앗(localStorage)은 모두 넣는다
EXIST = {
    "W01": ("index.html", 780, False), "W01-2": ("login.html", 780, False), "W02": ("signup.html", 900, False),
    "W03": ("eligibility.html", 780, True), "W04": ("health-info.html", 1500, True), "W04-2": ("survey.html", 780, True),
    "W05": ("review.html", 900, True), "W06": ("result.html", 1500, True), "W07": ("guide.html", 780, True),
    "W08": ("dashboard.html", 900, True), "W08-2": ("calendar-diary.html", 900, True), "W09": ("challenges.html", 1400, True),
    "W10": ("challenge-progress.html", 1400, True), "W11": ("trend.html", 900, True), "W11-2": ("program-review.html", 1500, True),
    "W11-3": ("reassessment.html?cycle=cy0", 900, True), "W12": ("mypage.html", 1300, True),
    "W04-form": ("health-info.html", 900, True), "W04-3": ("health-info.html", 900, True),
}
SKIP = {"W09": {"paeon-cycle", "paeon-progress"}, "W04-form": {"paeon-health", "paeon-survey", "paeon-prediction", "paeon-cycle", "paeon-progress"}}
SCREENS.update({k: v[:2] for k, v in EXIST.items()})
# 관리자: 이름 → 탭. 컴퓨터 화면이라 가로 1180
ADMIN = {"A-mission": "mission", "A-users": "users", "A-stats": "stats", "A-cc": "cc", "A-logs": "logs", "A-inq": "inquiries",
         "A-guest": "guest", "A-notices": "notices", "A-reports": "reports", "A-posts": "posts", "A-purge": "purge"}
SCREENS.update({k: ("admin.html", 760) for k in ADMIN})


def run(names):
    names = names or list(SCREENS)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for n in names:
            global CUR
            CUR = n
            url, h = SCREENS[n][:2]
            ctx = b.new_context(viewport={"width": 1180 if n in ADMIN else 390, "height": h}, device_scale_factor=2, has_touch=True)
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.clock.install(time="2026-10-25T03:00:00Z")

            def route(r):
                body = mock(r.request.url, r.request.method)
                if n == "W09" and r.request.url.endswith("/challenges/cycles/current"):
                    r.fulfill(status=404, content_type="application/json", headers={"access-control-allow-origin": "*"}, body=json.dumps({"error": {"code": "CHALLENGE_CYCLE_NOT_FOUND", "message": "x"}}))
                    return
                r.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "*", "access-control-allow-methods": "*", "access-control-allow-headers": "*"}, body=json.dumps(body))

            pg.route(API + "/**", route)
            pg.goto(BASE + "login.html")
            auth = EXIST.get(n, (0, 0, True))[2]
            pg.evaluate("() => { localStorage.clear(); }")
            if auth:
                pg.evaluate("() => { localStorage.setItem('paeon-access-token','d'); localStorage.setItem('paeon-refresh-token','d'); }")
            if n in EXIST:
                fn, items = E.seed_js(None)
                for k in SKIP.get(n, ()):
                    items.pop(k, None)
                pg.evaluate(fn, items)
            pg.goto(BASE + url)
            pg.wait_for_timeout(2200)
            if n in ADMIN and ADMIN[n] != "mission":
                pg.click(f'#tabs button[data-t="{ADMIN[n]}"]')
                pg.wait_for_timeout(1200)
            if n in EXIST and h > 780:      # 긴 화면은 내용 높이에 맞춘다(하단 탭이 맨 아래에 오도록)
                full = min(2800, pg.evaluate("document.documentElement.scrollHeight"))
                pg.set_viewport_size({"width": 390, "height": max(780, full)})
                pg.wait_for_timeout(500)
            pg.screenshot(path=str(OUT / f"{n}.png"))
            print(n, url, "오류:", errs[:1])
            ctx.close()
        b.close()


if __name__ == "__main__":
    run(sys.argv[1:])
