from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional

DEFAULT_LEAGUE_ID = "1323035452969586688"
API_ROOT = "https://api.sleeper.app/v1"


class SleeperAPIError(RuntimeError):
    pass


class SleeperClient:
    """Small, read-only client for Sleeper's public GET API."""

    def __init__(
        self,
        league_id: str = DEFAULT_LEAGUE_ID,
        cache_dir: Optional[Path] = None,
        timeout: int = 30,
    ) -> None:
        self.league_id = str(league_id)
        self.cache_dir = Path(cache_dir or os.getenv("SLEEPER_CACHE_DIR", ".cache/sleeper"))
        self.timeout = timeout
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get(self, path: str) -> Any:
        url = f"{API_ROOT}/{path.lstrip('/')}"
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "sleeper-league-mcp/0.1"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise SleeperAPIError(f"Sleeper GET failed for {url}: {exc}") from exc

    def league(self) -> dict[str, Any]:
        return self._get(f"league/{self.league_id}")

    def nfl_state(self) -> dict[str, Any]:
        return self._get("state/nfl")

    def users(self) -> list[dict[str, Any]]:
        return self._get(f"league/{self.league_id}/users")

    def rosters(self) -> list[dict[str, Any]]:
        return self._get(f"league/{self.league_id}/rosters")

    def traded_picks(self) -> list[dict[str, Any]]:
        return self._get(f"league/{self.league_id}/traded_picks")

    def matchups(self, week: int) -> list[dict[str, Any]]:
        return self._get(f"league/{self.league_id}/matchups/{int(week)}")

    def transactions(self, week: int) -> list[dict[str, Any]]:
        return self._get(f"league/{self.league_id}/transactions/{int(week)}")

    def players(self, force: bool = False) -> dict[str, dict[str, Any]]:
        """Fetch the large player map at most once per day unless forced."""
        cache_path = self.cache_dir / "players_nfl.json"
        if not force and cache_path.exists() and time.time() - cache_path.stat().st_mtime < 86400:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        players = self._get("players/nfl")
        _atomic_write(cache_path, players)
        return players


def _atomic_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def _points(settings: dict[str, Any], prefix: str) -> float:
    return float(settings.get(prefix, 0) or 0) + float(settings.get(f"{prefix}_decimal", 0) or 0) / 100


def _owner_label(user: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not user:
        return {"user_id": None, "display_name": "Orphaned roster", "team_name": None}
    metadata = user.get("metadata") or {}
    return {
        "user_id": user.get("user_id"),
        "display_name": user.get("display_name") or user.get("username"),
        "team_name": metadata.get("team_name"),
    }


def _player(player_id: str, player_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    raw = player_map.get(str(player_id), {})
    full_name = raw.get("full_name") or " ".join(
        part for part in (raw.get("first_name"), raw.get("last_name")) if part
    )
    if not full_name:
        full_name = str(player_id) if len(str(player_id)) <= 4 and str(player_id).isalpha() else "Unknown player"
    return {
        "player_id": str(player_id),
        "name": full_name,
        "position": raw.get("position"),
        "team": raw.get("team"),
        "status": raw.get("status"),
        "injury_status": raw.get("injury_status"),
    }


def _resolved_ids(ids: Optional[Iterable[str]], player_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [_player(str(player_id), player_map) for player_id in (ids or [])]


def _week_range(current_week: int, count: int) -> list[int]:
    start = max(1, current_week - max(1, count) + 1)
    return list(range(start, current_week + 1))


def build_snapshot(
    client: SleeperClient,
    recent_weeks: int = 3,
    include_players: bool = True,
    force_players: bool = False,
) -> dict[str, Any]:
    league = client.league()
    state = client.nfl_state()
    users = client.users()
    rosters = client.rosters()
    traded_picks = client.traded_picks()
    player_map = client.players(force=force_players) if include_players else {}

    by_user = {str(user.get("user_id")): user for user in users}
    roster_owner: dict[int, dict[str, Any]] = {}
    roster_rows: list[dict[str, Any]] = []
    for roster in rosters:
        roster_id = int(roster["roster_id"])
        owner = _owner_label(by_user.get(str(roster.get("owner_id"))))
        roster_owner[roster_id] = owner
        starters = {str(value) for value in (roster.get("starters") or [])}
        reserve = {str(value) for value in (roster.get("reserve") or [])}
        taxi = {str(value) for value in (roster.get("taxi") or [])}
        resolved = []
        for entry in _resolved_ids(roster.get("players"), player_map):
            player_id = entry["player_id"]
            entry["roster_slot"] = (
                "starter" if player_id in starters else "reserve" if player_id in reserve else "taxi" if player_id in taxi else "bench"
            )
            resolved.append(entry)
        settings = roster.get("settings") or {}
        roster_rows.append(
            {
                "roster_id": roster_id,
                "owner": owner,
                "co_owners": [
                    _owner_label(by_user.get(str(user_id))) for user_id in (roster.get("co_owners") or [])
                ],
                "record": {
                    "wins": int(settings.get("wins", 0) or 0),
                    "losses": int(settings.get("losses", 0) or 0),
                    "ties": int(settings.get("ties", 0) or 0),
                    "points_for": _points(settings, "fpts"),
                    "points_against": _points(settings, "fpts_against"),
                    "potential_points": _points(settings, "ppts"),
                },
                "players": resolved,
            }
        )

    standings = sorted(
        (
            {
                "roster_id": row["roster_id"],
                "owner": row["owner"],
                **row["record"],
            }
            for row in roster_rows
        ),
        key=lambda row: (-row["wins"], row["losses"], -row["points_for"], row["roster_id"]),
    )
    for rank, row in enumerate(standings, start=1):
        row["rank"] = rank

    picks = []
    for pick in traded_picks:
        picks.append(
            {
                **pick,
                "original_owner": roster_owner.get(int(pick["roster_id"]), {"display_name": "Unknown"}),
                "current_owner": roster_owner.get(int(pick["owner_id"]), {"display_name": "Unknown"}),
                "previous_owner": roster_owner.get(int(pick["previous_owner_id"]), {"display_name": "Unknown"}),
            }
        )
    picks.sort(key=lambda row: (int(row["season"]), int(row["round"]), int(row["roster_id"])))

    # Sleeper only returns picks whose ownership changed. Reconstruct complete
    # inventories for every season present in that feed, retaining the raw list too.
    transferred = {
        (str(pick["season"]), int(pick["round"]), int(pick["roster_id"])): int(pick["owner_id"])
        for pick in traded_picks
    }
    seasons = sorted({str(pick["season"]) for pick in traded_picks})
    draft_rounds = int((league.get("settings") or {}).get("draft_rounds") or 0)
    draft_picks = []
    for season in seasons:
        for original_roster_id in sorted(roster_owner):
            for round_number in range(1, draft_rounds + 1):
                current_roster_id = transferred.get(
                    (season, round_number, original_roster_id), original_roster_id
                )
                draft_picks.append(
                    {
                        "season": season,
                        "round": round_number,
                        "original_roster_id": original_roster_id,
                        "original_owner": roster_owner[original_roster_id],
                        "current_roster_id": current_roster_id,
                        "current_owner": roster_owner.get(current_roster_id, {"display_name": "Unknown"}),
                        "is_traded": current_roster_id != original_roster_id,
                    }
                )

    league_week = int((league.get("settings") or {}).get("leg") or state.get("leg") or state.get("week") or 1)
    weeks = _week_range(league_week, recent_weeks)
    matchup_rows = []
    transaction_rows = []
    for week in weeks:
        teams = client.matchups(week)
        groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for team in teams:
            groups[team.get("matchup_id")].append(
                {
                    "roster_id": team.get("roster_id"),
                    "owner": roster_owner.get(int(team["roster_id"]), {"display_name": "Unknown"}),
                    "points": team.get("custom_points") if team.get("custom_points") is not None else team.get("points"),
                    "starters": _resolved_ids(team.get("starters"), player_map),
                }
            )
        matchup_rows.append(
            {"week": week, "matchups": [{"matchup_id": key, "teams": value} for key, value in sorted(groups.items(), key=lambda x: (x[0] is None, x[0]))]}
        )

        for transaction in client.transactions(week):
            transaction_rows.append(_resolve_transaction(transaction, roster_owner, player_map))
    transaction_rows.sort(key=lambda row: int(row.get("created") or 0), reverse=True)

    return {
        "meta": {
            "generated_at_unix": int(time.time()),
            "league_id": client.league_id,
            "source": "Sleeper public read-only API",
            "recent_weeks": weeks,
            "players_resolved": include_players,
        },
        "league": league,
        "nfl_state": state,
        "users": users,
        "rosters": roster_rows,
        "standings": standings,
        "traded_picks": picks,
        "draft_picks": draft_picks,
        "recent_matchups": matchup_rows,
        "recent_transactions": transaction_rows,
    }


def _resolve_transaction(
    transaction: dict[str, Any],
    roster_owner: dict[int, dict[str, Any]],
    player_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    adds = transaction.get("adds") or {}
    drops = transaction.get("drops") or {}
    return {
        "transaction_id": transaction.get("transaction_id"),
        "type": transaction.get("type"),
        "status": transaction.get("status"),
        "week": transaction.get("leg"),
        "created": transaction.get("created"),
        "rosters": [
            {"roster_id": roster_id, "owner": roster_owner.get(int(roster_id), {"display_name": "Unknown"})}
            for roster_id in (transaction.get("roster_ids") or [])
        ],
        "adds": [{"roster_id": roster_id, "player": _player(player_id, player_map)} for player_id, roster_id in adds.items()],
        "drops": [{"roster_id": roster_id, "player": _player(player_id, player_map)} for player_id, roster_id in drops.items()],
        "draft_picks": transaction.get("draft_picks") or [],
        "waiver_budget": transaction.get("waiver_budget") or [],
    }


def load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    _atomic_write(path, snapshot)

