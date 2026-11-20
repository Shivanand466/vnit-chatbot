"""
Screenshot the chat page after something has happened in it, with headless Edge.

tools/shot.sh takes the picture when the page has loaded, which is before a
streamed answer has finished. This drives Edge through its DevTools protocol
instead: open the page at a given size, optionally run some JavaScript (type a
question, press Stop), wait until a CSS selector appears, then take the picture.

    python tools/cdp_shot.py "<url>" checks/out.png 1280 900 --wait ".msg.bot .meta"
        [--js "<script run after load>"] [--after-js "<script run before the shot>"] [--timeout 120]

A tool for checking the page during development; it uses the websocket-client
package that came with Anaconda and is not needed to run the chatbot.
"""
import argparse
import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.request

import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9333


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("width", type=int)
    ap.add_argument("height", type=int)
    ap.add_argument("--wait", default="")
    ap.add_argument("--js", default="")
    ap.add_argument("--after-js", default="")
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--dark", action="store_true")
    a = ap.parse_args()

    profile = tempfile.mkdtemp(prefix="vnit-v2-edge-")
    edge = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                             f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
                             f"--window-size={max(a.width, 600)},{a.height}", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        target = None
        for _ in range(60):
            try:
                pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                target = next(p for p in pages if p.get("type") == "page")
                break
            except Exception:
                time.sleep(0.5)
        ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
        counter = [0]

        def send(method, **params):
            counter[0] += 1
            ws.send(json.dumps({"id": counter[0], "method": method, "params": params}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == counter[0]:
                    return msg.get("result", {})

        def js(expr):
            r = send("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
            return r.get("result", {}).get("value")

        send("Emulation.setDeviceMetricsOverride", width=a.width, height=a.height,
             deviceScaleFactor=1, mobile=a.width < 600)
        send("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme",
                                                      "value": "dark" if a.dark else "light"}])
        send("Page.enable")
        send("Page.navigate", url=a.url)
        time.sleep(2)
        if a.js:
            js(a.js)
        if a.wait:
            end = time.time() + a.timeout
            while time.time() < end and not js(f"!!document.querySelector({json.dumps(a.wait)})"):
                time.sleep(0.5)
        if a.after_js:
            js(a.after_js)
            time.sleep(1.5)
        time.sleep(0.8)
        shot = send("Page.captureScreenshot", format="png")
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "wb") as fh:
            fh.write(base64.b64decode(shot["data"]))
        print(f"saved {a.out}")
        ws.close()
    finally:
        edge.terminate()


if __name__ == "__main__":
    main()
