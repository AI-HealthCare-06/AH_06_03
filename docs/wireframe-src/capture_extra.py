"""capture.py로 못 찍는 변형 화면(저장값·서버 응답을 바꿔야 하는 것)을 찍는다 → shots/*.png
 - W06-good: 결과가 "양호"일 때 안내 문구와 모델 버전 표시
 - W08-3a/3b: 12주를 모두 마친 홈과 "새 12주 시작하기" 확인창 (서버가 새 12주 API를 준다고 가정한 가짜 응답)
실행(frontend에서 python -m http.server 5500을 켠 뒤): python docs/wireframe-src/capture_extra.py
"""
import copy
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from playwright.sync_api import sync_playwright

import capture as C
import mock_existing as E


def cy(i, n, s="completed"):
    return {"cycle_id": i, "cycle_number": n, "program_number": 1, "status": s, "started_on": f"2026-08-{n * 5:02d}",
            "ended_on": f"2026-09-{n * 5:02d}", "cycle_rate": 0.9, "reassessed": True}


STATUS = {"program_number": 1, "complete": True, "can_restart": True, "model_version": "v0.1.1", "latest_model_version": "v0.2.0",
          "version_changed": True, "latest_updated_on": "2026-10-20", "change_note": "한국인 보정 확률 기준"}


def run():
    pred = copy.deepcopy(E.PRED)
    pred["model_a"].update(risk_level="normal", probability=0.016, model_version="v0.2.0", model_updated_on="2026-10-20")
    pred["model_b"].update(model_version="v0.2.0", model_updated_on="2026-10-20")
    seeds = dict(E.SEEDS)
    seeds["paeon-prediction"] = pred
    seeds.pop("paeon-cycle", None)
    seeds.pop("paeon-progress", None)

    def shoot(name, url, h, click=None):
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={"width": 390, "height": h}, device_scale_factor=2, has_touch=True)
            pg = ctx.new_page()
            pg.clock.install(time="2026-10-25T03:00:00Z")

            def route(r):
                path = C.re.sub(r"^.*/v1", "", r.request.url)
                if path == "/notices":
                    body = {"data": []}
                elif path == "/challenges/cycles":
                    body = {"data": [cy("c3", 3), cy("c2", 2), cy("c1", 1)]}
                elif path == "/challenges/program/status":
                    body = {"data": STATUS}
                else:
                    body = C.mock(r.request.url, r.request.method)
                r.fulfill(status=200, content_type="application/json", body=json.dumps(body),
                          headers={"access-control-allow-origin": "*", "access-control-allow-methods": "*", "access-control-allow-headers": "*"})

            pg.route(C.API + "/**", route)
            pg.goto(C.BASE + "login.html")
            pg.evaluate("() => { localStorage.clear(); localStorage.setItem('paeon-access-token','d'); localStorage.setItem('paeon-refresh-token','d'); }")
            for k, v in seeds.items():
                pg.evaluate("([k, v]) => localStorage.setItem(k, JSON.stringify(v))", [k, v])
            pg.goto(C.BASE + url)
            pg.wait_for_timeout(2200)
            if click:
                pg.click(click)
                pg.wait_for_timeout(600)
            pg.screenshot(path=str(C.OUT / f"{name}.png"))
            print(name, url)
            b.close()

    shoot("W06-good", "result.html", 1500)
    shoot("W08-3a", "dashboard.html", 780)
    shoot("W08-3b", "dashboard.html", 780, click="#restart-prog")


if __name__ == "__main__":
    run()
