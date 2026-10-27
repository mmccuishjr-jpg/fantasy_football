from __future__ import annotations

import os
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .core import DEFAULT_LEAGUE_ID, SleeperClient, build_snapshot

LEAGUE_ID = os.getenv("SLEEPER_LEAGUE_ID", DEFAULT_LEAGUE_ID)
RECENT_WEEKS = int(os.getenv("SLEEPER_RECENT_WEEKS", "3"))

mcp = FastMCP(
    "Sleeper League (read-only)",
    instructions=(
        "Read-only access to one Sleeper fantasy football league. "
        "All tools issue public GET requests only. No trade, waiver, lineup, or league mutation is supported."
    ),
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "8000")),
    stateless_http=True,
    json_response=True,
)


def _snapshot(recent_weeks: int = RECENT_WEEKS) -> dict[str, Any]:
    return build_snapshot(SleeperClient(LEAGUE_ID), recent_weeks=recent_weeks)


@mcp.tool()
def league_overview() -> dict[str, Any]:
    """Use this for league rules, season/week status, teams, standings, and a compact live overview. Read-only."""
    data = _snapshot()
    league = data["league"]
    return {
        "meta": data["meta"],
        "name": league.get("name"),
        "season": league.get("season"),
        "status": league.get("status"),
        "roster_positions": league.get("roster_positions"),
        "scoring_settings": league.get("scoring_settings"),
        "league_settings": league.get("settings"),
        "standings": data["standings"],
    }


@mcp.tool()
def get_rosters(roster_id: Optional[int] = None) -> list[dict[str, Any]]:
    """Use this for current rosters, owner mapping, resolved player names, starter/bench/reserve/taxi slots. Read-only."""
    rows = _snapshot()["rosters"]
    return [row for row in rows if roster_id is None or row["roster_id"] == roster_id]


@mcp.tool()
def get_standings() -> list[dict[str, Any]]:
    """Use this for current rank, records, points for/against, and potential points. Read-only."""
    return _snapshot()["standings"]


@mcp.tool()
def get_traded_picks(roster_id: Optional[int] = None, season: Optional[str] = None) -> list[dict[str, Any]]:
    """Use this for complete future pick ownership, including native and traded picks. Read-only; does not propose or execute trades."""
    rows = _snapshot()["draft_picks"]
    return [
        row
        for row in rows
        if (roster_id is None or int(row["current_roster_id"]) == roster_id or int(row["original_roster_id"]) == roster_id)
        and (season is None or str(row["season"]) == str(season))
    ]


@mcp.tool()
def get_recent_transactions(week: Optional[int] = None, transaction_type: Optional[str] = None) -> list[dict[str, Any]]:
    """Use this for completed/recent trades, waivers, and free-agent moves with resolved players. Read-only."""
    rows = _snapshot()["recent_transactions"]
    return [
        row
        for row in rows
        if (week is None or int(row.get("week") or 0) == week)
        and (transaction_type is None or row.get("type") == transaction_type)
    ]


@mcp.tool()
def get_recent_matchups(week: Optional[int] = None) -> list[dict[str, Any]]:
    """Use this for recent weekly matchups, scores, owners, and resolved starters. Read-only."""
    rows = _snapshot()["recent_matchups"]
    return [row for row in rows if week is None or row["week"] == week]


@mcp.tool()
def refresh_league(recent_weeks: int = RECENT_WEEKS) -> dict[str, Any]:
    """Fetch fresh league data from Sleeper now and return the full normalized snapshot. Read-only GET requests only."""
    return _snapshot(max(1, min(int(recent_weeks), 18)))


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()

