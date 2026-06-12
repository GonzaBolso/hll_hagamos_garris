"""
discord/webhook.py  –  Envía embeds a Discord via webhook
"""
import logging
from datetime import datetime, timezone, timedelta

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

TZ_UY = timezone(timedelta(hours=-3))

COLORS = {
    "allied": 0x3A7EBF,
    "axis":   0xBF3A3A,
    "draw":   0x888888,
    "info":   0x5865F2,
    "gold":   0xF1C40F,
    "green":  0x2ECC71,
    "purple": 0x9B59B6,
    "orange": 0xE67E22,
    "red":    0xE74C3C,
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
        logger.warning("DISCORD_WEBHOOK_URL no configurada.")
        return False
    try:
        resp = requests.post(settings.DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error("Error enviando webhook: %s", e)
        return False


def _footer(server_name: str) -> dict:
    return {"text": f"{server_name} · HLL Stats Bot"}


def _now() -> str:
    return datetime.now(TZ_UY).isoformat()


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


def _player_line(i: int, p: dict, stat: str) -> dict:
    """
    Genera un embed field por jugador con avatar como thumbnail.
    stat: el texto de la stat principal ya formateado.
    """
    flag   = _country_flag(p.get("country"))
    avatar = p.get("avatar_url") or p.get("avatar") or None
    name   = p.get("name", "?")
    parts  = p.get("matches_played", 0)
    return {
        "medal":   _medals(i),
        "flag":    flag,
        "name":    name,
        "stat":    stat,
        "parts":   parts,
        "avatar":  avatar,
    }


def _build_ranking_embed(title: str, lines: list[str], color: int,
                          server_name: str, thumbnail_url: str | None = None) -> dict:
    embed = {
        "title":       title,
        "description": "\n".join(lines),
        "color":       color,
        "footer":      _footer(server_name),
        "timestamp":   _now(),
    }
    if thumbnail_url:
        embed["thumbnail"] = {"url": thumbnail_url}
    return embed


# ──────────────────────────────────────────────
# Embeds de colección y match
# ──────────────────────────────────────────────

def send_match_summary(match: dict, top_players: list[dict],
                       server_name: str = "HLL Stats") -> bool:
    winner     = match.get("winner", "draw")
    color      = COLORS.get(winner, COLORS["info"])
    winner_lbl = TEAM_LABELS.get(winner, "Empate")
    duration   = _format_duration(match.get("duration_minutes"))

    start = match.get("start_time")
    ts = f"<t:{int(start.timestamp())}:F>" if isinstance(start, datetime) else str(start or "?")

    fields = [
        {"name": "📋 Mapa",      "value": f"{match.get('map_name','?')} — *{match.get('game_mode','?')}*", "inline": True},
        {"name": "⏱️ Duración",  "value": duration, "inline": True},
        {"name": "🏆 Resultado", "value": f"{winner_lbl}\n🟦 {match.get('score_allied',0)}  —  {match.get('score_axis',0)} 🟥", "inline": False},
        {"name": "👥 Jugadores / Bajas", "value": f"{match.get('players_count',0)} jugadores · {match.get('total_kills',0)} kills totales", "inline": False},
    ]

    if top_players:
        lines = []
        for i, p in enumerate(top_players[:5]):
            side   = "🟦" if p.get("team_side") == "allied" else "🟥" if p.get("team_side") == "axis" else "⬜"
            kd     = p.get("kill_death_ratio", 0)
            weapons = p.get("weapons") or {}
            top_w  = max(weapons, key=weapons.get, default=None) if weapons else None
            gun    = f" · {WEAPON_ICONS.get(top_w,'🔫')} {top_w}" if top_w else ""
            lines.append(f"{_medals(i)} {side} **{p['player_name']}** — {p.get('kills',0)}K/{p.get('deaths',0)}D (KD {kd:.2f}){gun}")
        fields.append({"name": "🎖️ Top Jugadores", "value": "\n".join(lines), "inline": False})

    payload = {"embeds": [{"title": "📊 Resumen de Partida", "description": f"🗓️ {ts}",
                "color": color, "fields": fields,
                "footer": _footer(server_name), "timestamp": _now()}]}
    return _post(payload)


def send_collection_report(counters: dict, server_name: str = "HLL Stats") -> bool:
    payload = {"embeds": [{"title": "🔄 Recolección de historial completada", "color": COLORS["info"],
                "fields": [
                    {"name": "✅ Partidas nuevas",     "value": str(counters.get("new_matches", 0)),      "inline": True},
                    {"name": "⏭️ Ya existían",          "value": str(counters.get("skipped", 0)),          "inline": True},
                    {"name": "👤 Players actualizados", "value": str(counters.get("players_upserted", 0)), "inline": True},
                    {"name": "❌ Errores",              "value": str(counters.get("errors", 0)),            "inline": True},
                ],
                "footer": _footer(server_name), "timestamp": _now()}]}
    return _post(payload)


# ──────────────────────────────────────────────
# Rankings de jugadores
# ──────────────────────────────────────────────

def _player_lines(players: list[dict], stat_fn) -> tuple[list[str], str | None]:
    """Genera líneas de texto y thumbnail del #1."""
    lines = []
    thumbnail = None
    for i, p in enumerate(players):
        if i == 0:
            thumbnail = p.get("avatar_url")
        flag = _country_flag(p.get("country"))
        lines.append(f"{_medals(i)}{flag} **{p['name']}** — {stat_fn(p)} · {p.get('matches_played',0)} partidas")
    return lines, thumbnail


def send_top_players(players: list[dict], period_label: str = "Histórico",
                     server_name: str = "HLL Stats") -> bool:
    lines, thumb = _player_lines(players, lambda p:
        f"{p.get('total_kills',0)}K/{p.get('total_deaths',0)}D · KD **{p.get('overall_kd',0)}**")
    embed = _build_ranking_embed(f"💀 Top Kills — {period_label}", lines, COLORS["info"], server_name, thumb)
    return _post({"embeds": [embed]})


def send_top_hours(players: list[dict], period_label: str = "Histórico",
                   server_name: str = "HLL Stats") -> bool:
    lines, thumb = _player_lines(players, lambda p:
        f"⏱️ **{p.get('total_hours',0)}h** · {p.get('total_kills',0)} kills")
    embed = _build_ranking_embed(f"⏱️ Top Horas Jugadas — {period_label}", lines, COLORS["green"], server_name, thumb)
    return _post({"embeds": [embed]})


def send_top_kd(players: list[dict], min_matches: int = 5, period_label: str = "Histórico",
                server_name: str = "HLL Stats") -> bool:
    lines, thumb = _player_lines(players, lambda p:
        f"KD **{p.get('kd_ratio',0)}** · {p.get('total_kills',0)}K/{p.get('total_deaths',0)}D")
    embed = _build_ranking_embed(f"⚔️ Top KD — {period_label} (mín. {min_matches} partidas)",
                                  lines, COLORS["gold"], server_name, thumb)
    return _post({"embeds": [embed]})


def send_top_efficiency(players: list[dict], min_hours: float = 1.0, period_label: str = "Histórico",
                        server_name: str = "HLL Stats") -> bool:
    lines, thumb = _player_lines(players, lambda p:
        f"🎯 **{p.get('kills_per_hour',0)} K/h** · {p.get('total_kills',0)} kills en {p.get('total_hours',0)}h")
    embed = _build_ranking_embed(f"🎯 Top Eficiencia K/h — {period_label} (mín. {min_hours}h)",
                                  lines, COLORS["purple"], server_name, thumb)
    return _post({"embeds": [embed]})


def send_top_score_tactical(players: list[dict], period_label: str = "Histórico",
                             server_name: str = "HLL Stats") -> bool:
    lines, thumb = _player_lines(players, lambda p:
        f"🛡️ **{int(p.get('score_tactical',0))} pts** · Atq {p.get('total_offense',0)} / Def {p.get('total_defense',0)}")
    embed = _build_ranking_embed(f"🛡️ Top Táctico — {period_label} (Ataque + Defensa×1.75)",
                                  lines, COLORS["orange"], server_name, thumb)
    return _post({"embeds": [embed]})


def send_top_score_combat(players: list[dict], period_label: str = "Histórico",
                           server_name: str = "HLL Stats") -> bool:
    lines, thumb = _player_lines(players, lambda p:
        f"💥 **{int(p.get('score_combat',0))} pts** · Cmb {p.get('total_combat',0)} / Apo {p.get('total_support',0)}")
    embed = _build_ranking_embed(f"💥 Top Combate — {period_label} (Combate + Apoyo×1.75)",
                                  lines, COLORS["red"], server_name, thumb)
    return _post({"embeds": [embed]})


# ──────────────────────────────────────────────
# Ranking de mapas
# ──────────────────────────────────────────────

def send_top_maps(maps: list[dict], period_label: str = "Histórico",
                  server_name: str = "HLL Stats") -> bool:
    if not maps:
        return False
    lines = []
    for i, m in enumerate(maps):
        dur = f"{int(m.get('avg_duration_min') or 0)}min"
        lines.append(
            f"{_medals(i)} **{m['map_name']}** — "
            f"🎮 {m['total_matches']} partidas · "
            f"🟦 {m['allied_wins']} / 🟥 {m['axis_wins']} · "
            f"⏱️ {dur} prom."
        )
    embed = _build_ranking_embed(f"🗺️ Mapas Más Jugados — {period_label}", lines, COLORS["info"], server_name)
    return _post({"embeds": [embed]})