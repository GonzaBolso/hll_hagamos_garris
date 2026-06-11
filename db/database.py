"""
db/database.py  – Conexión y operaciones con PostgreSQL via psycopg2
"""
import logging
from contextlib import contextmanager

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
            match["match_id"], match["map_id"], match["map_name"],
            match["game_mode"], match["environment"],
            match["start_time"], match["end_time"],
            match["score_allied"], match["score_axis"],
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
# Filtros de período
# ──────────────────────────────────────────────

def _period_filter(period: str | None) -> tuple[str, list]:
    """
    Filtra por período relativo.
    period: 'day' | 'week' | 'month' | None (historial completo)
    """
    if not period:
        return "", []
    if period == "day":
        # Desde medianoche UY de hoy
        clause = "AND m.start_time >= date_trunc('day', NOW() AT TIME ZONE 'America/Montevideo') AT TIME ZONE 'America/Montevideo'"
        return clause, []
    intervals = {"week": "7 days", "month": "30 days"}
    interval = intervals.get(period, "7 days")
    clause = "AND m.start_time >= NOW() - INTERVAL %s"
    return clause, [interval]


def _date_filter(date_str: str | None) -> tuple[str, list]:
    """
    Filtra por fecha calendario UY específica (YYYY-MM-DD).
    Toma desde medianoche hasta medianoche siguiente en hora Uruguay.
    """
    if not date_str:
        return "", []
    clause = """
        AND m.start_time >= (%s::date) AT TIME ZONE 'America/Montevideo'
        AND m.start_time <  (%s::date + INTERVAL '1 day') AT TIME ZONE 'America/Montevideo'
    """
    return clause, [date_str, date_str]


# ──────────────────────────────────────────────
# Queries de lectura
# ──────────────────────────────────────────────

def get_match_ids_in_db() -> set[int]:
    with db_cursor(commit=False) as cur:
        cur.execute("SELECT match_id FROM matches")
        return {row[0] for row in cur.fetchall()}


def get_player_totals(limit: int = 10, period: str | None = None, date_str: str | None = None) -> list[dict]:
    """Top jugadores por kills totales."""
    if date_str:
        extra_clause, extra_params = _date_filter(date_str)
    else:
        extra_clause, extra_params = _period_filter(period)
    sql = f"""
        SELECT
            p.player_id, p.name, p.country,
            COUNT(DISTINCT mps.match_id)  AS matches_played,
            SUM(mps.kills)                AS total_kills,
            SUM(mps.deaths)               AS total_deaths,
            CASE WHEN SUM(mps.deaths) > 0
                 THEN ROUND(SUM(mps.kills)::numeric / SUM(mps.deaths), 2)
                 ELSE SUM(mps.kills) END  AS overall_kd
        FROM match_player_stats mps
        JOIN players p USING (player_id)
        JOIN matches m USING (match_id)
        WHERE TRUE {extra_clause}
        GROUP BY p.player_id, p.name, p.country
        ORDER BY total_kills DESC
        LIMIT %s
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, extra_params + [limit])
        return [dict(row) for row in cur.fetchall()]


def get_top_hours(limit: int = 10, period: str | None = None, date_str: str | None = None) -> list[dict]:
    """Top jugadores por horas jugadas."""
    if date_str:
        extra_clause, extra_params = _date_filter(date_str)
    else:
        extra_clause, extra_params = _period_filter(period)
    sql = f"""
        SELECT
            p.name, p.country,
            COUNT(DISTINCT mps.match_id)             AS matches_played,
            SUM(mps.time_seconds)                    AS total_seconds,
            ROUND(SUM(mps.time_seconds) / 3600.0, 1) AS total_hours,
            SUM(mps.kills)                           AS total_kills,
            SUM(mps.deaths)                          AS total_deaths
        FROM match_player_stats mps
        JOIN players p USING (player_id)
        JOIN matches m USING (match_id)
        WHERE TRUE {extra_clause}
        GROUP BY p.player_id, p.name, p.country
        HAVING SUM(mps.time_seconds) > 0
        ORDER BY total_seconds DESC
        LIMIT %s
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, extra_params + [limit])
        return [dict(row) for row in cur.fetchall()]


def get_top_kd(limit: int = 10, min_matches: int = 5, period: str | None = None, date_str: str | None = None) -> list[dict]:
    """Top jugadores por KD con mínimo de partidas."""
    if date_str:
        extra_clause, extra_params = _date_filter(date_str)
    else:
        extra_clause, extra_params = _period_filter(period)
    sql = f"""
        SELECT
            p.name, p.country,
            COUNT(DISTINCT mps.match_id) AS matches_played,
            SUM(mps.kills)               AS total_kills,
            SUM(mps.deaths)              AS total_deaths,
            CASE WHEN SUM(mps.deaths) > 0
                 THEN ROUND(SUM(mps.kills)::numeric / SUM(mps.deaths), 2)
                 ELSE SUM(mps.kills) END AS kd_ratio
        FROM match_player_stats mps
        JOIN players p USING (player_id)
        JOIN matches m USING (match_id)
        WHERE TRUE {extra_clause}
        GROUP BY p.player_id, p.name, p.country
        HAVING COUNT(DISTINCT mps.match_id) >= %s
        ORDER BY kd_ratio DESC
        LIMIT %s
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, extra_params + [min_matches, limit])
        return [dict(row) for row in cur.fetchall()]


def get_top_kills_per_hour(limit: int = 10, min_hours: float = 1.0, period: str | None = None, date_str: str | None = None) -> list[dict]:
    """Top jugadores por kills/hora."""
    if date_str:
        extra_clause, extra_params = _date_filter(date_str)
    else:
        extra_clause, extra_params = _period_filter(period)
    sql = f"""
        SELECT
            p.name, p.country,
            COUNT(DISTINCT mps.match_id)                               AS matches_played,
            SUM(mps.kills)                                             AS total_kills,
            ROUND(SUM(mps.time_seconds) / 3600.0, 1)                  AS total_hours,
            ROUND(SUM(mps.kills) / (SUM(mps.time_seconds) / 3600.0), 2) AS kills_per_hour
        FROM match_player_stats mps
        JOIN players p USING (player_id)
        JOIN matches m USING (match_id)
        WHERE TRUE {extra_clause}
        GROUP BY p.player_id, p.name, p.country
        HAVING SUM(mps.time_seconds) >= %s * 3600
        ORDER BY kills_per_hour DESC
        LIMIT %s
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, extra_params + [min_hours, limit])
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