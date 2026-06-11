"""
discord/webhook.py  –  Envía embeds a Discord via webhook
"""
import logging
from datetime import datetime, timezone
from typing import Any

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

COLORS = {
    "allied": 0x3A7EBF,    # azul aliados
    "axis":   0xBF3A3A,    # rojo eje
    "draw":   0x888888,    # gris empate
    "info":   0x5865F2,    # blanco discord
}

TEAM_LABELS = {
    "allied": "🟦 Aliados",
    "axis":   "🟥 Eje",
    "draw":   "⬜ Empate",
}

WEAPON_ICONS = {
    "MP40":             "🔫",
    "GEWEHR 43":        "🎯",
    "KARABINER 98K":    "🔭",
    "M1 GARAND":        "🪖",
    "M1A1 THOMPSON":    "💥",
    "STG44":            "⚡",
    "M1918A2 BAR":      "🔥",
    "M3 GREASE GUN":    "🔫",
    "MK2 GRENADE":      "💣",
    "PRECISION STRIKE": "🛩️",
}


def _post(payload: dict) -> bool:
    if not settings.DISCORD_WEBHOOK_URL:
        logger.warning("DISCORD_WEBHOOK_URL no configurada. Mensaje no enviado.")
        return False
    try:
        resp = requests.post(
            settings.DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error("Error enviando webhook: %s", e)
        return False


def _format_duration(minutes: float | None) -> str:
    if not minutes:
        return "?"
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m}m" if h else f"{m}m"


def _weapon_label(weapon: str, kills: int) -> str:
    icon = WEAPON_ICONS.get(weapon, "🔸")
    return f"{icon} {weapon}: **{kills}**"


# ──────────────────────────────────────────────
# Embeds
# ──────────────────────────────────────────────

def send_match_summary(match: dict, top_players: list[dict]) -> bool:
    """
    Postea un resumen de partida en Discord.

    match debe tener: map_name, game_mode, start_time, duration_minutes,
                      score_allied, score_axis, winner, players_count, total_kills
    top_players: lista con kills, deaths, player_name, team_side, weapons
    """
    winner     = match.get("winner", "draw")
    color      = COLORS.get(winner, COLORS["info"])
    winner_lbl = TEAM_LABELS.get(winner, "Empate")
    duration   = _format_duration(match.get("duration_minutes"))

    start = match.get("start_time")
    if isinstance(start, datetime):
        ts = f"<t:{int(start.timestamp())}:F>"
    else:
        ts = str(start or "?")

    # Campos del embed
    fields = [
        {
            "name": "📋 Mapa",
            "value": f"{match.get('map_name','?')} — *{match.get('game_mode','?')}*",
            "inline": True,
        },
        {
            "name": "⏱️ Duración",
            "value": duration,
            "inline": True,
        },
        {
            "name": "🏆 Resultado",
            "value": (
                f"{winner_lbl}\n"
                f"🟦 {match.get('score_allied',0)}  —  "
                f"{match.get('score_axis',0)} 🟥"
            ),
            "inline": False,
        },
        {
            "name": "👥 Jugadores / Bajas",
            "value": f"{match.get('players_count',0)} jugadores · {match.get('total_kills',0)} kills totales",
            "inline": False,
        },
    ]

    # Top jugadores
    if top_players:
        lines = []
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, p in enumerate(top_players[:5]):
            medal  = medals[i] if i < len(medals) else "•"
            side   = "🟦" if p.get("team_side") == "allied" else "🟥" if p.get("team_side") == "axis" else "⬜"
            kd     = p.get("kill_death_ratio", 0)
            weapons: dict = p.get("weapons") or {}
            top_weapon = max(weapons, key=weapons.get, default=None) if weapons else None
            gun_txt = f" · {WEAPON_ICONS.get(top_weapon,'🔫')} {top_weapon}" if top_weapon else ""
            lines.append(
                f"{medal} {side} **{p['player_name']}** — "
                f"{p.get('kills',0)}K/{p.get('deaths',0)}D (KD {kd:.2f}){gun_txt}"
            )
        fields.append({
            "name": "🎖️ Top Jugadores",
            "value": "\n".join(lines),
            "inline": False,
        })

    payload = {
        "embeds": [
            {
                "title": f"📊 Resumen de Partida",
                "description": f"🗓️ {ts}",
                "color": color,
                "fields": fields,
                "footer": {"text": "[LATAM] Hagamos Garris · HLL Stats"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }

    return _post(payload)


def send_collection_report(counters: dict) -> bool:
    """Postea un reporte rápido de la última recolección."""
    payload = {
        "embeds": [
            {
                "title": "🔄 Recolección de historial completada",
                "color": COLORS["info"],
                "fields": [
                    {"name": "✅ Partidas nuevas",     "value": str(counters.get("new_matches", 0)),       "inline": True},
                    {"name": "⏭️ Ya existían",          "value": str(counters.get("skipped", 0)),           "inline": True},
                    {"name": "👤 Players actualizados", "value": str(counters.get("players_upserted", 0)),  "inline": True},
                    {"name": "❌ Errores",              "value": str(counters.get("errors", 0)),             "inline": True},
                ],
                "footer": {"text": "HLL Stats Bot"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }
    return _post(payload)


def send_top_players(players: list[dict], title: str = "🏅 Top Jugadores del Servidor") -> bool:
    """Postea el ranking global de jugadores."""
    if not players:
        return False

    lines = []
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 20
    for i, p in enumerate(players):
        kd      = p.get("overall_kd") or 0
        country = f" :flag_{p['country'].lower()}:" if p.get("country") and len(p["country"]) == 2 else ""
        lines.append(
            f"{medals[i]}{country} **{p['name']}** — "
            f"{p.get('total_kills',0)}K/{p.get('total_deaths',0)}D "
            f"· KD **{kd}** · {p.get('matches_played',0)} partidas"
        )

    payload = {
        "embeds": [
            {
                "title": title,
                "description": "\n".join(lines),
                "color": COLORS["info"],
                "footer": {"text": "HLL Stats Bot"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }
    return _post(payload)
