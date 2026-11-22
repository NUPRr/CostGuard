"""Cost Guard - local demo server (no AWS needed)."""
import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KEY = "demo1234"
PORT = 8000
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "local_data.json")
DASH = os.path.join(HERE, "dashboard", "index.html")

state = {
    "settings": {"auto_stop": True, "allowed_types": ["t2.micro", "t3.micro", "t3.small"]},
    "events": [],
}
if os.path.exists(DATA):
    try:
        with open(DATA) as f:
            state = json.load(f)
    except Exception:
        pass


def save():
    with open(DATA, "w") as f:
        json.dump(state, f, indent=2)


def simulate(instance_type, when=None):
    s = state["settings"]
    allowed = [t.lower() for t in s["allowed_types"]]
    if instance_type.lower() in allowed:
        status = "ALLOWED"
        msg = f"{instance_type} is on the allowed list. No action needed."
    elif s["auto_stop"]:
        status = "STOPPED"
        msg = f"{instance_type} is not allowed. It was stopped automatically."
    else:
        status = "FLAGGED"
        msg = f"{instance_type} is not allowed. Auto-stop is OFF, so it was left running."
    event = {
        "time": when or datetime.now(timezone.utc).isoformat(),
        "instance_id": "i-" + uuid.uuid4().hex[:17],
        "instance_type": instance_type,
        "region": "ap-south-1 (demo)",
        "launched_by": "demo-user",
        "status": status,
        "message": msg,
    }
    state["events"].insert(0, event)
    state["events"] = state["events"][:50]
    save()
    return event


def seed():
    """Fill the last 7 days with realistic sample launches."""
    rnd = random.Random(7)
    types = ["t3.micro", "t3.micro", "t3.small", "t3.medium", "t3.large",
             "c5.4xlarge", "p3.8xlarge", "g4dn.xlarge"]
    state["events"] = []
    now = datetime.now(timezone.utc)
    items = []
    for d in range(6, -1, -1):
        for _ in range(rnd.randint(2, 5)):
            when = now - timedelta(days=d, hours=rnd.randint(0, 20), minutes=rnd.randint(0, 59))
            items.append((when, rnd.choice(types)))
    items.sort()
    for when, t in items:
        simulate(t, when.isoformat())


SIM_BAR = """
<div style="height:90px"></div>
<div style="position:fixed;left:0;right:0;bottom:0;background:#10243a;color:#fff;padding:10px 14px;
display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:center;z-index:9;font:15px system-ui">
  <strong>Demo mode</strong>
  <select id="simType" style="padding:10px;border-radius:8px;font:inherit">
    <option>t3.micro</option><option>t3.small</option><option>t3.medium</option><option>t3.large</option>
    <option>c5.4xlarge</option><option>g4dn.xlarge</option><option>p3.8xlarge</option>
  </select>
  <button id="simBtn" style="padding:10px 16px;border:0;border-radius:8px;background:#0f8b6d;color:#fff;font:inherit;font-weight:600;min-height:44px">Simulate a launch</button>
  <button id="seedBtn" style="padding:10px 16px;border:1px solid #5b7a99;border-radius:8px;background:transparent;color:#fff;font:inherit;font-weight:600;min-height:44px">Load sample week</button>
  <button id="clearBtn" style="padding:10px 16px;border:1px solid #5b7a99;border-radius:8px;background:transparent;color:#fff;font:inherit;font-weight:600;min-height:44px">Clear</button>
</div>
<script>
async function demoPost(path, body) {
  await fetch(path, {method: "POST",
    headers: {"x-api-key": getKey(), "Content-Type": "application/json"},
    body: JSON.stringify(body || {})});
  load();
}
document.getElementById("simBtn").onclick = () => demoPost("/simulate", {instance_type: document.getElementById("simType").value});
document.getElementById("seedBtn").onclick = () => demoPost("/seed");
document.getElementById("clearBtn").onclick = () => demoPost("/clear");
</script>
"""


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authed(self):
        return self.headers.get("x-api-key", "") == KEY

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                with open(DASH, encoding="utf-8") as f:
                    html = f.read()
            except FileNotFoundError:
                html = ""
            if not html.strip():
                return self.send(200, "<h2>dashboard/index.html is empty. Paste the dashboard code into it and refresh.</h2>", "text/html")
            html = html.replace('const API_URL = "PASTE_API_URL_HERE";', 'const API_URL = "";')
            html = html.replace("</body>", SIM_BAR + "</body>")
            return self.send(200, html, "text/html; charset=utf-8")
        if not self.authed():
            return self.send(401, json.dumps({"error": "Wrong access key"}))
        if self.path == "/events":
            return self.send(200, json.dumps({"events": state["events"]}))
        if self.path == "/settings":
            return self.send(200, json.dumps(state["settings"]))
        self.send(404, json.dumps({"error": "Not found"}))

    def do_POST(self):
        if not self.authed():
            return self.send(401, json.dumps({"error": "Wrong access key"}))
        size = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(size) or "{}")
        except ValueError:
            return self.send(400, json.dumps({"error": "Bad request"}))
        if self.path == "/settings":
            types = [str(t).strip().lower() for t in data.get("allowed_types", []) if str(t).strip()]
            state["settings"] = {"auto_stop": bool(data.get("auto_stop", True)), "allowed_types": types}
            save()
            return self.send(200, json.dumps(state["settings"]))
        if self.path == "/simulate":
            return self.send(200, json.dumps(simulate(str(data.get("instance_type", "t3.micro")))))
        if self.path == "/seed":
            seed()
            return self.send(200, json.dumps({"ok": True}))
        if self.path == "/clear":
            state["events"] = []
            save()
            return self.send(200, json.dumps({"ok": True}))
        self.send(404, json.dumps({"error": "Not found"}))

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"Cost Guard is running. Open http://localhost:{PORT}")
    print(f"Access key: {KEY}   (press Ctrl+C to stop)")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()