# Garmin Coach

[Leer en español](README.es.md)

A personal training coach built on top of your own Garmin Connect data, plus an **MCP connector** so an AI assistant
(Claude) can read that data and talk about it: *"what should I do today?"*, weekly volume, recovery, charts, and
(optionally) sending a structured workout to your watch.

> **Status: personal project, shared as-is. Not a public service, and not under active development as one.**
> The reasons are explained below, because they may be useful to anyone thinking about doing something similar.

## What it does

- **Web app** (FastAPI + SQLite): daily sync from Garmin, a "today" view, weekly volume, and a daily recommendation.
- **MCP server** (`coach/mcp_app.py`, Streamable HTTP, OAuth 2.1 with a password you set): read-only tools such as
  `training_summary`, `daily_metrics`, `activities`, `activity_detail`, `weekly_volume`, `hr_zones`, `race_predictions`,
  `scheduled_workouts`, `training_plan`, `metric_series` and `pace_by_hr_zone`. The assistant is instructed to keep
  *what Garmin recommends* separate from *its own recommendation and why*, and never to invent Garmin recommendations.
- **Optional `send_workout`** (off by default, `COACH_ENABLE_SEND=1`): builds a structured running workout, shows a
  preview, and only sends it after explicit confirmation. Not exhaustively tested; review every workout before using it.
- `server.py`: a minimal local MCP server (stdio) for Claude Desktop.
- `coach/garmin_dev.py`: an experimental receiver for the Garmin Connect Developer Program push notifications
  (see "Why this is not a public service").

## Why this is not a public service

The goal was a connector anyone could add to Claude. I stopped, for reasons that are mostly about what Garmin makes
available and what it takes to operate one responsibly:

1. **What the data gives you.** The personal data this project reads (readiness, training status, load, race
   predictions, the Garmin Coach plan) comes from Garmin Connect endpoints that are **not documented** in the public
   Personal API reference (28 read-only `GET` endpoints at the time of writing). They work for your own account,
   but Garmin can change or remove them without notice, and they are not a sound base for a service for other people.
2. **The official route for multiple users is limited.** The public overview of the Garmin Connect Developer Program
   describes the Starter tier as push-only with no historical data. In my own tests with a single account, the types
   that arrive are activities, daily summaries, sleep, HRV, stress, SpO2, respiration and similar; I did not see
   readiness, training status, load or the Garmin Coach plan. A new user would start with an empty history, and
   "what does Garmin recommend today?" could not be answered.
3. **Storage and responsibility.** Push delivery means the operator must receive and store each user's health data.
   That brings data-protection duties (GDPR in my case), terms of service, and legal exposure that fall on an
   individual personally if there is no company behind the project. For a service that adds little beyond what the
   Garmin apps already show, that was not a trade I wanted to make.
4. **AI-specific terms.** Passing a user's Garmin data to an AI assistant is a use the program's rules treat with
   care. I asked Garmin for clarification and only received a generic automated reply, so I did not build on an
   assumption.

None of this is a criticism of Garmin; it is a snapshot of what I found. If you decide to build something similar,
check the current program terms yourself.

## Using it for yourself

You need your own Garmin Connect account and a server or computer you control.

```bash
python -m venv .venv
.venv/bin/pip install -r coach/requirements.txt      # Windows: .venv\Scripts\pip
python login.py                                       # one-time login; stores tokens in ~/.garmin-mcp-tokens
```

- **Local with Claude Desktop:** add an MCP server that runs `python server.py` in your `claude_desktop_config.json`.
- **Web app + remote connector:** `deploy/setup.sh` installs it on Ubuntu/Debian (Caddy for HTTPS + systemd):
  `DOMAIN=example.com bash deploy/setup.sh`, then copy your tokens to `data/tokens` and fill `.env`.
  Add the connector in Claude with `https://your-domain/mcp`; it signs in through `/oauth/login` with your password.
- `deploy/audit.sh` is a read-only server security audit; `deploy/run-as-coach.sh` runs the service as an unprivileged user.

Configuration (environment variables in `.env`):

| Variable | Purpose |
|---|---|
| `COACH_PASSWORD` | Password for the web app and the connector login |
| `SESSION_SECRET` | Cookie signing key |
| `COACH_PUBLIC_URL` | Public base URL, e.g. `https://example.com` (required for the connector) |
| `COACH_DATA` | Data directory (default `./data`) |
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY`, `COACH_PROVIDER`, `COACH_MODEL` | Only for the daily recommendation in the web app |
| `COACH_ENABLE_SEND` | `1` enables `send_workout` |
| `GARMIN_PUSH_TOKEN` | Only for the experimental push receiver |
| `PRIVACY_CONTROLLER_NAME`, `PRIVACY_CONTACT_EMAIL`, `PRIVACY_COUNTRY`, `PRIVACY_HOSTING` | Fill the privacy page |

## Important notes

- **Unofficial.** Not affiliated with, endorsed by or supported by Garmin Ltd. or Anthropic. It uses the community
  `garminconnect` library and undocumented endpoints; using it may conflict with Garmin's terms. Use it only with
  your own account and at your own risk.
- **Not medical advice.** Training suggestions are informational. Stop and see a professional if you feel unwell.
- **Security.** The repository contains no credentials. Keep `.env`, `data/` and your Garmin tokens private. The
  legal pages (`coach/legal.py`) are drafts I wrote for my own deployment and are **not** legal advice; have them
  reviewed before reusing them.
- **No licence has been added yet**, so by default all rights are reserved. Ask if you want to reuse the code.

## Contact

Questions about the project or ideas to build on it: **jaimegonzgomz@gmail.com**. If anyone at Garmin finds this idea
useful, I'm glad to talk.
