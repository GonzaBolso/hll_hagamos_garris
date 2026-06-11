"""
db/database.py  – Conexión y operaciones con PostgreSQL via psycopg2
"""
import logging
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PgConnection

from config.settings import settings

logger = logging.getLogger(__name__)


def get_connection() -> PgConnection:
    return psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )


@contextmanager
def db_cursor(commit: bool = True):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Crea todas las tablas e índices si no existen."""
    import os
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        sql = f.read()
    with db_cursor() as cur:
        cur.execute(sql)
    logger.info("Base de datos inicializada correctamente.")


# ──────────────────────────────────────────────
# Upserts
# ──────────────────────────────────────────────

def upsert_player(player_id: str, name: str, steam_name: str | None,
                  country: str | None, level: int | None) -> None:
    sql = """
        INSERT INTO players (player_id, name, steam_name, country, level, last_seen_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (player_id) DO UPDATE SET
            name         = EXCLUDED.name,
            steam_name   = COALESCE(EXCLUDED.steam_name, players.steam_name),
            country      = COALESCE(EXCLUDED.country, players.country),
            level        = GREATEST(EXCLUDED.level, players.level),
            last_seen_at = NOW()
    """
    with db_cursor() as cur:
        cur.execute(sql, (player_id, name, steam_name, country, level))


def upsert_match(match: dict) -> bool:
    """Inserta una partida. Retorna True si es nueva, False si ya existía."""
    sql = """
        INSERT INTO matches (
            match_id, map_id, map_name, game_mode, environment,
            start_time, end_time, score_allied, score_axis
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (match_id) DO NOTHING
        RETURNING match_id
    """
    with db_cursor() as cur:
        cur.execute(sql, (
            match["match_id"],
            match["map_id"],
            match["map_name"],
            match["game_mode"],
            match["environment"],
            match["start_time"],
            match["end_time"],
            match["score_allied"],
            match["score_axis"],
        ))
        return cur.fetchone() is not None


def upsert_match_player_stats(stats: dict) -> None:
    sql = """
        INSERT INTO match_player_stats (
            match_id, player_id, player_name, team_side,
            kills, deaths, kill_death_ratio,
            kills_per_minute, deaths_per_minute,
            kills_streak, teamkills,
            combat, offense, defense, support,
            time_seconds, longest_life_secs, shortest_life_secs, level,
            weapons, death_by_weapons, most_killed, death_by
        ) VALUES (
            %(match_id)s, %(player_id)s, %(player_name)s, %(team_side)s,
            %(kills)s, %(deaths)s, %(kill_death_ratio)s,
            %(kills_per_minute)s, %(deaths_per_minute)s,
            %(kills_streak)s, %(teamkills)s,
            %(combat)s, %(offense)s, %(defense)s, %(support)s,
            %(time_seconds)s, %(longest_life_secs)s, %(shortest_life_secs)s, %(level)s,
            %(weapons)s, %(death_by_weapons)s, %(most_killed)s, %(death_by)s
        )
        ON CONFLICT (match_id, player_id) DO UPDATE SET
            kills              = EXCLUDED.kills,
            deaths             = EXCLUDED.deaths,
            kill_death_ratio   = EXCLUDED.kill_death_ratio,
            kills_per_minute   = EXCLUDED.kills_per_minute,
            deaths_per_minute  = EXCLUDED.deaths_per_minute,
            kills_streak       = EXCLUDED.kills_streak,
            teamkills          = EXCLUDED.teamkills,
            combat             = EXCLUDED.combat,
            offense            = EXCLUDED.offense,
            defense            = EXCLUDED.defense,
            support            = EXCLUDED.support,
            time_seconds       = EXCLUDED.time_seconds,
            longest_life_secs  = EXCLUDED.longest_life_secs,
            shortest_life_secs = EXCLUDED.shortest_life_secs,
            level              = EXCLUDED.level,
            weapons            = EXCLUDED.weapons,
            death_by_weapons   = EXCLUDED.death_by_weapons,
            most_killed        = EXCLUDED.most_killed,
            death_by           = EXCLUDED.death_by,
            team_side          = COALESCE(EXCLUDED.team_side, match_player_stats.team_side)
    """
    with db_cursor() as cur:
        cur.execute(sql, stats)


# ──────────────────────────────────────────────
# Queries de lectura
# ──────────────────────────────────────────────

def get_match_ids_in_db() -> set[int]:
    with db_cursor(commit=False) as cur:
        cur.execute("SELECT match_id FROM matches")
        return {row[0] for row in cur.fetchall()}


def get_player_totals(limit: int = 10) -> list[dict]:
    sql = """
        SELECT player_id, name, country, matches_played,
               total_kills, total_deaths, overall_kd,
               total_combat, total_offense, total_defense, total_support,
               best_kill_streak, max_level, last_seen_at
        FROM player_totals
        ORDER BY total_kills DESC
        LIMIT %s
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, (limit,))
        return [dict(row) for row in cur.fetchall()]


def get_recent_matches(limit: int = 5) -> list[dict]:
    sql = """
        SELECT match_id, map_name, game_mode, start_time,
               duration_minutes, score_allied, score_axis,
               winner, players_count, total_kills
        FROM match_summary
        LIMIT %s
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, (limit,))
        return [dict(row) for row in cur.fetchall()]


def get_match_top_players(match_id: int, limit: int = 5) -> list[dict]:
    sql = """
        SELECT player_name, team_side, kills, deaths,
               kill_death_ratio, combat, offense, defense, support,
               weapons, most_killed
        FROM match_player_stats
        WHERE match_id = %s
        ORDER BY kills DESC
        LIMIT %s
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, (match_id, limit))
        return [dict(row) for row in cur.fetchall()]
