# Sleeper league — persistent read-only connection

This project connects league `1323035452969586688` ("Thousand Dollar Bet") to Sleeper's public, read-only API. It supports live league details, rosters, user-to-owner mapping, player ID resolution, future pick ownership, transactions, standings, and recent matchups. It contains **no write endpoint and no trade, waiver, lineup, or commissioner action**.

## What is included

- `sleeper-refresh`: saves a normalized JSON snapshot for immediate/reusable analysis.
- `sleeper-mcp`: exposes the same live data as six read-only MCP tools over Streamable HTTP at `/mcp`.
- A 24-hour local cache for Sleeper's large NFL player map, per Sleeper's request to download it no more than once daily.
- The three uploaded exports under `data/seed/` as an offline starting point.
- A Dockerfile and `render.yaml` for a small hosted service.

## Fastest local setup

Python 3.10+ is required. The built-in Python on some older Macs is 3.9, so install a current Python first if needed.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
sleeper-refresh
```

The refreshed league data will be at `data/snapshot.json`. Run the same `sleeper-refresh` command any time you want a fresh copy. Use `sleeper-refresh --recent-weeks 6` for a wider window, or `--no-players` for a quicker ID-only refresh.

## Run the MCP server locally

```bash
source .venv/bin/activate
sleeper-mcp
```

The MCP endpoint is `http://localhost:8000/mcp`. Every tool fetches current Sleeper data when invoked. The player dictionary is cached for 24 hours; everything else is live.

Test it with MCP Inspector:

```bash
npx @modelcontextprotocol/inspector@latest
```

Choose Streamable HTTP and enter `http://localhost:8000/mcp`.

## Connect it to ChatGPT

There are two supported connection shapes:

1. **Hosted HTTPS (persistent):** deploy this Docker service to Render, Fly.io, Railway, or another HTTPS host. The connection URL will be `https://YOUR-HOST/mcp`.
2. **Secure MCP Tunnel / development tunnel:** keep the server on your laptop and connect through a Secure MCP Tunnel if your ChatGPT workspace offers it, or temporarily expose port 8000 with an HTTPS tunnel for development.

In ChatGPT on the web, open **Plugins**, press **+**, choose **Add custom MCP server**, and enter the HTTPS URL ending in `/mcp` (or select Tunnel). Choose **No authentication** only if you are comfortable with the public endpoint being callable by anyone who knows its URL; otherwise put the deployment behind supported OAuth. Create it as a plugin, install it, then `@`-mention it in a new chat.

Availability is controlled by the ChatGPT account/workspace and its security policies. If **Add custom MCP server** is absent, the live-refresh command still provides the same current data as a portable JSON file; do not assume the MCP feature can be enabled from this project.

After changing MCP tool names or descriptions, restart/deploy the server, open the plugin's details page, choose **Refresh**, and test again in a new chat.

## Suggested prompts

- `@Sleeper League show the current standings and playoff race.`
- `@Sleeper League list roster 4 with resolved player names and slots.`
- `@Sleeper League summarize the last three weeks of transactions.`
- `@Sleeper League show who currently owns every 2027 first-round pick.`
- `@Sleeper League compare this week's matchups. Do not perform any roster changes.`

## Read-only guarantees

- The upstream Sleeper client implements HTTP `GET` only.
- Sleeper's public API itself is read-only and requires no token.
- No mutation tool is registered with MCP.
- Trades are visible only as transaction history and pick ownership; they cannot be proposed, accepted, or executed here.

Sleeper's traded-picks endpoint lists only picks whose ownership changed. The snapshot reconstructs a complete pick inventory for every returned future season by combining native ownership with those transfers.

## Important files

- `src/sleeper_mcp/core.py` — Sleeper API client and normalization.
- `src/sleeper_mcp/server.py` — read-only MCP tools.
- `src/sleeper_mcp/refresh.py` — one-command snapshot refresh.
- `tests/test_core.py` — normalization and resolution tests.

