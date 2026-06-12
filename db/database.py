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
                  country: str | None, level: int | None,
                  avatar_url: str | None = None) -> None:
    sql = """
        INSERT INTO players (player_id, name, steam_name, country, level, avatar_url, last_seen_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (player_id) DO UPDATE SET
            name         = EXCLUDED.name,
            steam_name   = COALESCE(EXCLUDED.steam_name, players.steam_name),
            country      = COALESCE(EXCLUDED.country, players.country),
            level        = GREATEST(EXCLUDED.level, players.level),
            avatar_url   = COALESCE(EXCLUDED.avatar_url, players.avatar_url),
            last_seen_at = NOW()
    """
    with db_cursor() as cur:
        cur.execute(sql, (player_id, name, steam_name, country, level, avatar_url))


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


def get_top_score_tactical(limit: int = 10, period: str | None = None, date_str: str | None = None) -> list[dict]:
    """Top jugadores por Ataque + (Defensa × 1.75)."""
    if date_str:
        extra_clause, extra_params = _date_filter(date_str)
    else:
        extra_clause, extra_params = _period_filter(period)
    sql = f"""
        SELECT
            p.name, p.country, p.avatar_url,
            COUNT(DISTINCT mps.match_id)                              AS matches_played,
            SUM(mps.offense)                                          AS total_offense,
            SUM(mps.defense)                                          AS total_defense,
            ROUND(SUM(mps.offense) + SUM(mps.defense) * 1.75, 0)    AS score_tactical
        FROM match_player_stats mps
        JOIN players p USING (player_id)
        JOIN matches m USING (match_id)
        WHERE TRUE {extra_clause}
        GROUP BY p.player_id, p.name, p.country, p.avatar_url
        ORDER BY score_tactical DESC
        LIMIT %s
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, extra_params + [limit])
        return [dict(row) for row in cur.fetchall()]


def get_top_score_combat(limit: int = 10, period: str | None = None, date_str: str | None = None) -> list[dict]:
    """Top jugadores por Combate + (Apoyo × 1.75)."""
    if date_str:
        extra_clause, extra_params = _date_filter(date_str)
    else:
        extra_clause, extra_params = _period_filter(period)
    sql = f"""
        SELECT
            p.name, p.country, p.avatar_url,
            COUNT(DISTINCT mps.match_id)                              AS matches_played,
            SUM(mps.combat)                                           AS total_combat,
            SUM(mps.support)                                          AS total_support,
            ROUND(SUM(mps.combat) + SUM(mps.support) * 1.75, 0)     AS score_combat
        FROM match_player_stats mps
        JOIN players p USING (player_id)
        JOIN matches m USING (match_id)
        WHERE TRUE {extra_clause}
        GROUP BY p.player_id, p.name, p.country, p.avatar_url
        ORDER BY score_combat DESC
        LIMIT %s
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, extra_params + [limit])
        return [dict(row) for row in cur.fetchall()]


def get_top_maps(limit: int = 10, period: str | None = None, date_str: str | None = None) -> list[dict]:
    """Top mapas por cantidad de partidas jugadas."""
    if date_str:
        extra_clause, extra_params = _date_filter(date_str)
    else:
        extra_clause, extra_params = _period_filter(period)
    # Filtramos partidas donde realmente se jugó (duración > 10 min)
    sql = f"""
        SELECT
            map_name,
            COUNT(*)                                                   AS total_matches,
            SUM(CASE WHEN score_allied > score_axis THEN 1 ELSE 0 END) AS allied_wins,
            SUM(CASE WHEN score_axis > score_allied THEN 1 ELSE 0 END) AS axis_wins,
            SUM(CASE WHEN score_allied = score_axis THEN 1 ELSE 0 END) AS draws,
            ROUND(AVG(EXTRACT(EPOCH FROM (end_time - start_time)) / 60), 0) AS avg_duration_min
        FROM matches m
        WHERE EXTRACT(EPOCH FROM (end_time - start_time)) > 600
        {extra_clause}
        GROUP BY map_name
        ORDER BY total_matches DESC
        LIMIT %s
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, extra_params + [limit])
        return [dict(row) for row in cur.fetchall()]
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


# ──────────────────────────────────────────────
# Discord ↔ Steam registro
# ──────────────────────────────────────────────

def register_discord_player(discord_id: str, discord_name: str, player_id: str) -> bool:
    """Registra o actualiza el link Discord ↔ Steam. Retorna True si es nuevo."""
    sql = """
        INSERT INTO discord_players (discord_id, discord_name, player_id, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (discord_id) DO UPDATE SET
            discord_name = EXCLUDED.discord_name,
            player_id    = EXCLUDED.player_id,
            updated_at   = NOW()
        RETURNING (xmax = 0) AS is_new
    """
    with db_cursor() as cur:
        cur.execute(sql, (discord_id, discord_name, player_id))
        row = cur.fetchone()
        return row and row[0]


def get_player_id_by_discord(discord_id: str) -> str | None:
    """Devuelve el player_id (Steam ID) asociado a un discord_id."""
    with db_cursor(commit=False) as cur:
        cur.execute("SELECT player_id FROM discord_players WHERE discord_id = %s", (discord_id,))
        row = cur.fetchone()
        return row[0] if row else None


def get_player_stats_full(player_id: str, year: int | None = None, month: int | None = None) -> dict | None:
    """Stats totales de un jugador filtradas por año/mes."""
    conditions = ["mps.player_id = %s"]
    params = [player_id]
    if year:
        conditions.append("EXTRACT(YEAR FROM m.start_time AT TIME ZONE 'America/Montevideo') = %s")
        params.append(year)
    if month:
        conditions.append("EXTRACT(MONTH FROM m.start_time AT TIME ZONE 'America/Montevideo') = %s")
        params.append(month)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            p.name, p.country, p.avatar_url,
            COUNT(DISTINCT mps.match_id)                              AS matches_played,
            SUM(mps.kills)                                            AS total_kills,
            SUM(mps.deaths)                                           AS total_deaths,
            CASE WHEN SUM(mps.deaths) > 0
                 THEN ROUND(SUM(mps.kills)::numeric / SUM(mps.deaths), 2)
                 ELSE SUM(mps.kills) END                              AS kd_ratio,
            ROUND(SUM(mps.time_seconds) / 3600.0, 1)                 AS total_hours,
            SUM(mps.kills_streak)                                     AS best_streak,
            SUM(mps.combat)                                           AS total_combat,
            SUM(mps.offense)                                          AS total_offense,
            SUM(mps.defense)                                          AS total_defense,
            SUM(mps.support)                                          AS total_support,
            SUM(mps.teamkills)                                        AS total_teamkills
        FROM match_player_stats mps
        JOIN players p USING (player_id)
        JOIN matches m USING (match_id)
        WHERE {where}
        GROUP BY p.player_id, p.name, p.country, p.avatar_url
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None


def get_player_weapons_stats(player_id: str, year: int | None = None, month: int | None = None) -> dict:
    """Agrega kills por arma para un jugador."""
    conditions = ["mps.player_id = %s"]
    params = [player_id]
    if year:
        conditions.append("EXTRACT(YEAR FROM m.start_time AT TIME ZONE 'America/Montevideo') = %s")
        params.append(year)
    if month:
        conditions.append("EXTRACT(MONTH FROM m.start_time AT TIME ZONE 'America/Montevideo') = %s")
        params.append(month)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT weapons
        FROM match_player_stats mps
        JOIN matches m USING (match_id)
        WHERE {where}
    """
    import json
    totals: dict = {}
    with db_cursor(commit=False) as cur:
        cur.execute(sql, params)
        for row in cur.fetchall():
            w = row[0]
            if isinstance(w, str):
                w = json.loads(w)
            if isinstance(w, dict):
                for weapon, kills in w.items():
                    totals[weapon] = totals.get(weapon, 0) + int(kills)
    return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))


def get_player_recent_games(player_id: str, limit: int = 5) -> list[dict]:
    """Últimas N partidas de un jugador."""
    sql = """
        SELECT
            m.map_name, m.start_time, m.winner,
            mps.kills, mps.deaths, mps.kill_death_ratio,
            mps.combat, mps.offense, mps.defense, mps.support,
            mps.time_seconds, mps.team_side, mps.weapons
        FROM match_player_stats mps
        JOIN matches m USING (match_id)
        WHERE mps.player_id = %s
        ORDER BY m.start_time DESC
        LIMIT %s
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, (player_id, limit))
        return [dict(row) for row in cur.fetchall()]


def get_top_by_weapon(weapon_name: str, limit: int = 20, year: int | None = None) -> list[dict]:
    """Top jugadores por kills con un arma específica."""
    conditions = []
    params = []
    if year:
        conditions.append("EXTRACT(YEAR FROM m.start_time AT TIME ZONE 'America/Montevideo') = %s")
        params.append(year)

    year_join = f"JOIN matches m USING (match_id)" if year else "JOIN matches m USING (match_id)"
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    sql = f"""
        SELECT
            p.name, p.country, p.avatar_url,
            SUM((mps.weapons->>%s)::int)  AS weapon_kills,
            COUNT(DISTINCT mps.match_id)  AS matches_played
        FROM match_player_stats mps
        JOIN players p USING (player_id)
        {year_join}
        {where}
        WHERE mps.weapons ? %s
        GROUP BY p.player_id, p.name, p.country, p.avatar_url
        HAVING SUM((mps.weapons->>%s)::int) > 0
        ORDER BY weapon_kills DESC
        LIMIT %s
    """
    # La query tiene dos WHERE, hay que arreglarla
    sql = f"""
        SELECT
            p.name, p.country, p.avatar_url,
            SUM((mps.weapons->>%s)::int)  AS weapon_kills,
            COUNT(DISTINCT mps.match_id)  AS matches_played
        FROM match_player_stats mps
        JOIN players p USING (player_id)
        JOIN matches m USING (match_id)
        WHERE mps.weapons ? %s
        {"AND " + " AND ".join(conditions) if conditions else ""}
        GROUP BY p.player_id, p.name, p.country, p.avatar_url
        HAVING SUM((mps.weapons->>%s)::int) > 0
        ORDER BY weapon_kills DESC
        LIMIT %s
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, [weapon_name, weapon_name] + params + [weapon_name, limit])
        return [dict(row) for row in cur.fetchall()]


def search_player_by_name(name: str) -> list[dict]:
    """Busca jugadores por nombre (case-insensitive, parcial)."""
    sql = """
        SELECT player_id, name, country, avatar_url
        FROM players
        WHERE name ILIKE %s
        LIMIT 10
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, (f"%{name}%",))
        return [dict(row) for row in cur.fetchall()]