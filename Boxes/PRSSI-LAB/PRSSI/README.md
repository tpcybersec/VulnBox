# PRSSI — Private Reactive Session Service Interface

A small Flask web application that serves as the backend for the
**Notes & Nonsense** personal blog. It provides cookie-based session
authentication, a feedback endpoint (with an optional admin-bot URL
visitor), and a private page that authenticated users can view.

## Features

- **Login / Register** — submit any username and password. If the
  account does not exist, it is created automatically. Sessions are
  cookie-based and signed with the Flask `SECRET_KEY`.
- **Private page** (`/flag`) — authenticated users see a centered input
  box containing their private value. The page is rendered with a
  gradient background and a clean layout.
- **Feedback page** (`/feedback`) — anyone (logged in or not) can submit
  a name, email, message, and an optional URL. Submissions are stored
  for the site owner. When a URL is included, a headless browser is
  launched in the background to log in as admin and visit the link as
  a sanity check.
- **Admin role** — only the `admin` user, logging in from `localhost`,
  sees the real value from `flag.txt`. Other users see a random
  placeholder. Admin login from any other IP is blocked.

## Tech Stack

- Python 3.11+
- Flask 3.0
- Gunicorn (production server)
- Playwright + headless Chromium (for the feedback URL visitor)
- Docker / docker-compose (optional)

## Project Layout

```
.
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
├── app.py                  # Flask application
├── flag.txt                # The private value
├── templates/
│   ├── base.html
│   ├── index.html          # Home page (blog landing)
│   ├── login.html
│   ├── register.html
│   ├── flag.html           # Private page (login required)
│   └── feedback.html       # Feedback form with optional URL
└── static/
    ├── style.css           # Stylesheet for the /flag page
    └── css/app.css         # Global app styling
```

## How to Run

### With Docker

```bash
docker compose -f docker-compose.yaml up --build -d
```

The app listens on `http://localhost:5000`.

### Without Docker

```bash
pip install -r requirements.txt
playwright install chromium
python app.py
```

## Configuration

| Environment variable | Default | Description |
|---------------------|---------|-------------|
| `SECRET_KEY`        | `dev-secret-key-...` | Flask session secret. Set this in production. |
| `FLAG_PATH`         | `/app/flag.txt` (Docker) or `./flag.txt` | Path to the value file. |

## Pages

| URL | Purpose |
|-----|---------|
| `/` | Home page (blog landing) |
| `/login` | Login form (also auto-registers) |
| `/register` | Register form |
| `/flag` | Private page (login required) |
| `/flag/<subpath>` | Same page, served under any subpath |
| `/feedback` | Feedback form with optional URL visitor |

## How the Feedback URL Visitor Works

When a feedback submission includes a URL, the server launches a
background thread that:

1. Starts a headless Chromium via Playwright.
2. Opens `http://127.0.0.1:5000/login` and submits the form with the
   default admin credentials (admin login is only allowed from localhost,
   which is true inside the container).
3. Navigates to the user-submitted URL with the admin session attached.
4. Logs the status, response length, and whether the private value
   appeared in the response body.

The visitor is asynchronous — the user sees the feedback confirmation
immediately while the visit happens in the background. Results are
written to the container stdout (`[admin-bot] ...` lines).

## Replacing the Private Value

Edit `flag.txt` and restart the app:

```bash
docker compose -f docker-compose.yaml restart
```

## Resetting the User Store

Users are stored in memory. Restart the container to wipe users:

```bash
docker compose -f docker-compose.yaml restart
```

To wipe everything (including the value file content, if you want to
change it):

```bash
docker compose -f docker-compose.yaml down --volumes
```