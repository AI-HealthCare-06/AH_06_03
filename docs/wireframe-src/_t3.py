import json, pathlib, sys, copy
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from playwright.sync_api import sync_playwright
import capture as C, mock_existing as E
pred = copy.deepcopy(E.PRED); pred["model_a"]["risk_level"]="normal"; pred["model_a"]["probability"]=0.016
seeds = dict(E.SEEDS); seeds["paeon-prediction"]=pred
with sync_playwright() as p:
    b=p.chromium.launch()
    for url,name,h in [("result.html","양호안내_결과화면",900),("dashboard.html","양호안내_홈",900)]:
        ctx=b.new_context(viewport={"width":390,"height":h},device_scale_factor=2); pg=ctx.new_page()
        def route(r):
            path=C.re.sub(r"^.*/v1","",r.request.url)
            body={"data":[]} if path=="/notices" else C.mock(r.request.url,r.request.method)
            r.fulfill(status=200,content_type="application/json",headers={"access-control-allow-origin":"*","access-control-allow-methods":"*","access-control-allow-headers":"*"},body=json.dumps(body))
        pg.route(C.API+"/**",route)
        pg.goto(C.BASE+"login.html")
        pg.evaluate("()=>{localStorage.clear();localStorage.setItem('paeon-access-token','d');localStorage.setItem('paeon-refresh-token','d');}")
        for k,v in seeds.items(): pg.evaluate("([k,v])=>localStorage.setItem(k,JSON.stringify(v))",[k,v])
        pg.goto(C.BASE+url); pg.wait_for_timeout(2200)
        pg.screenshot(path=str(pathlib.Path('docs/wireframe-src/preview')/f"{name}.png"))
        ctx.close()
    b.close()
