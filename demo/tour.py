"""Viva project tour: every part of Mini-Netflix in one browser page.

    python demo/tour.py          then open http://localhost:8095

Chapters: the Netflix case, our architecture, the app (live API calls), the circuit breaker
(live, needs Docker), replays of the real AWS chaos runs (S1 vs S2, AZ loss, scale-out) and
local runs, the results table, AWS evidence logs, a code tour, the test suite (run live), the
cost model and the limitations.

Replays are rebuilt second by second from the raw results/<stage>/<exp>/run<N>/*.csv files, so
what you see is the recorded data, not an animation. Standard library only for the server;
the live parts reuse demo/dashboard.py. Do not run alongside demo/dashboard.py, demo/demo.sh or
loadtest/run_local_suite.sh (they share the containers and port 8081).
"""
import csv
import json
import math
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import dashboard  # noqa: E402  live breaker demo: compose actions, probe, status

PORT = int(os.environ.get("TOUR_PORT", "8095"))
RESULTS = ROOT / "results"

# Files the page may read. Terraform state, variables and keys are never served.
ALLOWED_DIRS = ["results", "docs/diagrams", "cost", "app", "chaos", "loadtest", "infra", "demo"]
ALLOWED_EXT = {".png", ".svg", ".txt", ".md", ".json", ".py", ".tf", ".sh", ".yml", ".conf", ".html"}
BLOCKED = (".tfstate", ".tfvars", ".pem", ".env", ".terraform")
TYPES = {".png": "image/png", ".svg": "image/svg+xml", ".html": "text/html; charset=utf-8",
         ".json": "application/json"}

# ------------------------------------------------------------------ replays from raw CSVs
_replay_cache = {}
_replay_lock = threading.Lock()


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _p95(values):
    if not values:
        return None
    values.sort()
    return values[min(len(values) - 1, math.ceil(0.95 * len(values)) - 1)]


def build_replay(run_rel):
    run = (RESULTS / run_rel).resolve()
    if RESULTS.resolve() not in run.parents or not (run / "requests.csv").exists():
        raise FileNotFoundError(run_rel)
    secs = {}
    t0 = None
    with open(run / "requests.csv", newline="") as f:
        rows = csv.DictReader(f)
        for r in rows:
            ts = _num(r["ts_start"])
            if ts is None:
                continue
            t0 = ts if t0 is None else min(t0, ts)
            s = secs.setdefault(int(ts), {"n": 0, "err": 0, "home": 0, "ok": 0, "fb": 0, "lat": [], "inst": set()})
            status = int(_num(r["status"]) or 0)
            lat = _num(r["latency_ms"]) or 0
            s["n"] += 1
            if status != 200:
                s["err"] += 1
            if r["name"] == "home":
                s["home"] += 1
                s["lat"].append(lat)
                if status == 200 and lat <= 1000:
                    s["ok"] += 1
                if r.get("recs_source") == "fallback":
                    s["fb"] += 1
            sb = r.get("served_by") or ""
            if sb:
                s["inst"].add(sb.split("/")[0])
    if t0 is None:
        raise ValueError("empty requests.csv")
    base = int(t0)
    last = max(secs)
    series = {"t": [], "rps": [], "err": [], "home": [], "ok": [], "fb": [], "p95": [], "inst": []}
    for sec in range(base, last + 1):
        s = secs.get(sec)
        series["t"].append(sec - base)
        if s is None:
            for k in ("rps", "err", "home", "ok", "fb", "inst"):
                series[k].append(0)
            series["p95"].append(None)
            continue
        series["rps"].append(s["n"])
        series["err"].append(s["err"])
        series["home"].append(s["home"])
        series["ok"].append(s["ok"])
        series["fb"].append(s["fb"])
        series["p95"].append(round(_p95(s["lat"]), 1) if s["lat"] else None)
        series["inst"].append(len(s["inst"]))

    events = []
    if (run / "events.csv").exists():
        with open(run / "events.csv", newline="") as f:
            for r in csv.DictReader(f):
                ts = _num(r["ts"])
                if ts is not None and base - 5 <= ts <= last + 5:
                    events.append({"t": round(ts - base, 1), "action": r["action"], "target": r["target"],
                                   "az": r["az"], "note": r.get("note", "")})
    watch = []
    if (run / "watch.csv").exists():
        with open(run / "watch.csv", newline="") as f:
            for r in csv.DictReader(f):
                ts = _num(r["ts"])
                if ts is None or ts < base - 5 or ts > last + 5:
                    continue
                watch.append({"t": round(ts - base, 1), **{k: _num(r.get(k)) for k in
                              ("asg_desired", "asg_inservice", "tg_healthy", "ec2_running", "probe_ok")}})
    summary = json.loads((run / "summary.json").read_text()) if (run / "summary.json").exists() else {}
    summary.pop("run_dir", None)
    return {"run": run_rel, "duration": last - base + 1, "series": series, "events": events,
            "watch": watch, "summary": summary}


def replay(run_rel):
    with _replay_lock:
        if run_rel not in _replay_cache:
            _replay_cache[run_rel] = build_replay(run_rel)
        return _replay_cache[run_rel]


def summaries():
    rows = []
    for f in sorted(RESULTS.glob("*/*/run*/summary.json")):
        stage, exp, run = f.parts[-4], f.parts[-3], f.parts[-2]
        if "check" in exp:
            continue
        s = json.loads(f.read_text())
        rows.append({"stage": stage, "exp": exp, "run": run, **{k: s.get(k) for k in (
            "availability_pct", "home_p50_ms", "home_p95_ms", "throughput_rps", "longest_outage_s",
            "fallback_pct_of_home", "mean_time_to_restore_capacity_s", "slo_met")}})
    return rows


# ------------------------------------------------------------------ live API explorer
API_PATHS = ("/", "/health", "/movies", "/login", "/recommendations/", "/movies/")


def call_app(method, path, body):
    if not (path == "/" or path.startswith(API_PATHS[1:]) or path.startswith("/?")):
        return {"error": "path not allowed"}
    data = body.encode() if body else None
    req = urllib.request.Request(dashboard.APP_URL + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            status, headers, raw = r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        status, headers, raw = e.code, e.headers, e.read()
    except Exception as e:
        return {"status": 0, "ms": round((time.perf_counter() - t0) * 1000, 1),
                "error": f"no answer ({type(e).__name__}). Start the services in the Circuit breaker chapter."}
    ms = round((time.perf_counter() - t0) * 1000, 1)
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = raw[:2000].decode("utf-8", "replace")
    return {"status": status, "ms": ms, "served_by": headers.get("X-Served-By", ""),
            "recs_source": headers.get("X-Recs-Source", ""), "body": parsed}


# ------------------------------------------------------------------ test runner
tests = {"running": False, "output": "", "code": None, "started": None}
tests_lock = threading.Lock()


def run_tests():
    cmd = [sys.executable, "-m", "pytest", "app/tests", "chaos", "-v", "--color=no", "-p", "no:cacheprovider"]
    out = []
    try:
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace")
        for line in p.stdout:
            out.append(line)
            with tests_lock:
                tests["output"] = "".join(out)
        code = p.wait()
    except Exception as exc:
        out.append(f"\ncould not run pytest: {exc}\n")
        code = -1
    with tests_lock:
        tests.update(running=False, code=code, output="".join(out))


# ------------------------------------------------------------------ HTTP
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_bytes(self, body, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, obj, code=200):
        self.send_bytes(json.dumps(obj).encode(), "application/json", code)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n).decode("utf-8", "replace") if n else ""

    def serve_file(self, rel):
        rel = unquote(rel).replace("\\", "/").lstrip("/")
        path = (ROOT / rel).resolve()
        ok = (ROOT.resolve() in path.parents and path.is_file() and path.suffix.lower() in ALLOWED_EXT
              and any(rel == d or rel.startswith(d + "/") for d in ALLOWED_DIRS)
              and not any(b in path.name for b in BLOCKED) and ".terraform" not in path.parts)
        if not ok:
            return self.send_json({"error": "not available"}, 404)
        ctype = TYPES.get(path.suffix.lower(), "text/plain; charset=utf-8")
        self.send_bytes(path.read_bytes(), ctype)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/":
                return self.send_bytes((HERE / "tour.html").read_bytes(), "text/html; charset=utf-8")
            if u.path == "/breaker":
                return self.send_bytes((HERE / "dashboard.html").read_bytes(), "text/html; charset=utf-8")
            if u.path.startswith("/files/"):
                return self.serve_file(u.path[len("/files/"):])
            if u.path == "/api/replay":
                return self.send_json(replay(q.get("run", [""])[0]))
            if u.path == "/api/summaries":
                return self.send_json(summaries())
            if u.path == "/api/list":
                d = q.get("dir", [""])[0]
                if d not in ("results/aws-logs",):
                    return self.send_json([], 404)
                return self.send_json(sorted(p.name for p in (ROOT / d).iterdir() if p.is_file()))
            if u.path == "/api/tests":
                with tests_lock:
                    return self.send_json(dict(tests))
            # live breaker demo (same API as demo/dashboard.py)
            if u.path == "/api/probe":
                return self.send_json(dashboard.probe(q.get("user", ["user1"])[0]))
            if u.path == "/api/status":
                states, docker_ok = dashboard.service_states()
                with dashboard.job_lock:
                    j = dict(dashboard.job, log=dashboard.job["log"][-20:])
                return self.send_json({"docker": docker_ok, "services": states,
                                       "breaker": dashboard.breaker_mode() if states.get("catalogue") == "running" else None,
                                       "job": j})
        except FileNotFoundError:
            return self.send_json({"error": "no such run"}, 404)
        except Exception as exc:
            return self.send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/call":
            req = json.loads(self.body() or "{}")
            return self.send_json(call_app(req.get("method", "GET"), req.get("path", "/"), req.get("body")))
        if u.path == "/api/tests/run":
            with tests_lock:
                if tests["running"]:
                    return self.send_json({"error": "tests already running"}, 409)
                tests.update(running=True, output="", code=None, started=time.time())
            threading.Thread(target=run_tests, daemon=True).start()
            return self.send_json({"ok": True})
        if u.path.startswith("/api/action/"):
            name = u.path.rsplit("/", 1)[-1]
            if name not in dashboard.ACTIONS:
                return self.send_json({"error": "unknown action"}, 404)
            with dashboard.job_lock:
                if dashboard.job["busy"]:
                    return self.send_json({"error": "another action is still running"}, 409)
                dashboard.job.update(busy=True, label=dashboard.ACTIONS[name][0], error=None)
                dashboard.job["log"].append({"ts": time.time(), "text": dashboard.ACTIONS[name][0] + "..."})
            threading.Thread(target=dashboard.run_job, args=(name,), daemon=True).start()
            return self.send_json({"ok": True})
        self.send_json({"error": "not found"}, 404)


if __name__ == "__main__":
    print(f"Mini-Netflix project tour: http://localhost:{PORT}   (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
