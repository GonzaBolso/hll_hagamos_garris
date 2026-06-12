from datetime import datetime, timezone, timedelta

import notifications

from db.database import get_player_totals

TZ_UY = timezone(timedelta(hours=-3))


def _medals(i: int) -> str:
    return ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."


def _country_flag(country: str | None) -> str:
    if country and len(country) == 2:
        return f":flag_{country.lower()}: "
    return ""


async def cmd_leaderboard(interaction: notifications.Interaction, mes: bool = False):
    await interaction.response.defer()

    now   = datetime.now(TZ_UY)
    year  = now.year
    month = now.month if mes else None
    label = f"{now.strftime('%B %Y')}" if mes else f"Año {year}"

    # Usamos period=None pero filtramos por año/mes con date_str logic
    # Para año usamos _period_filter extendido — llamamos directo a la query con año
    from db.database import db_cursor, _date_filter
    conditions = ["TRUE"]
    params: list = []

    conditions.append("EXTRACT(YEAR FROM m.start_time AT TIME ZONE 'America/Montevideo') = %s")
    params.append(year)
    if month:
        conditions.append("EXTRACT(MONTH FROM m.start_time AT TIME ZONE 'America/Montevideo') = %s")
        params.append(month)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            p.name, p.country,
            SUM(mps.kills)   AS total_kills,
            SUM(mps.deaths)  AS total_deaths,
            CASE WHEN SUM(mps.deaths) > 0
                 THEN ROUND(SUM(mps.kills)::numeric / SUM(mps.deaths), 2)
                 ELSE SUM(mps.kills) END AS kd_ratio,
            COUNT(DISTINCT mps.match_id) AS matches_played
        FROM match_player_stats mps
        JOIN players p USING (player_id)
        JOIN matches m USING (match_id)
        WHERE {where}
        GROUP BY p.player_id, p.name, p.country
        ORDER BY total_kills DESC
        LIMIT 20
    """
    with db_cursor(commit=False) as cur:
        cur.execute(sql, params)
        players = [dict(row) for row in cur.fetchall()]

    if not players:
        embed = notifications.Embed(
            title="⚠️ Sin datos",
            description=f"No hay partidas registradas para {label}.",
            color=0xF1C40F,
        )
        await interaction.followup.send(embed=embed)
        return

    lines = []
    for i, p in enumerate(players):
        flag = _country_flag(p.get("country"))
        kd   = float(p.get("kd_ratio") or 0)
        lines.append(
            f"{_medals(i)} {flag}**{p['name']}** — "
            f"{p['total_kills']}K/{p['total_deaths']}D · KD **{kd}** · {p['matches_played']} partidas"
        )

    embed = notifications.Embed(
        title=f"🏆 Top 20 — Kills — {label}",
        description="\n".join(lines),
        color=0x5865F2,
    )
    embed.set_footer(text="[LATAM] Hagamos Garris · HLL Stats Bot")
    await interaction.followup.send(embed=embed)