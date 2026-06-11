"""
discord/webhook.py  –  Envía embeds a Discord via webhook
"""
import logging
from datetime import datetime, timezone, timedelta

import requests

TZ_UY = timezone(timedelta(hours=-3))  # Uruguay UTC-3

from config.settings import settings

logger = logging.getLogger(__name__)

COLORS = {
    "allied": 0x3A7EBF,
    "axis":   0xBF3A3A,
    "draw":   0x888888,
    "info":   0x5865F2,
    "gold":   0xF1C40F,
    "green":  0x2ECC71,
    "purple": 0x9B59B6,
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
        resp = requests.post(settings.DISCORD_WEBHOOK_URL, json=payload, timeout=10)
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


def _country_flag(country: str | None) -> str:
    if country and len(country) == 2:
        return f" :flag_{country.lower()}:"
    return ""


def _medals(i: int) -> str:
    return ["🥇", "🥈", "🥉"][i] if i < 3 else "🔹"


# ──────────────────────────────────────────────
# Embeds existentes
# ──────────────────────────────────────────────

def send_match_summary(match: dict, top_players: list[dict]) -> bool:
    winner     = match.get("winner", "draw")
    color      = COLORS.get(winner, COLORS["info"])
    winner_lbl = TEAM_LABELS.get(winner, "Empate")
    duration   = _format_duration(match.get("duration_minutes"))

    start = match.get("start_time")
    ts = f"<t:{int(start.timestamp())}:F>" if isinstance(start, datetime) else str(start or "?")

    fields = [
        {"name": "📋 Mapa",     "value": f"{match.get('map_name','?')} — *{match.get('game_mode','?')}*", "inline": True},
        {"name": "⏱️ Duración", "value": duration, "inline": True},
        {"name": "🏆 Resultado", "value": f"{winner_lbl}\n🟦 {match.get('score_allied',0)}  —  {match.get('score_axis',0)} 🟥", "inline": False},
        {"name": "👥 Jugadores / Bajas", "value": f"{match.get('players_count',0)} jugadores · {match.get('total_kills',0)} kills totales", "inline": False},
    ]

    if top_players:
        lines = []
        for i, p in enumerate(top_players[:5]):
            side   = "🟦" if p.get("team_side") == "allied" else "🟥" if p.get("team_side") == "axis" else "⬜"
            kd     = p.get("kill_death_ratio", 0)
            weapons = p.get("weapons") or {}
            top_weapon = max(weapons, key=weapons.get, default=None) if weapons else None
            gun_txt = f" · {WEAPON_ICONS.get(top_weapon,'🔫')} {top_weapon}" if top_weapon else ""
            lines.append(f"{_medals(i)} {side} **{p['player_name']}** — {p.get('kills',0)}K/{p.get('deaths',0)}D (KD {kd:.2f}){gun_txt}")
        fields.append({"name": "🎖️ Top Jugadores", "value": "\n".join(lines), "inline": False})

    payload = {"embeds": [{"title": "📊 Resumen de Partida", "description": f"🗓️ {ts}", "color": color,
                            "fields": fields, "footer": {"text": "[LATAM] Hagamos Garris · HLL Stats"},
                            "timestamp": datetime.now(TZ_UY).isoformat()}]}
    return _post(payload)


def send_collection_report(counters: dict) -> bool:
    payload = {"embeds": [{"title": "🔄 Recolección de historial completada", "color": COLORS["info"],
                "fields": [
                    {"name": "✅ Partidas nuevas",     "value": str(counters.get("new_matches", 0)),      "inline": True},
                    {"name": "⏭️ Ya existían",          "value": str(counters.get("skipped", 0)),          "inline": True},
                    {"name": "👤 Players actualizados", "value": str(counters.get("players_upserted", 0)), "inline": True},
                    {"name": "❌ Errores",              "value": str(counters.get("errors", 0)),            "inline": True},
                ],
                "footer": {"text": "HLL Stats Bot"}, "timestamp": datetime.now(TZ_UY).isoformat()}]}
    return _post(payload)


def send_top_players(players: list[dict]) -> bool:
    """Top kills totales."""
    if not players:
        return False
    lines = []
    for i, p in enumerate(players):
        kd = p.get("overall_kd") or 0
        lines.append(f"{_medals(i)}{_country_flag(p.get('country'))} **{p['name']}** — "
                     f"{p.get('total_kills',0)}K/{p.get('total_deaths',0)}D · KD **{kd}** · {p.get('matches_played',0)} partidas")
    payload = {"embeds": [{"title": "💀 Top Kills Totales", "description": "\n".join(lines),
                "color": COLORS["info"], "footer": {"text": "HLL Stats Bot"},
                "timestamp": datetime.now(TZ_UY).isoformat()}]}
    return _post(payload)


# ──────────────────────────────────────────────
# Nuevos rankings
# ──────────────────────────────────────────────

def send_top_hours(players: list[dict]) -> bool:
    """Top horas jugadas."""
    if not players:
        return False
    lines = []
    for i, p in enumerate(players):
        lines.append(f"{_medals(i)}{_country_flag(p.get('country'))} **{p['name']}** — "
                     f"⏱️ **{p.get('total_hours',0)}h** · {p.get('total_kills',0)} kills · {p.get('matches_played',0)} partidas")
    payload = {"embeds": [{"title": "⏱️ Top Horas Jugadas", "description": "\n".join(lines),
                "color": COLORS["green"], "footer": {"text": "HLL Stats Bot"},
                "timestamp": datetime.now(TZ_UY).isoformat()}]}
    return _post(payload)


def send_top_kd(players: list[dict], min_matches: int = 10) -> bool:
    """Top KD con mínimo de partidas."""
    if not players:
        return False
    lines = []
    for i, p in enumerate(players):
        lines.append(f"{_medals(i)}{_country_flag(p.get('country'))} **{p['name']}** — "
                     f"KD **{p.get('kd_ratio',0)}** · {p.get('total_kills',0)}K/{p.get('total_deaths',0)}D · {p.get('matches_played',0)} partidas")
    payload = {"embeds": [{"title": f"⚔️ Top KD (mín. {min_matches} partidas)", "description": "\n".join(lines),
                "color": COLORS["gold"], "footer": {"text": "HLL Stats Bot"},
                "timestamp": datetime.now(TZ_UY).isoformat()}]}
    return _post(payload)


def send_top_efficiency(players: list[dict], min_hours: float = 2.0) -> bool:
    """Top kills por hora — el combo que mencionaste."""
    if not players:
        return False
    lines = []
    for i, p in enumerate(players):
        lines.append(f"{_medals(i)}{_country_flag(p.get('country'))} **{p['name']}** — "
                     f"🎯 **{p.get('kills_per_hour',0)} K/h** · {p.get('total_kills',0)} kills en {p.get('total_hours',0)}h · {p.get('matches_played',0)} partidas")
    payload = {"embeds": [{"title": f"🎯 Top Eficiencia — Kills/Hora (mín. {min_hours}h)", "description": "\n".join(lines),
                "color": COLORS["purple"], "footer": {"text": "HLL Stats Bot"},
                "timestamp": datetime.now(TZ_UY).isoformat()}]}
    return _post(payload)