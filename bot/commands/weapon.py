from datetime import datetime, timezone, timedelta

import discord

from db.database import get_top_by_weapon

TZ_UY = timezone(timedelta(hours=-3))


def _medals(i: int) -> str:
    return ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."


def _country_flag(country: str | None) -> str:
    if country and len(country) == 2:
        return f":flag_{country.lower()}: "
    return ""


async def cmd_weapon(interaction: discord.Interaction, weapon_name: str):
    await interaction.response.defer()

    year = datetime.now(TZ_UY).year
    weapon_upper = weapon_name.strip().upper()

    players = get_top_by_weapon(weapon_name=weapon_upper, limit=20, year=year)

    if not players:
        # Intentar búsqueda case-insensitive desde la DB
        from db.database import db_cursor
        with db_cursor(commit=False) as cur:
            cur.execute("""
                SELECT DISTINCT jsonb_object_keys(weapons) AS weapon
                FROM match_player_stats
                WHERE weapons::text ILIKE %s
                LIMIT 5
            """, (f"%{weapon_name}%",))
            suggestions = [row[0] for row in cur.fetchall()]

        embed = discord.Embed(
            title=f"❌ Arma no encontrada: `{weapon_name}`",
            color=0xE74C3C,
        )
        if suggestions:
            embed.add_field(
                name="¿Quisiste decir?",
                value="\n".join(f"• `{s}`" for s in suggestions),
                inline=False,
            )
        else:
            embed.description = "No se encontraron kills con esa arma. Verificá el nombre exacto."
        await interaction.followup.send(embed=embed)
        return

    lines = []
    for i, p in enumerate(players):
        flag = _country_flag(p.get("country"))
        lines.append(
            f"{_medals(i)} {flag}**{p['name']}** — "
            f"**{p['weapon_kills']}** kills · {p['matches_played']} partidas"
        )

    embed = discord.Embed(
        title=f"🔫 Top 20 — {weapon_upper} — Año {year}",
        description="\n".join(lines),
        color=0x5865F2,
    )
    if players[0].get("avatar_url"):
        embed.set_thumbnail(url=players[0]["avatar_url"])
    embed.set_footer(text="[LATAM] Hagamos Garris · HLL Stats Bot")
    await interaction.followup.send(embed=embed)