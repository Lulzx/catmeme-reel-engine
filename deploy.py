#!/usr/bin/env python3
"""One-command deploy for Cat Reel Studio — build, sync, restart, with a live
animated CLI.

    python3 deploy.py                 # full deploy
    python3 deploy.py --no-web        # skip the web build/upload (data-only push)
    python3 deploy.py --db-only       # only reconcile the SQLite store
    python3 deploy.py --dry-run       # show the plan, touch nothing

What it does, in order:
  1. preflight   reach the server, check rsync/scp/ssh
  2. web build   `npm run build` locally (the server's Node is too old)
  3. code        `git push` then `git pull` on the server
  4. web dist    rsync web/dist -> server
  5. db sync     pull the server DB, MERGE with local (engine.db.merge), push back
  6. media       rsync output/*.mp4 + posters -> server
  7. restart     restart the systemd service and health-check it

The DB sync is a true two-way merge (see engine/db.py): local authoring and the
server's live scheduling state converge without clobbering each other.

Host/paths come from the environment (sensible defaults below):
  CRS_HOST=lulz  CRS_REMOTE=/opt/cats  CRS_SERVICE=cats.service  CRS_PORT=8765
"""
import argparse, os, shutil, subprocess, sys, threading, time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "engine"))

HOST    = os.environ.get("CRS_HOST", "lulz")
REMOTE  = os.environ.get("CRS_REMOTE", "/opt/cats")
SERVICE = os.environ.get("CRS_SERVICE", "cats.service")
PORT    = os.environ.get("CRS_PORT", "8765")

# ── tiny ANSI toolkit ─────────────────────────────────────────────────────────
TTY = sys.stdout.isatty()
def _c(code, s): return f"\033[{code}m{s}\033[0m" if TTY else s
def dim(s):   return _c("2", s)
def bold(s):  return _c("1", s)
def green(s): return _c("32", s)
def red(s):   return _c("31", s)
def cyan(s):  return _c("36", s)
def lime(s):  return _c("38;2;194;255;77", s)   # the studio brand lime

FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class Spinner:
    """A single animated status line that resolves to ✓ / ✗ when the step ends."""
    def __init__(self, label):
        self.label = label
        self._stop = threading.Event()
        self._t = None
        self.t0 = time.monotonic()

    def __enter__(self):
        if TTY:
            self._t = threading.Thread(target=self._spin, daemon=True)
            self._t.start()
        else:
            print(f"  …  {self.label}", flush=True)
        return self

    def __exit__(self, *exc):
        # safety net: if done() wasn't called (e.g. an exception), stop the thread
        if not self._stop.is_set():
            self._stop.set()
            if self._t:
                self._t.join()
        return False

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            frame = lime(FRAMES[i % len(FRAMES)])
            sys.stdout.write(f"\r  {frame}  {self.label}{dim(' …')}\033[K")
            sys.stdout.flush()
            i += 1
            time.sleep(0.08)

    def done(self, ok, detail=""):
        self._stop.set()
        if self._t:
            self._t.join()
        el = dim(f"{time.monotonic() - self.t0:.1f}s")
        mark = green("✓") if ok else red("✗")
        tail = f"  {dim('— ' + detail)}" if detail else ""
        line = f"\r  {mark}  {self.label}{tail}  {el}\033[K"
        print(line if TTY else f"  {'OK' if ok else 'FAIL'}  {self.label}  {detail}".rstrip(),
              flush=True)


class StepError(Exception):
    def __init__(self, msg, output=""):
        super().__init__(msg); self.output = output


def run(cmd, **kw):
    """Run a command, raising StepError with captured output on failure."""
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if p.returncode != 0:
        raise StepError(f"`{' '.join(cmd)}` exited {p.returncode}",
                        (p.stdout + p.stderr).strip())
    return p.stdout.strip()


def step(label, fn, dry=False):
    """Execute one step under a spinner; abort the whole deploy on failure."""
    with Spinner(label) as sp:
        if dry:
            sp.done(True, "skipped (dry-run)"); return None
        try:
            detail = fn() or ""
        except StepError as e:
            sp.done(False, str(e))
            if e.output:
                print(dim("\n    " + e.output.replace("\n", "\n    ")), file=sys.stderr)
            raise SystemExit(1)
        sp.done(True, detail)
        return detail


# ── steps ─────────────────────────────────────────────────────────────────────
def preflight():
    for tool in ("ssh", "scp", "rsync"):
        if not shutil.which(tool):
            raise StepError(f"`{tool}` not found on PATH")
    run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", HOST,
         f"test -d {REMOTE}"])
    return f"{HOST}:{REMOTE}"


def build_web():
    run(["npm", "--prefix", os.path.join(ROOT, "web"), "run", "build"])
    dist = os.path.join(ROOT, "web", "dist", "index.html")
    return "web/dist built" if os.path.exists(dist) else "built"


def push_code():
    branch = run(["git", "-C", ROOT, "rev-parse", "--abbrev-ref", "HEAD"])
    run(["git", "-C", ROOT, "push", "origin", branch])
    out = run(["ssh", HOST, f"cd {REMOTE} && git pull --ff-only"])
    return out.splitlines()[-1].strip() if out else f"pushed {branch}"


def sync_web():
    run(["rsync", "-az", "--delete",
         os.path.join(ROOT, "web", "dist") + "/", f"{HOST}:{REMOTE}/web/dist/"])
    return "dist synced"


def sync_db():
    import db as DB
    work = os.path.join(ROOT, ".deploy"); os.makedirs(work, exist_ok=True)
    local = os.path.join(ROOT, "data", "videos.db")
    pulled = os.path.join(work, "remote.videos.db")
    # back up both ends before touching them
    if os.path.exists(local):
        shutil.copy2(local, local + ".bak")
    run(["ssh", HOST, f"test -f {REMOTE}/data/videos.db && "
                      f"cp {REMOTE}/data/videos.db {REMOTE}/data/videos.db.bak || true"])
    run(["scp", "-q", f"{HOST}:{REMOTE}/data/videos.db", pulled])
    summary = DB.merge(local, pulled)                  # writes both files in place
    # push the merged DB atomically (scp to .new, then mv)
    run(["scp", "-q", pulled, f"{HOST}:{REMOTE}/data/videos.db.new"])
    run(["ssh", HOST, f"mv {REMOTE}/data/videos.db.new {REMOTE}/data/videos.db"])
    bits = [f"{summary['total']} rows"]
    if summary["to_remote"]: bits.append(f"+{len(summary['to_remote'])}→server")
    if summary["to_local"]:  bits.append(f"+{len(summary['to_local'])}→local")
    return ", ".join(bits)


def sync_media():
    out = os.path.join(ROOT, "output")
    mp4s = [f for f in os.listdir(out)] if os.path.isdir(out) else []
    if any(f.endswith((".mp4", ".mov", ".webm")) for f in mp4s):
        run(["rsync", "-az", "--include=*/", "--include=*.mp4", "--include=*.mov",
             "--include=*.webm", "--exclude=*", out + "/", f"{HOST}:{REMOTE}/output/"])
    posters = os.path.join(ROOT, "work", "posters")
    if os.path.isdir(posters):
        run(["rsync", "-az", posters + "/", f"{HOST}:{REMOTE}/work/posters/"])
    return f"{sum(f.endswith(('.mp4','.mov','.webm')) for f in mp4s)} reels"


def restart():
    run(["ssh", HOST, f"systemctl restart {SERVICE}"])
    time.sleep(2)
    state = run(["ssh", HOST, f"systemctl is-active {SERVICE}"])
    if state != "active":
        raise StepError(f"service is {state}")
    code = run(["ssh", HOST,
                f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{PORT}/api/health"])
    return f"service active, health {code}"


def main():
    ap = argparse.ArgumentParser(description="Deploy Cat Reel Studio to the VPS.")
    ap.add_argument("--no-web", action="store_true", help="skip the web build + dist upload")
    ap.add_argument("--no-code", action="store_true", help="skip git push/pull")
    ap.add_argument("--db-only", action="store_true", help="only reconcile the SQLite store")
    ap.add_argument("--dry-run", action="store_true", help="show the plan, change nothing")
    a = ap.parse_args()

    print()
    print(f"  {lime('▮')} {bold('Cat Reel Studio')} {dim('deploy')} {dim('→')} {cyan(HOST + ':' + REMOTE)}")
    if a.dry_run:
        print(f"  {dim('dry-run — nothing will be changed')}")
    print()

    t0 = time.monotonic()
    plan = [("preflight", preflight, True)]
    if not a.db_only:
        if not a.no_web:  plan.append(("build web", build_web, False))
        if not a.no_code: plan.append(("push code → server", push_code, False))
        if not a.no_web:  plan.append(("sync web/dist", sync_web, False))
    plan.append(("sync sqlite (merge)", sync_db, True))
    if not a.db_only:
        plan.append(("sync media", sync_media, False))
    plan.append(("restart + health", restart, True))

    for label, fn, _always in plan:
        step(label, fn, dry=a.dry_run)

    el = time.monotonic() - t0
    print()
    url = "https://cats.lulzx.space"
    print(f"  {green('●')} {bold('deployed')} {dim(f'in {el:.1f}s')} {dim('·')} {cyan(url)}")
    print()


if __name__ == "__main__":
    main()
