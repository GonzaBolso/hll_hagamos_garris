from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands

from db.database import get_top_by_weapon, get_weapons_autocomplete

TZ_UY = timezone(timedelta(hours=-3))


def _medals(i: int) -> str:
    return ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."


def _country_flag(country: str | None) -> str:
    if country and len(country) == 2:
        return f":flag_{country.lower()}: "
    return ""


async def weapon_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    try:
        weapons = get_weapons_autocomplete(current.upper(), limit=10)
        return [app_commands.Choice(name=w, value=w) for w in weapons]
    except Exception:
        return []


async def cmd_weapon(interaction: discord.Interaction, weapon_name: str, mes: bool = False):
    await interaction.response.defer()

    now   = datetime.now(TZ_UY)
    year  = now.year
    month = now.month if mes else None
    label = f"{now.strftime('%B %Y')}" if mes else f"Año {year}"
    date_from = f"01/{now.month:02d}/{year}" if mes else f"01/01/{year}"
    date_to   = now.strftime("%d/%m/%Y")

    weapon_upper = weapon_name.strip().upper()
    players = get_top_by_weapon(weapon_name=weapon_upper, limit=20, year=year, month=month)

    if not players:
        from db.database import db_cursor
        with db_cursor(commit=False) as cur:
            cur.execute("""
                SELECT DISTINCT jsonb_object_keys(weapons) AS weapon
                FROM match_player_stats
                WHERE weapons::text ILIKE %s
                LIMIT 5
            """, (f"%{weapon_name}%",))
            suggestions = [row[0] for row in cur.fetchall()]

        embed = discord.Embed(title=f"❌ Arma no encontrada: `{weapon_name}`", color=0xE74C3C)
        if suggestions:
            embed.add_field(name="¿Quisiste decir?", value="\n".join(f"• `{s}`" for s in suggestions), inline=False)
        else:
            embed.description = "No se encontraron kills con esa arma."
        await interaction.followup.send(embed=embed)
        return

    lines = []
    for i, p in enumerate(players):
        flag = _country_flag(p.get("country"))
        lines.append(f"{_medals(i)} {flag}**{p['name']}** — **{p['weapon_kills']}** kills · {p['matches_played']} partidas")

    embed = discord.Embed(
        title=f"🔫 Top 20 — {weapon_upper} — {label}",
        description="\n".join(lines),
        color=0x5865F2,
    )
    if players[0].get("avatar_url"):
        embed.set_thumbnail(url=players[0]["avatar_url"])
    embed.set_footer(text=f"📅 Desde {date_from} hasta {date_to}  •  [LATAM] Hagamos Garris · HLL Stats Bot")
    await interaction.followup.send(embed=embed)