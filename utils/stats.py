from __future__ import annotations

from collections import Counter


def compute_stats(matches_data: dict, name: str, tag: str) -> dict:
    """Process raw v4 matches JSON into computed stats.

    Args:
        matches_data: Raw JSON dict from HenrikClient.get_matches().
        name: Player's Riot name (used to locate them in each match).
        tag:  Player's Riot tag.

    Returns:
        Stats dict consumed by banter.engine.generate_banter() and
        the embed builders in cogs/stats.py. Returns a zeroed dict
        with games=0 if the player has no visible match history.
    """
    matches = matches_data.get("data", [])

    if not matches:
        return _empty_stats(name)

    total_kills = 0
    total_deaths = 0
    total_assists = 0
    total_headshots = 0
    total_bodyshots = 0
    total_legshots = 0
    total_score = 0
    total_rounds = 0
    wins = 0
    agent_counter: Counter[str] = Counter()
    games_counted = 0

    for match in matches:
        players = match.get("players", [])

        player = _find_player(players, name, tag)
        if player is None:
            continue

        games_counted += 1

        stats = player.get("stats", {})
        kills = stats.get("kills", 0)
        deaths = stats.get("deaths", 0)
        assists = stats.get("assists", 0)
        headshots = stats.get("headshots", 0)
        bodyshots = stats.get("bodyshots", 0)
        legshots = stats.get("legshots", 0)
        score = stats.get("score", 0)

        total_kills += kills
        total_deaths += deaths
        total_assists += assists
        total_headshots += headshots
        total_bodyshots += bodyshots
        total_legshots += legshots
        total_score += score

        agent_name = player.get("agent", {}).get("name", "Unknown")
        agent_counter[agent_name] += 1

        player_team_id = player.get("team_id", "")
        for team in match.get("teams", []):
            if team.get("team_id") == player_team_id:
                if team.get("won"):
                    wins += 1
                rounds = team.get("rounds", {})
                total_rounds += rounds.get("won", 0) + rounds.get("lost", 0)
                break

    if games_counted == 0:
        return _empty_stats(name)

    total_shots = total_headshots + total_bodyshots + total_legshots
    losses = games_counted - wins

    return {
        "name": name,
        "kda": round((total_kills + total_assists) / max(total_deaths, 1), 2),
        "hs": round(total_headshots / max(total_shots, 1) * 100, 1),
        "wr": round(wins / games_counted * 100, 1),
        "acs": round(total_score / max(total_rounds, 1), 1),
        "wins": wins,
        "losses": losses,
        "games": games_counted,
        "avg_kills": round(total_kills / games_counted, 1),
        "avg_deaths": round(total_deaths / games_counted, 1),
        "avg_assists": round(total_assists / games_counted, 1),
        "top_agent": agent_counter.most_common(1)[0][0] if agent_counter else "Unknown",
    }


def _find_player(players: list, name: str, tag: str) -> dict | None:
    name_lower = name.lower()
    tag_lower = tag.lower()
    for player in players:
        if (
            player.get("name", "").lower() == name_lower
            and player.get("tag", "").lower() == tag_lower
        ):
            return player
    return None


def _empty_stats(name: str) -> dict:
    return {
        "name": name,
        "kda": 0.0,
        "hs": 0.0,
        "wr": 0.0,
        "acs": 0.0,
        "wins": 0,
        "losses": 0,
        "games": 0,
        "avg_kills": 0.0,
        "avg_deaths": 0.0,
        "avg_assists": 0.0,
        "top_agent": "Unknown",
    }
