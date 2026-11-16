"""Viva demo dashboard: the circuit-breaker demo (demo/demo.sh) in a browser.

    python demo/dashboard.py          then open http://localhost:8090

Buttons start the local S2 service split with the breaker ON or OFF, stop / start the
recommendations service, and shut everything down. The page sends a steady stream of
home-page requests through the gateway (http://localhost:8081) and shows each answer live.
Standard library only; needs Docker Desktop running. Do not run alongside demo.sh or
loadtest/run_local_suite.sh (they use the same containers and port 8081).
"""
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPOSE = ["docker", "compose", "-f", os.path.join(ROOT, "app", "docker-compose.services.yml")]
APP_URL = "http://127.0.0.1:8081"  # not "localhost": on Windows that tries IPv6 first and stalls when down
PORT = int(os.environ.get("DASHBOARD_PORT", "8090"))
PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")

job = {"busy": False, "label": "", "log": [], "error": None}
job_lock = threading.Lock()
_breaker_cache = {"id": None, "mode": None}


def run(cmd, env=None, timeout=900):
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def wait_healthy(seconds=120):
    end = time.time() + seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(APP_URL + "/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1.5)
    return False


def start_stack(mode):
    env = dict(os.environ, BREAKER=mode)
    code, out = run(COMPOSE + ["up", "-d", "--build", "--force-recreate"], env=env)
    if code != 0:
        raise RuntimeError(out[-800:])
    if not wait_healthy():
        raise RuntimeError("services started but /health did not answer within 120 s")


def compose_simple(*args):
    code, out = run(COMPOSE + list(args), timeout=120)
    if code != 0:
        raise RuntimeError(out[-800:])


ACTIONS = {
    "start-on": ("Starting services with the circuit breaker ON", lambda: start_stack("on")),
    "start-off": ("Starting services with the circuit breaker OFF", lambda: start_stack("off")),
    "kill-recs": ("Stopping the recommendations service", lambda: compose_simple("stop", "recommendations")),
    "restore-recs": ("Starting the recommendations service", lambda: compose_simple("start", "recommendations")),
    "down": ("Shutting everything down", lambda: compose_simple("down")),
}


def run_job(name):
    label, fn = ACTIONS[name]
    try:
        fn()
        err = None
    except Exception as exc:  # shown in the page, never crashes the server
        err = str(exc)
    with job_lock:
        job.update(busy=False, error=err)
        job["log"].append({"ts": time.time(), "text": (label + (" - FAILED" if err else " - done"))})


def service_states():
    code, out = run(COMPOSE + ["ps", "-a", "--format", "json"], timeout=30)
    states = {}
    if code != 0 or not out:
        return states, code == 0
    text = out.strip()
    try:
        rows = json.loads(text) if text.startswith("[") else [json.loads(l) for l in text.splitlines() if l.strip()]
    except ValueError:
        return states, False
    for r in rows:
        states[r.get("Service")] = r.get("State", "unknown")
    return states, True


def breaker_mode():
    code, cid = run(COMPOSE + ["ps", "-q", "catalogue"], timeout=30)
    cid = cid.strip()
    if code != 0 or not cid:
        return None
    if _breaker_cache["id"] == cid:
        return _breaker_cache["mode"]
    code, out = run(["docker", "inspect", "--format", "{{json .Config.Env}}", cid], timeout=30)
    mode = None
    if code == 0:
        try:
            for kv in json.loads(out):
                if kv.startswith("BREAKER="):
                    mode = kv.split("=", 1)[1].lower()
        except ValueError:
            pass
    _breaker_cache.update(id=cid, mode=mode)
    return mode


def probe(user):
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(f"{APP_URL}/?user={user}", timeout=6) as r:
            status, body, src = r.status, r.read(), r.headers.get("X-Recs-Source", "")
    except urllib.error.HTTPError as e:
        status, body, src = e.code, e.read(), e.headers.get("X-Recs-Source", "")
    except Exception as e:
        return {"status": 0, "ms": round((time.perf_counter() - t0) * 1000, 1), "source": "",
                "error": f"no answer ({type(e).__name__})"}
    ms = round((time.perf_counter() - t0) * 1000, 1)
    try:
        data = json.loads(body)
    except ValueError:
        data = {"raw": body[:300].decode("utf-8", "replace")}
    return {"status": status, "ms": ms, "source": src, "data": data}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            with open(PAGE, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif u.path == "/api/probe":
            user = parse_qs(u.query).get("user", ["user1"])[0]
            self.send_json(probe(user))
        elif u.path == "/api/status":
            states, docker_ok = service_states()
            with job_lock:
                j = dict(job, log=job["log"][-20:])
            self.send_json({"docker": docker_ok, "services": states,
                            "breaker": breaker_mode() if states.get("catalogue") == "running" else None,
                            "job": j})
        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        name = u.path.rsplit("/", 1)[-1]
        if not u.path.startswith("/api/action/") or name not in ACTIONS:
            return self.send_json({"error": "unknown action"}, 404)
        with job_lock:
            if job["busy"]:
                return self.send_json({"error": "another action is still running"}, 409)
            job.update(busy=True, label=ACTIONS[name][0], error=None)
            job["log"].append({"ts": time.time(), "text": ACTIONS[name][0] + "..."})
        threading.Thread(target=run_job, args=(name,), daemon=True).start()
        self.send_json({"ok": True})


if __name__ == "__main__":
    print(f"Mini-Netflix demo dashboard: http://localhost:{PORT}   (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
