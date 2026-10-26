"""PAEON 와이어프레임 v6 생성기.
화면 정의는 screens_*.py 에 모아 두고, 이 파일이 같은 양식(왼쪽 모바일 390px 프레임 / 오른쪽 설명)으로 HTML을 만든다.
관리자 화면은 컴퓨터에서 쓰는 화면이라 왼쪽 프레임을 넓게(720px) 그린다.
실행: python docs/wireframe-src/build.py  →  docs/PAEON_와이어프레임_v6.html
"""
import html
import importlib
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

OUT = HERE.parent / "PAEON_와이어프레임_v6.html"

CSS = """
:root{--blue:#5C86AC; --blue-l:#E4F0F5; --cream:#F8F1E7; --line:#E6DBCD; --ink:#243749; --muted:#6B7A88; --mid:#B8C4CE; --soft:#EEF1F4; --risk:#C0392B; --ok:#2E7D5B}
*{box-sizing:border-box}
body{margin:0; background:#F4F1EC; color:var(--ink); font-family:'Noto Sans KR','Malgun Gothic','Apple SD Gothic Neo',sans-serif; line-height:1.6; padding-bottom:90px}
h1,h2,h3{margin:0}
.picker{position:sticky; top:0; z-index:50; background:rgba(255,255,255,.96); backdrop-filter:blur(6px); border-bottom:1px solid var(--line); padding:12px 20px; display:flex; gap:6px; flex-wrap:wrap; align-items:center}
.picker .brand{font-weight:900; font-size:17px; margin-right:10px; color:var(--blue)}
.picker a{font-size:12px; text-decoration:none; color:var(--muted); border:1px solid var(--line); border-radius:999px; padding:4px 10px; background:#fff}
.picker a:hover{background:var(--blue); color:#fff; border-color:var(--blue)}
.intro{max-width:1180px; margin:34px auto 6px; padding:0 24px}
.intro h1{font-size:26px}
.intro p{color:var(--muted); font-size:14px; margin:8px 0 0}
.sect{max-width:1180px; margin:54px auto 0; padding:0 24px}
.sect h2{font-size:20px; padding-bottom:8px; border-bottom:2px solid var(--blue)}
.sect p{color:var(--muted); font-size:13.5px; margin:8px 0 0}
.row{max-width:1180px; margin:28px auto; padding:0 24px; display:grid; grid-template-columns:420px 1fr; gap:36px; align-items:start; scroll-margin-top:70px}
.row.wide{grid-template-columns:760px 1fr}
.side .tag{display:flex; align-items:center; gap:10px; flex-wrap:wrap}
.side .id{background:var(--blue); color:#fff; font-weight:800; font-size:13px; padding:3px 12px; border-radius:999px}
.side .name{font-size:19px; font-weight:800}
.side .flow{margin:8px 0 0; color:var(--muted); font-size:13.5px}
.side .req{margin:6px 0 0; color:#8C6A4F; font-size:12.5px}
.side h4{margin:18px 0 6px; font-size:13px; color:var(--blue); letter-spacing:.3px}
.side ul{margin:0; padding-left:18px; font-size:13.5px}
.side li{margin:3px 0}
.side .st{display:grid; grid-template-columns:auto 1fr; gap:4px 12px; font-size:13px}
.side .st b{color:var(--ink)}
.side .src{margin-top:14px; font-size:12px; color:var(--muted)}
.side .flagged{display:inline-block; margin-left:6px; font-size:11px; font-weight:700; color:#8C6A4F; background:#FFF3DD; border-radius:999px; padding:1px 8px}
/* ---- 모바일 프레임 ---- */
.phone{width:390px; margin:0 auto; background:#fff; border:10px solid #2A3744; border-radius:36px; box-shadow:0 10px 30px rgba(36,55,73,.18); overflow:hidden}
.phone.shot{border-width:10px; background:#fff}
.phone.shot img{display:block; width:100%; height:auto}
.phone .scr{height:760px; display:flex; flex-direction:column; position:relative}
.phone .bar{height:44px; flex:none; display:flex; align-items:center; justify-content:space-between; padding:0 16px; border-bottom:1px solid var(--line); font-size:14px; font-weight:800}
.phone .bar .r{display:flex; gap:8px; font-weight:600; font-size:12px; color:var(--muted)}
.phone .bd{flex:1; overflow:hidden; padding:14px 16px; display:flex; flex-direction:column; gap:10px}
.phone .tabs{height:54px; flex:none; border-top:1px solid var(--line); display:flex; font-size:11px; color:var(--muted)}
.phone .tabs div{flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px}
.phone .tabs div.on{color:var(--ink); font-weight:800}
.phone .tabs i{width:18px; height:18px; border-radius:5px; border:1.6px solid currentColor; display:block}
/* ---- 와이어 부품 ---- */
.bx{border:1.5px solid var(--mid); border-radius:12px; padding:10px 12px; font-size:12.5px; background:#fff}
.bx.fill{background:var(--soft); border-color:var(--soft)}
.bx.cream{background:var(--cream); border-color:var(--cream)}
.bx.blue{background:var(--blue-l); border-color:var(--blue-l)}
.bx.dash{border-style:dashed}
.t{font-weight:800; font-size:13.5px}
.m{color:var(--muted); font-size:12px}
.ln{height:9px; border-radius:5px; background:var(--soft); margin:5px 0}
.ln.s{width:60%} .ln.m2{width:80%}
.btn{display:flex; align-items:center; justify-content:center; height:40px; border-radius:999px; background:var(--blue); color:#fff; font-weight:800; font-size:13px}
.btn.g{background:#fff; color:var(--ink); border:1.5px solid var(--mid)}
.btn.sm{height:30px; font-size:12px; padding:0 14px; display:inline-flex}
.chip{display:inline-flex; align-items:center; height:24px; padding:0 10px; border:1.5px solid var(--mid); border-radius:999px; font-size:11.5px; background:#fff}
.chip.on{background:var(--blue); border-color:var(--blue); color:#fff}
.chips{display:flex; gap:6px; flex-wrap:wrap}
.av{width:36px; height:36px; border-radius:11px; background:var(--cream); border:1.5px solid var(--line); display:inline-flex; align-items:center; justify-content:center; font-size:15px; flex:none}
.av.lg{width:76px; height:76px; border-radius:22px; font-size:30px}
.flex{display:flex; align-items:center; gap:8px}
.between{display:flex; align-items:center; justify-content:space-between; gap:8px}
.col{display:flex; flex-direction:column; gap:8px}
.grid2{display:grid; grid-template-columns:1fr 1fr; gap:8px}
.grid3{display:grid; grid-template-columns:repeat(3,1fr); gap:8px}
.grid4{display:grid; grid-template-columns:repeat(4,1fr); gap:8px}
.heart{color:#E5484D}
.fab{position:absolute; right:14px; bottom:66px; height:40px; padding:0 16px; border-radius:999px; background:var(--blue); color:#fff; font-weight:800; font-size:13px; display:flex; align-items:center}
.sw{width:26px; height:26px; border-radius:50%; border:1.5px solid var(--mid)}
.sw.on{outline:2px solid var(--ink); outline-offset:2px}
.sheet{position:absolute; left:0; right:0; bottom:0; background:#fff; border-top:2px solid var(--blue); border-radius:18px 18px 0 0; padding:14px 16px; box-shadow:0 -6px 18px rgba(0,0,0,.12)}
.dim{position:absolute; inset:0; background:rgba(36,55,73,.35)}
.note{font-size:11.5px; color:var(--blue); font-weight:700}
/* ---- 관리자(넓은 프레임) ---- */
.desk{background:#fff; border:10px solid #2A3744; border-radius:14px; box-shadow:0 10px 30px rgba(36,55,73,.18); overflow:hidden}
.desk .top{height:40px; background:var(--cream); display:flex; align-items:center; padding:0 14px; font-weight:800; font-size:13px; justify-content:space-between; border-bottom:1px solid var(--line)}
.desk .lay{display:grid; grid-template-columns:150px 1fr; min-height:560px}
.desk .menu{border-right:1px solid var(--line); padding:10px; display:flex; flex-direction:column; gap:4px; font-size:12px; background:#FBF9F6}
.desk .menu div{padding:6px 10px; border-radius:8px}
.desk .menu div.on{background:var(--blue-l); font-weight:800}
.desk .main{padding:14px; display:flex; flex-direction:column; gap:10px; font-size:12px}
.tb{width:100%; border-collapse:collapse; font-size:12px}
.tb th{background:var(--soft); text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); font-size:11.5px}
.tb td{padding:6px 8px; border-bottom:1px solid var(--line)}
.stat{display:grid; grid-template-columns:repeat(4,1fr); gap:8px}
.stat .bx{text-align:center}
.stat b{font-size:20px; display:block}
@media (max-width:1100px){.row,.row.wide{grid-template-columns:1fr}}
"""


def esc(t):
    return html.escape(str(t), quote=False)


def deskshot(*names):
    """관리자(컴퓨터) 화면 캡처 여러 장을 세로로 쌓는다."""
    import base64
    out = []
    for n in names:
        f = HERE / "shots" / f"{n}.png"
        if not f.exists():
            out.append('<div class="bx dash m">캡처 없음: ' + esc(n) + "</div>")
            continue
        out.append(f'<img src="data:image/png;base64,{base64.b64encode(f.read_bytes()).decode()}" alt="{esc(n)} 서비스 화면" style="width:100%;display:block;border:1px solid var(--line);border-radius:10px;margin-bottom:12px">')
    return '<div class="deskshot">' + "".join(out) + "</div>"


def shot(name):
    """서비스 화면 캡처(docs/wireframe-src/shots/{name}.png)를 모바일 프레임에 넣는다. 이미지는 문서 안에 포함한다."""
    import base64
    f = HERE / "shots" / f"{name}.png"
    if not f.exists():
        return phone('<div class="bx dash m" style="margin:auto;text-align:center">캡처 없음: ' + esc(name) + "</div>")
    b64 = base64.b64encode(f.read_bytes()).decode()
    return f'<div class="phone shot"><img src="data:image/png;base64,{b64}" alt="{esc(name)} 서비스 화면" width="390"></div>'


def phone(body, title="PAEON", right="", tab=None, extra=""):
    """모바일 프레임. tab: 하단 탭에서 켤 곳(0~4) 또는 None(탭 없음)."""
    tabs = ""
    if tab is not None:
        names = ["내 변화", "챌린지", "홈", "커뮤니티", "더보기"]
        tabs = '<div class="tabs">' + "".join(f'<div class="{"on" if i == tab else ""}"><i></i>{n}</div>' for i, n in enumerate(names)) + "</div>"
    return f'<div class="phone"><div class="scr"><div class="bar"><span>{title}</span><span class="r">{right}</span></div><div class="bd">{body}</div>{extra}{tabs}</div></div>'


def desk(menu_on, body, title="PAEON 관리자"):
    items = ["가입자", "챌린지 통계", "공통 챌린지", "열람 기록", "문의", "비회원 문의", "공지", "신고", "글 관리", "테스트 계정 삭제"]
    menu = "".join(f'<div class="{"on" if n == menu_on else ""}">{n}</div>' for n in items)
    return f'<div class="desk"><div class="top"><span>{title}</span><span class="m">관리자 로그인 중 · 로그아웃</span></div><div class="lay"><div class="menu">{menu}</div><div class="main">{body}</div></div></div>'


def side(s):
    """오른쪽 설명 칸."""
    out = [f'<div class="tag"><span class="id">{esc(s["id"])}</span><span class="name">{esc(s["name"])}</span>']
    if s.get("flag"):
        out.append(f'<span class="flagged">{esc(s["flag"])}</span>')
    out.append("</div>")
    if s.get("flow"):
        out.append(f'<p class="flow">{esc(s["flow"])}</p>')
    if s.get("req"):
        out.append(f'<p class="req">연결 요구사항 · {esc(s["req"])}</p>')
    if s.get("elements"):
        out.append("<h4>배치된 요소</h4><ul>" + "".join(f"<li>{esc(x)}</li>" for x in s["elements"]) + "</ul>")
    if s.get("rules"):
        out.append("<h4>동작 · 규칙</h4><ul>" + "".join(f"<li>{esc(x)}</li>" for x in s["rules"]) + "</ul>")
    if s.get("states"):
        out.append('<h4>상태 · 예외</h4><div class="st">' + "".join(f"<b>{esc(k)}</b><span>{esc(v)}</span>" for k, v in s["states"]) + "</div>")
    if s.get("src"):
        out.append(f'<div class="src">서비스 화면 · {esc(s["src"])}</div>')
    return "".join(out)


def block(s):
    kind = "wide" if s.get("wide") else ""
    left = s["screen"]
    anchor = s["id"].replace("-", "")
    return f'<div class="row {kind}" id="{anchor}">{left}<div class="side">{side(s)}</div></div>'


def swatch(hex_, label, dark=False):
    c = "#fff" if dark else "#243749"
    return f'<span style="display:inline-block;background:{hex_};color:{c};border:1px solid #E6DBCD;border-radius:999px;padding:3px 12px;font-size:12px;font-weight:700;margin:0 6px 6px 0">{hex_} {label}</span>'


def design_block():
    sw = "".join([swatch("#FFFFFF", "바탕"), swatch("#F8F1E7", "연한 면(카드·입력칸)"), swatch("#E6DBCD", "선·구분"), swatch("#81A6C6", "보조 포인트", True),
                  swatch("#5C86AC", "포인트·주 버튼", True), swatch("#243749", "글자", True), swatch("#E4F0F5", "안내 상자"),
                  swatch("#3E7A55", "정상", True), swatch("#8C6014", "주의", True), swatch("#B0543F", "위험", True)])
    return f'''<div class="sect" id="design"><h2>디자인 기준</h2></div>
<div class="row" style="grid-template-columns:1fr"><div class="side"><h3><span class="id">기준</span> 디자인 토큰 (서비스 화면 기준)</h3>
<div style="margin:14px 0"><b>색 — 파랑 + 크림 (2026-10 리디자인)</b><p>{sw}</p>
<p>포인트색은 화면당 주 버튼 하나에만 써요. 위험 범주 3색(정상·주의·위험)과 본문 17px·버튼 48px 클릭 영역 등 접근성 수치는 그대로예요.</p></div>
<div style="margin:14px 0"><b>모양</b><p>글꼴 나눔고딕. 입력칸 모서리 12 · 카드 20 · 버튼은 알약 모양. 그림자 없이 1px 선으로 나눠요. 모바일 390~430px 한 칼럼, 아래에 탭 5개(내 변화·챌린지·홈·커뮤니티·더보기), 위에 제목 + 파이 숫자 + 알림 종.</p></div>
<div style="margin:14px 0"><b>v4(9/28) 대비 바뀐 것</b><p>분홍 팔레트 → 파랑·크림. 데스크톱 사이드 메뉴 → 모바일 하단 탭. 관리자 화면만 컴퓨터용 넓은 화면.</p></div></div></div>'''


def toc_block(parts):
    items = []
    for p in parts:
        for s in p["screens"]:
            tag = f' <span class="flagged">{esc(s["flag"])}</span>' if s.get("flag") else ""
            items.append(f'<div><b>{esc(s["id"])}</b> {esc(s["name"])}{tag}</div>')
    flow = ("핵심 흐름: W01 → W01-2 → W02 → W03 → W04 → W04-2 → W05 → W06 → W07 → W09 → W10 → W08 → W11 → W11-2 → W23(12주 결과)<br>"
            "커뮤니티: W17(닉네임) → W13 → W14 → W15 → W16 · 파이·파티·공통 챌린지: W18 · W19 · W20 · 문의·공지·알림: W21 · W22 · 배지: W24<br>"
            "관리자(컴퓨터): A01 → A05")
    return (f'<div class="sect" id="toc"><h2>화면 목록 · 핵심 흐름</h2></div><div class="row" style="grid-template-columns:1fr"><div class="side">'
            f'<div style="columns:2;column-gap:28px;font-size:13px;line-height:1.9">{"".join(items)}</div><p style="margin-top:12px;font-size:13px;color:#5A6B7A">{flow}</p></div></div>')


def build(parts):
    nav = '<a href="#top">소개</a><a href="#design">디자인</a><a href="#toc">목록</a>' + "".join(f'<a href="#{p["anchor"]}">{esc(p["nav"])}</a>' for p in parts)
    body = []
    for p in parts:
        body.append(f'<div class="sect" id="{p["anchor"]}"><h2>{esc(p["title"])}</h2>' + (f'<p>{esc(p["desc"])}</p>' if p.get("desc") else "") + "</div>")
        body.extend(block(s) for s in p["screens"])
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PAEON 와이어프레임 v6</title><style>{CSS}</style></head><body>
<div class="picker"><span class="brand">PAEON</span>{nav}</div>
<div class="intro" id="top"><h1>파이온 PAEON 와이어프레임 v6</h1>
<p>모바일(390px) 화면은 왼쪽, 설명은 오른쪽. 관리자 화면은 컴퓨터에서 쓰는 화면이라 넓게 그렸어요.<br>
화면 ID는 기존(W01~W12)을 유지하고 새 화면은 W13부터 이어 붙였어요. 요구사항 ID는 요구사항 정의서(v2.4) 기준이에요.<br>
<b>v6 · 2026-10-26 · 서비스(지인 체험 배포 후) 화면 기준으로 전체 재작성.</b></p></div>
{design_block()}{toc_block(parts)}{"".join(body)}
</body></html>"""


def main():
    names = sys.argv[1:] or ["screens_community", "screens_admin"]
    parts = []
    for n in names:
        parts.extend(importlib.import_module(n).PARTS)
    OUT.write_text(build(parts), encoding="utf-8")
    print("wrote", OUT, "screens:", sum(len(p["screens"]) for p in parts))


if __name__ == "__main__":
    main()
