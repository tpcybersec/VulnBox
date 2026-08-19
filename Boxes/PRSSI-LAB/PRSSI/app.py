"""PRSSI — Private Reactive Session Service Interface.

A small Flask backend for the "Notes & Nonsense" personal blog.
"""
import hashlib
import os
import random
import string
import threading
import time
from urllib.parse import unquote

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "dev-secret-key-replace-in-production-please-32bytes",
)


@app.context_processor
def inject_user():
    return {"user": session.get("username")}


users: dict = {}


def _load_flag() -> str:
    for path in (
        os.environ.get("FLAG_PATH"),
        "/app/flag.txt",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "flag.txt"),
    ):
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as _f:
                return _f.read().strip()
    raise FileNotFoundError(
        "flag.txt not found. Set FLAG_PATH or place flag.txt next to app.py."
    )


FLAG = _load_flag()


def _random_flag() -> str:
    alphabet = string.ascii_lowercase + string.digits + "_"
    body = "".join(random.choice(alphabet) for _ in range(random.randint(28, 36)))
    return f"FLAG{{{body}}}"


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"


def _is_localhost() -> bool:
    return (request.remote_addr or "").strip() in ("127.0.0.1", "::1", "localhost")


def _ensure_admin() -> None:
    if ADMIN_USERNAME not in users:
        users[ADMIN_USERNAME] = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()


_ensure_admin()


@app.route("/")
def index():
    return render_template("index.html", user=session.get("username"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "username" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template(
                "register.html",
                error="Username and password are required",
                username=username,
            )

        # Generic error: do not reveal that 'admin' is special or that
        # registration is restricted by source IP.
        if username == ADMIN_USERNAME and not _is_localhost():
            return render_template(
                "register.html",
                error="Username or password not valid",
                username=username,
            ), 403

        password_hash = hashlib.sha256(password.encode()).hexdigest()

        if username in users:
            if users[username] == password_hash:
                session["username"] = username
                return redirect(url_for("flag"))
            users[username] = password_hash
        else:
            users[username] = password_hash

        session["username"] = username
        return redirect(url_for("flag"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "username" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template(
                "login.html",
                error="Username and password are required",
                username=username,
            )

        # Generic error: do not reveal that 'admin' is special or that
        # login is restricted by source IP.
        if username == ADMIN_USERNAME and not _is_localhost():
            return render_template(
                "login.html",
                error="Invalid username or password",
                username=username,
            ), 403

        password_hash = hashlib.sha256(password.encode()).hexdigest()

        if username not in users:
            users[username] = password_hash
            session["username"] = username
            return redirect(url_for("flag"))

        if users[username] != password_hash:
            return render_template(
                "login.html",
                error="Invalid password",
                username=username,
            )

        session["username"] = username
        return redirect(url_for("flag"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("index"))


feedback_log: list = []


@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        url = request.form.get("url", "").strip()

        if not name or not message:
            return render_template(
                "feedback.html",
                error="Name and message are required.",
                submitted_name=name,
                submitted_email=email,
                submitted_message=message,
                submitted_url=url,
            )

        feedback_log.append({
            "name": name,
            "email": email,
            "message": message,
            "url": url,
            "timestamp": time.time(),
        })

        if url:
            if not url.startswith(("http://", "https://")):
                url = request.host_url.rstrip("/") + (
                    url if url.startswith("/") else "/" + url
                )
            threading.Thread(
                target=_admin_bot_visit,
                args=(url,),
                daemon=True,
            ).start()

        return render_template(
            "feedback.html",
            success=True,
            submitted_name=name,
            submitted_email=email,
        )

    return render_template("feedback.html")


def _admin_bot_visit(url: str) -> None:
    print(f"[admin-bot] starting visit to {url}", flush=True)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        print(f"[admin-bot] playwright not installed: {e}", flush=True)
        return

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            try:
                context = browser.new_context()
                page = context.new_page()
                page.goto("http://127.0.0.1:5000/login", wait_until="networkidle", timeout=15000)
                page.fill('input[name="username"]', ADMIN_USERNAME)
                page.fill('input[name="password"]', ADMIN_PASSWORD)
                page.click('button[type="submit"]')
                page.wait_for_load_state("networkidle")

                response = page.goto(url, wait_until="networkidle", timeout=15000)
                content = page.content()
                print(
                    f"[admin-bot] visited {url} status={response.status if response else 0} "
                    f"len={len(content)} contains_flag={FLAG in content}",
                    flush=True,
                )
            finally:
                browser.close()
    except Exception as e:
        print(f"[admin-bot] error visiting {url}: {e}", flush=True)


def _flag_for_current_user() -> str:
    if session.get("username") == ADMIN_USERNAME and _is_localhost():
        return FLAG
    return _random_flag()


@app.route("/flag")
def flag():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("flag.html", flag=_flag_for_current_user(), subpath="")


@app.route("/flag/<path:subpath>")
def flag_subpath(subpath):
    if "static" in subpath or subpath.endswith(".css"):
        abort(404)
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("flag.html", flag=_flag_for_current_user(), subpath=subpath)


@app.errorhandler(404)
def not_found(e):
    safe_path = (
        unquote(request.path)
        .replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>404 — {safe_path}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}

:root {{
    --bg-1: #0f0c29;
    --bg-2: #302b63;
    --bg-3: #24243e;
    --accent: #ff5e7e;
    --accent-2: #6dd5ed;
    --text: #e8e8f0;
    --text-dim: #9a9bb0;
}}

html, body {{
    height: 100%;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: var(--text);
    background: linear-gradient(135deg, var(--bg-1) 0%, var(--bg-2) 50%, var(--bg-3) 100%);
    background-size: 200% 200%;
    animation: gradientShift 15s ease infinite;
}}

@keyframes gradientShift {{
    0%, 100% {{ background-position: 0% 50%; }}
    50% {{ background-position: 100% 50%; }}
}}

body {{
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    position: relative;
}}

.blob {{
    position: absolute;
    border-radius: 50%;
    filter: blur(60px);
    opacity: 0.4;
    animation: float 20s ease-in-out infinite;
    pointer-events: none;
}}

.blob.b1 {{
    width: 400px; height: 400px;
    background: var(--accent);
    top: -100px; left: -100px;
    animation-delay: 0s;
}}

.blob.b2 {{
    width: 350px; height: 350px;
    background: var(--accent-2);
    bottom: -100px; right: -100px;
    animation-delay: -7s;
}}

.blob.b3 {{
    width: 300px; height: 300px;
    background: #c471f5;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    animation-delay: -14s;
    opacity: 0.25;
}}

@keyframes float {{
    0%, 100% {{ transform: translate(0, 0) scale(1); }}
    33%      {{ transform: translate(50px, -30px) scale(1.1); }}
    66%      {{ transform: translate(-30px, 50px) scale(0.9); }}
}}

.container {{
    position: relative;
    z-index: 1;
    text-align: center;
    padding: 32px;
    max-width: 800px;
    width: 90%;
}}

.code {{
    font-size: clamp(120px, 22vw, 220px);
    font-weight: 800;
    line-height: 1;
    letter-spacing: -0.05em;
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    position: relative;
    display: inline-block;
    animation: glitch 4s infinite;
    margin-bottom: 16px;
}}

.code::before, .code::after {{
    content: '404';
    position: absolute;
    top: 0; left: 0;
    width: 100%;
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    opacity: 0.5;
}}

.code::before {{
    animation: glitchTop 3s infinite linear alternate-reverse;
    clip-path: polygon(0 0, 100% 0, 100% 33%, 0 33%);
}}

.code::after {{
    animation: glitchBottom 2.5s infinite linear alternate-reverse;
    clip-path: polygon(0 67%, 100% 67%, 100% 100%, 0 100%);
}}

@keyframes glitch {{
    0%, 90%, 100% {{ transform: translate(0); }}
    92% {{ transform: translate(-2px, 1px); }}
    94% {{ transform: translate(2px, -1px); }}
    96% {{ transform: translate(-1px, 2px); }}
    98% {{ transform: translate(1px, -2px); }}
}}

@keyframes glitchTop {{
    0%, 100% {{ transform: translate(0); }}
    25% {{ transform: translate(-2px, 0); }}
    50% {{ transform: translate(2px, 0); }}
    75% {{ transform: translate(-1px, 0); }}
}}

@keyframes glitchBottom {{
    0%, 100% {{ transform: translate(0); }}
    25% {{ transform: translate(2px, 0); }}
    50% {{ transform: translate(-2px, 0); }}
    75% {{ transform: translate(-1px, 0); }}
}}

.title {{
    font-size: clamp(20px, 3vw, 28px);
    font-weight: 600;
    margin-bottom: 12px;
    letter-spacing: -0.02em;
}}

.subtitle {{
    color: var(--text-dim);
    font-size: 15px;
    margin-bottom: 32px;
    line-height: 1.6;
}}

.path-box {{
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 16px 20px;
    margin: 24px 0;
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
    position: relative;
    overflow: hidden;
    text-align: left;
}}

.path-box::before {{
    content: '';
    position: absolute;
    top: 0; left: -100%;
    width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.05), transparent);
    animation: shimmer 3s infinite;
}}

@keyframes shimmer {{
    0% {{ left: -100%; }}
    100% {{ left: 100%; }}
}}

.path-label {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--accent-2);
    margin-bottom: 8px;
    font-weight: 600;
}}

.path-value {{
    font-family: "SF Mono", Monaco, Menlo, Consolas, monospace;
    font-size: 13px;
    color: var(--text);
    word-break: break-all;
    line-height: 1.5;
}}

.actions {{
    display: flex;
    gap: 12px;
    justify-content: center;
    margin-top: 32px;
    flex-wrap: wrap;
}}

.btn {{
    padding: 12px 24px;
    border-radius: 10px;
    text-decoration: none;
    font-size: 14px;
    font-weight: 500;
    transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    cursor: pointer;
}}

.btn-primary {{
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
    color: #fff;
    box-shadow: 0 4px 16px rgba(255, 94, 126, 0.3);
}}

.btn-primary:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(255, 94, 126, 0.4);
}}

.btn-ghost {{
    background: rgba(255, 255, 255, 0.05);
    color: var(--text);
    backdrop-filter: blur(10px);
}}

.btn-ghost:hover {{
    background: rgba(255, 255, 255, 0.1);
    transform: translateY(-2px);
}}

.particle {{
    position: absolute;
    width: 4px;
    height: 4px;
    background: var(--accent);
    border-radius: 50%;
    pointer-events: none;
    animation: rise 8s infinite linear;
    opacity: 0;
}}

@keyframes rise {{
    0%   {{ transform: translateY(100vh) translateX(0); opacity: 0; }}
    10%  {{ opacity: 1; }}
    90%  {{ opacity: 1; }}
    100% {{ transform: translateY(-100vh) translateX(100px); opacity: 0; }}
}}

.status {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 99px;
    background: rgba(255, 94, 126, 0.1);
    border: 1px solid rgba(255, 94, 126, 0.3);
    color: var(--accent);
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 24px;
}}

.status-dot {{
    width: 6px; height: 6px;
    background: var(--accent);
    border-radius: 50%;
    animation: pulse 1.5s ease-in-out infinite;
}}

@keyframes pulse {{
    0%, 100% {{ opacity: 1; transform: scale(1); }}
    50%      {{ opacity: 0.5; transform: scale(1.3); }}
}}

@media (max-width: 540px) {{
    .code {{ font-size: 100px; }}
}}
</style>
</head>
<body>
    <div class="blob b1"></div>
    <div class="blob b2"></div>
    <div class="blob b3"></div>

    <div class="container">
        <div class="status">
            <span class="status-dot"></span>
            404 Not Found
        </div>

        <div class="code">404</div>
        <h1 class="title">Page not found</h1>
        <p class="subtitle">The page you're looking for doesn't exist or has been moved.</p>

        <div class="path-box">
            <div class="path-label">Requested path</div>
            <div class="path-value">{safe_path}</div>
        </div>

        <div class="actions">
            <a href="/" class="btn btn-primary">← Go home</a>
            <a href="javascript:history.back()" class="btn btn-ghost">Go back</a>
        </div>
    </div>

    <script>
        for (let i = 0; i < 20; i++) {{
            const p = document.createElement('div');
            p.className = 'particle';
            p.style.left = Math.random() * 100 + 'vw';
            p.style.animationDelay = Math.random() * 8 + 's';
            p.style.animationDuration = (6 + Math.random() * 6) + 's';
            p.style.background = ['#ff5e7e', '#6dd5ed', '#c471f5'][Math.floor(Math.random() * 3)];
            document.body.appendChild(p);
        }}
    </script>
</body>
</html>
"""
    return body, 200, {"Content-Type": "text/html; charset=utf-8"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)