from __future__ import annotations

import argparse
from pathlib import Path

from .core import DEFAULT_LEAGUE_ID, SleeperClient, build_snapshot, save_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh a read-only Sleeper league snapshot")
    parser.add_argument("--league-id", default=DEFAULT_LEAGUE_ID)
    parser.add_argument("--output", type=Path, default=Path("data/snapshot.json"))
    parser.add_argument("--recent-weeks", type=int, default=3)
    parser.add_argument("--no-players", action="store_true", help="Skip the large player-ID map")
    parser.add_argument("--force-players", action="store_true", help="Ignore the 24-hour player cache")
    args = parser.parse_args()

    snapshot = build_snapshot(
        SleeperClient(args.league_id),
        recent_weeks=args.recent_weeks,
        include_players=not args.no_players,
        force_players=args.force_players,
    )
    save_snapshot(args.output, snapshot)
    print(f"Saved {args.output} for {args.league_id}")


if __name__ == "__main__":
    main()

