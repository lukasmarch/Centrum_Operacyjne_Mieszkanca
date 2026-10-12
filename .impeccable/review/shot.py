"""Zrzut przez CDP: prawdziwa szerokość urządzenia + opcjonalny localStorage.
Użycie: python shot.py <width> <height> <out.png> [village] [fullpage:1|0]"""
import asyncio, base64, json, subprocess, sys, tempfile, time, urllib.request
import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H, OUT = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
VILLAGE = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
FULL = len(sys.argv) <= 5 or sys.argv[5] == "1"
PORT = 9333

proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--remote-debugging-port={PORT}",
                         f"--user-data-dir={tempfile.mkdtemp()}", "--hide-scrollbars", "about:blank"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    try:
        tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
        page = next(t for t in tabs if t["type"] == "page"); break
    except Exception:
        time.sleep(0.2)

async def main():
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=2**28) as ws:
        n = 0
        async def call(method, **params):
            nonlocal n; n += 1; mid = n
            await ws.send(json.dumps({"id": mid, "method": method, "params": params}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == mid: return msg.get("result", {})
        mobile = W < 800
        await call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=mobile)
        await call("Page.enable")
        await call("Page.navigate", url="http://localhost:3001/")
        await asyncio.sleep(1.5)
        # baner cookies i PWA zasłaniają treść — decyzja „tylko niezbędne” zapisana jak przez użytkownika
        await call("Runtime.evaluate", expression=(
            "localStorage.setItem('cookie_consent_v1', JSON.stringify({necessary:true,analytics:false,marketing:false,timestamp:new Date().toISOString()}));"
            "localStorage.setItem('pwa_install_dismissed', '1');"
            + (f"localStorage.setItem('rl_village', {json.dumps(VILLAGE)});" if VILLAGE else "")))
        await call("Page.reload")
        await asyncio.sleep(6)
        if FULL:
            m = await call("Page.getLayoutMetrics")
            h = int(m["cssContentSize"]["height"])
            await call("Emulation.setDeviceMetricsOverride", width=W, height=h, deviceScaleFactor=1, mobile=mobile)
            await asyncio.sleep(1)
        sw = await call("Runtime.evaluate", expression="document.documentElement.scrollWidth+'/'+innerWidth", returnByValue=True)
        print("scrollWidth/innerWidth:", sw["result"]["value"])
        shot = await call("Page.captureScreenshot", format="png")
        open(OUT, "wb").write(base64.b64decode(shot["data"]))

try:
    asyncio.run(main())
finally:
    proc.terminate()
