from flask import Blueprint, jsonify, session

from ...extensions import db
from ...models.stats import UserStats

stats_bp = Blueprint("stats", __name__)


@stats_bp.get("/me")
def my_stats():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "not_authenticated"}), 401

    stats = db.session.get(UserStats, user_id)
    if stats is None:
        return jsonify(
            {
                "games_played": 0,
                "games_won": 0,
                "win_distribution": {},
                "current_streak": 0,
                "max_streak": 0,
            }
        )
    return jsonify(
        {
            "games_played": stats.games_played,
            "games_won": stats.games_won,
            "win_distribution": stats.win_distribution,
            "current_streak": stats.current_streak,
            "max_streak": stats.max_streak,
        }
    )
