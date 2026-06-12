"""
collectors/history_collector.py
Descarga el historial de partidas y persiste en PostgreSQL.
Modo incremental: para cuando encuentra IDs que ya están en la DB.
"""
import json
import logging
from typing import Any

from collectors.api_client import get_scoreboard_maps, get_map_scoreboard
from db.database import (
    upsert_player,
    upsert_match,
    upsert_match_player_stats,
    get_match_ids_in_db,
)
from config.settings import settings

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Parsers
# ──────────────────────────────────────────────

def _parse_match(raw: dict) -> dict:
    m = raw["map"]
    return {
        "match_id":    raw["id"],
        "map_id":      m["id"],
        "map_name":    m["map"]["pretty_name"],
        "game_mode":   m["game_mode"],
        "environment": m.get("environment", "day"),
        "start_time":  raw.get("start"),
        "end_time":    raw.get("end"),
        "score_allied": raw["result"]["allied"],
        "score_axis":   raw["result"]["axis"],
    }


def _parse_player_stats(raw: dict, match_id: int) -> dict:
    shortest = raw.get("shortest_life_secs", 0)
    if shortest == 9999:
        shortest = 0

    team_side = None
    team_info = raw.get("team")
    if isinstance(team_info, dict):
        side = team_info.get("side")
        if side in ("allied", "axis"):
            team_side = side

    return {
        "match_id":           match_id,
        "player_id":          raw["player_id"],
        "player_name":        raw["player"],
        "team_side":          team_side,
        "kills":              raw.get("kills", 0),
        "deaths":             raw.get("deaths", 0),
        "kill_death_ratio":   raw.get("kill_death_ratio", 0),
        "kills_per_minute":   raw.get("kills_per_minute", 0),
        "deaths_per_minute":  raw.get("deaths_per_minute", 0),
        "kills_streak":       raw.get("kills_streak", 0),
        "teamkills":          raw.get("teamkills", 0),
        "combat":             raw.get("combat", 0),
        "offense":            raw.get("offense", 0),
        "defense":            raw.get("defense", 0),
        "support":            raw.get("support", 0),
        "time_seconds":       raw.get("time_seconds", 0),
        "longest_life_secs":  raw.get("longest_life_secs", 0),
        "shortest_life_secs": shortest,
        "level":              raw.get("level"),
        "weapons":            json.dumps(raw.get("weapons", {})),
        "death_by_weapons":   json.dumps(raw.get("death_by_weapons", {})),
        "most_killed":        json.dumps(raw.get("most_killed", {})),
        "death_by":           json.dumps(raw.get("death_by", {})),
    }


def _parse_player_identity(raw: dict) -> tuple[str, str | None, str | None, int | None, str | None]:
    steam_info = raw.get("steaminfo") or {}
    profile    = steam_info.get("profile") or {}
    steam_name = profile.get("personaname")
    country    = steam_info.get("country")
    level      = raw.get("level")
    avatar_url = profile.get("avatar") or profile.get("avatarmedium") or profile.get("avatarfull")
    return raw["player_id"], steam_name, country, level, avatar_url


# ──────────────────────────────────────────────
# Lógica principal
# ──────────────────────────────────────────────

def collect_history(max_pages: int | None = None, full: bool = False) -> dict[str, int]:
    """
    Descarga el historial de partidas y lo guarda en la DB.
    Modo incremental: para cuando encuentra una página sin partidas nuevas.
    Modo full (--full): procesa todas las páginas sin importar si ya existen.

    Parámetros:
        max_pages: límite de páginas
        full: si True, ignora el modo incremental y recorre todas las páginas
    """
    page_size = settings.PAGE_SIZE
    known_ids = get_match_ids_in_db()
    counters  = {"new_matches": 0, "skipped": 0, "players_upserted": 0, "errors": 0}

    logger.info("Iniciando recolección de historial. IDs ya en DB: %d — modo: %s",
                len(known_ids), "full" if full else "incremental")

    page = 1
    while True:
        if max_pages and page > max_pages:
            logger.info("Límite de páginas alcanzado (%d).", max_pages)
            break

        logger.info("Procesando página %d…", page)

        try:
            result = get_scoreboard_maps(page=page, limit=page_size)
        except Exception as e:
            logger.error("Error al obtener página %d: %s", page, e)
            counters["errors"] += 1
            break

        maps = result.get("maps", [])
        if not maps:
            logger.info("No hay más partidas en página %d. Fin.", page)
            break

        new_in_page = 0

        for raw_match in maps:
            match_id = raw_match["id"]

            if match_id in known_ids:
                counters["skipped"] += 1
                continue

            match_data = _parse_match(raw_match)
            is_new = upsert_match(match_data)

            if not is_new:
                counters["skipped"] += 1
                continue

            try:
                detail = get_map_scoreboard(match_id)
            except Exception as e:
                logger.warning("No se pudo obtener detalle del match %d: %s", match_id, e)
                counters["errors"] += 1
                continue

            for raw_ps in detail.get("player_stats", []):
                try:
                    pid, steam_name, country, level, avatar_url = _parse_player_identity(raw_ps)
                    upsert_player(pid, raw_ps["player"], steam_name, country, level, avatar_url)
                    counters["players_upserted"] += 1
                    ps = _parse_player_stats(raw_ps, match_id)
                    upsert_match_player_stats(ps)
                except Exception as e:
                    logger.warning("Error guardando stats del jugador en match %d: %s", match_id, e)
                    counters["errors"] += 1

            counters["new_matches"] += 1
            new_in_page += 1
            known_ids.add(match_id)
            logger.debug("Match %d guardado (%s).", match_id, match_data["map_name"])

        # En modo incremental, para cuando no hay novedades
        if not full and new_in_page == 0:
            logger.info("Página %d sin partidas nuevas. Recolección incremental completa.", page)
            break

        page += 1

    logger.info("Recolección finalizada: %s", counters)
    return counters