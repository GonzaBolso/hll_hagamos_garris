"""
collectors/api_client.py  –  Wrapper para los endpoints HLL
"""
import logging
from typing import Any

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})
TIMEOUT = 15


def _get(endpoint: str, params: dict | None = None) -> Any:
    url = f"{settings.HLL_BASE_URL}/{endpoint}"
    try:
        resp = SESSION.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("failed"):
            raise RuntimeError(f"API error en {endpoint}: {data.get('error')}")
        return data["result"]
    except requests.RequestException as e:
        logger.error("Error al llamar %s: %s", url, e)
        raise


# ──────────────────────────────────────────────
# Endpoints públicos
# ──────────────────────────────────────────────

def get_public_info() -> dict:
    """Estado actual del servidor (mapa, jugadores, score)."""
    return _get("get_public_info")


def get_live_game_stats() -> list[dict]:
    """Estadísticas en vivo de los jugadores actuales."""
    result = _get("get_live_game_stats")
    return result.get("stats", [])


def get_live_scoreboard() -> list[dict]:
    """Scoreboard en vivo."""
    result = _get("live_scoreboard")
    return result.get("stats", [])


# ──────────────────────────────────────────────
# Endpoints de historial
# ──────────────────────────────────────────────

def get_scoreboard_maps(page: int = 1, limit: int = 50) -> dict:
    """
    Lista de partidas históricas.
    Retorna: {"page", "page_size", "total", "maps": [...]}
    """
    return _get("get_scoreboard_maps", params={"page": page, "limit": limit})


def get_map_scoreboard(map_id: int) -> dict:
    """Detalle completo de una partida con estadísticas por jugador."""
    return _get("get_map_scoreboard", params={"map_id": map_id})
