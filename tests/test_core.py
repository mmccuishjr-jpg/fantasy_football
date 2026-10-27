import tempfile
import unittest
from pathlib import Path

from sleeper_mcp.core import SleeperClient, build_snapshot


class FakeClient(SleeperClient):
    def __init__(self):
        super().__init__("league", Path(tempfile.mkdtemp()))

    def league(self):
        return {"name": "Test", "season": "2026", "settings": {"leg": 2, "draft_rounds": 1}}

    def nfl_state(self):
        return {"season": "2026", "week": 2}

    def users(self):
        return [
            {"user_id": "u1", "display_name": "Alpha", "metadata": {"team_name": "A Team"}},
            {"user_id": "u2", "display_name": "Beta", "metadata": {}},
        ]

    def rosters(self):
        return [
            {"roster_id": 1, "owner_id": "u1", "players": ["p1"], "starters": ["p1"], "settings": {"wins": 1, "losses": 1, "fpts": 200, "fpts_decimal": 25}},
            {"roster_id": 2, "owner_id": "u2", "players": ["p2"], "starters": ["p2"], "settings": {"wins": 2, "losses": 0, "fpts": 190}},
        ]

    def traded_picks(self):
        return [{"season": "2027", "round": 1, "roster_id": 1, "previous_owner_id": 1, "owner_id": 2}]

    def matchups(self, week):
        return [
            {"matchup_id": 1, "roster_id": 1, "points": 99, "starters": ["p1"]},
            {"matchup_id": 1, "roster_id": 2, "points": 100, "starters": ["p2"]},
        ]

    def transactions(self, week):
        return [{"transaction_id": f"t{week}", "type": "waiver", "status": "complete", "leg": week, "created": week, "roster_ids": [1], "adds": {"p2": 1}, "drops": {"p1": 1}}]

    def players(self, force=False):
        return {
            "p1": {"full_name": "Player One", "position": "RB", "team": "AAA"},
            "p2": {"first_name": "Player", "last_name": "Two", "position": "WR", "team": "BBB"},
        }


class SnapshotTests(unittest.TestCase):
    def test_snapshot_normalizes_and_resolves(self):
        result = build_snapshot(FakeClient(), recent_weeks=2)
        self.assertEqual([row["roster_id"] for row in result["standings"]], [2, 1])
        self.assertEqual(result["rosters"][0]["players"][0]["name"], "Player One")
        self.assertEqual(result["rosters"][0]["players"][0]["roster_slot"], "starter")
        self.assertEqual(result["traded_picks"][0]["current_owner"]["display_name"], "Beta")
        self.assertEqual(len(result["draft_picks"]), 2)
        self.assertEqual(result["draft_picks"][0]["current_owner"]["display_name"], "Beta")
        self.assertTrue(result["draft_picks"][0]["is_traded"])
        self.assertEqual(len(result["recent_matchups"]), 2)
        self.assertEqual(result["recent_transactions"][0]["adds"][0]["player"]["name"], "Player Two")


if __name__ == "__main__":
    unittest.main()

