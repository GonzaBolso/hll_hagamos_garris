import json
from datetime import datetime, timezone, timedelta

import discord

from db.database import (
    get_player_id_by_discord,
    get_player_stats_full,
    get_player_weapons_stats,
    get_player_recent_games,
)

TZ_UY = timezone(timedelta(hours=-3))
WEAPON_ICONS = {
    "MP40": "🔫", "GEWEHR 43": "🎯", "KARABINER 98K": "🔭",
    "M1 GARAND": "🪖", "M1A1 THOMPSON": "💥", "STG44": "⚡",
    "M1918A2 BAR": "🔥", "MK2 GRENADE": "💣", "PRECISION STRIKE": "🛩️",
}


def _not_registered_embed() -> discord.Embed:
    return discord.Embed(
        title="❌ No estás registrado",
        description="Usá `/hll register <steam_id>` para vincular tu cuenta primero.",
        color=0xE74C3C,
    )


def _country_flag(country: str | None) -> str:
    if country and len(country) == 2:
        return f":flag_{country.lower()}: "
    return ""


async def cmd_stats_show(interaction: discord.Interaction, mes: bool = False):
    await interaction.response.defer()

    player_id = get_player_id_by_discord(str(interaction.user.id))
    if not player_id:
        await interaction.followup.send(embed=_not_registered_embed(), ephemeral=True)
        return

    now   = datetime.now(TZ_UY)
    year  = now.year
    month = now.month if mes else None
    label = f"{now.strftime('%B %Y')}" if mes else f"Año {year}"
    date_from = f"01/{now.month:02d}/{year}" if mes else f"01/01/{year}"
    date_to   = now.strftime("%d/%m/%Y")

    stats = get_player_stats_full(player_id, year=year, month=month)
    if not stats:
        embed = discord.Embed(
            title="⚠️ Sin datos",
            description=f"No tenés partidas registradas para {label}.",
            color=0xF1C40F,
        )
        await interaction.followup.send(embed=embed)
        return

    weapons = get_player_weapons_stats(player_id, year=year, month=month)
    top_weapons = list(weapons.items())[:5]

    flag  = _country_flag(stats.get("country"))
    name  = stats["name"]
    kd    = float(stats.get("kd_ratio") or 0)
    hours = float(stats.get("total_hours") or 0)
    kph   = round(stats["total_kills"] / hours, 2) if hours > 0 else 0

    embed = discord.Embed(
        title=f"{flag}📊 Stats de {name} — {label}",
        color=0x5865F2,
    )
    if stats.get("avatar_url"):
        embed.set_thumbnail(url=stats["avatar_url"])

    embed.add_field(name="🎮 Partidas", value=str(stats["matches_played"]), inline=True)
    embed.add_field(name="⏱️ Horas",    value=f"{hours}h",                  inline=True)
    embed.add_field(name="🎯 K/h",      value=str(kph),                     inline=True)

    embed.add_field(name="💀 Kills",    value=str(stats["total_kills"]),    inline=True)
    embed.add_field(name="☠️ Deaths",   value=str(stats["total_deaths"]),   inline=True)
    embed.add_field(name="⚔️ KD",       value=str(kd),                      inline=True)

    embed.add_field(name="💥 Combate",  value=str(stats["total_combat"]),   inline=True)
    embed.add_field(name="🗡️ Ataque",   value=str(stats["total_offense"]),  inline=True)
    embed.add_field(name="🛡️ Defensa",  value=str(stats["total_defense"]),  inline=True)
    embed.add_field(name="🤝 Apoyo",    value=str(stats["total_support"]),  inline=True)
    embed.add_field(name="🔪 TKs",      value=str(stats["total_teamkills"]), inline=True)

    if top_weapons:
        weapon_lines = "\n".join(
            f"{WEAPON_ICONS.get(w, '🔸')} **{w}**: {k} kills"
            for w, k in top_weapons
        )
        embed.add_field(name="🔫 Top Armas", value=weapon_lines, inline=False)

    embed.set_footer(text=f"📅 Desde {date_from} hasta {date_to}  •  [LATAM] Hagamos Garris · HLL Stats Bot")
    await interaction.followup.send(embed=embed)


async def cmd_stats_games(interaction: discord.Interaction):
    await interaction.response.defer()

    player_id = get_player_id_by_discord(str(interaction.user.id))
    if not player_id:
        await interaction.followup.send(embed=_not_registered_embed(), ephemeral=True)
        return

    games = get_player_recent_games(player_id, limit=5)
    if not games:
        embed = discord.Embed(
            title="⚠️ Sin partidas",
            description="No tenés partidas registradas aún.",
            color=0xF1C40F,
        )
        await interaction.followup.send(embed=embed)
        return

    embed = discord.Embed(
        title=f"🎮 Últimas 5 partidas",
        color=0x5865F2,
    )

    for g in games:
        start = g.get("start_time")
        ts    = f"<t:{int(start.timestamp())}:d>" if start else "?"
        side  = "🟦" if g.get("team_side") == "allied" else "🟥" if g.get("team_side") == "axis" else "⬜"
        kd    = float(g.get("kill_death_ratio") or 0)
        hours = round(g.get("time_seconds", 0) / 3600, 1)

        # Arma con más kills en esa partida
        weapons = g.get("weapons") or {}
        if isinstance(weapons, str):
            try:
                weapons = json.loads(weapons)
            except Exception:
                weapons = {}
        top_w = max(weapons, key=weapons.get, default=None) if weapons else None
        gun   = f"{WEAPON_ICONS.get(top_w,'🔸')} {top_w} ({weapons[top_w]}k)" if top_w else "—"

        embed.add_field(
            name=f"{side} {g['map_name']} · {ts}",
            value=(
                f"💀 {g['kills']}K / {g['deaths']}D · KD {kd:.2f}\n"
                f"🔫 {gun} · ⏱️ {hours}h\n"
                f"💥 {g['combat']} · 🗡️ {g['offense']} · 🛡️ {g['defense']} · 🤝 {g['support']}"
            ),
            inline=False,
        )

    now_str = datetime.now(TZ_UY).strftime("%d/%m/%Y")
    embed.set_footer(text=f"📅 Consultado al {now_str}  •  [LATAM] Hagamos Garris · HLL Stats Bot")
    await interaction.followup.send(embed=embed)