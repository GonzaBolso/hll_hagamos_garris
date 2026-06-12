import notifications


async def cmd_help(interaction: notifications.Interaction):
    embed = notifications.Embed(
        title="📖 Comandos HLL Stats",
        description="Stats del servidor **[LATAM] Hagamos Garris**",
        color=0x5865F2,
    )
    embed.add_field(name="📋 Registro", value=(
        "`/hll register <steam_id>` — Vinculá tu Steam ID con tu cuenta de Discord\n"
        "ej: `/hll register 76561198012345678`"
    ), inline=False)
    embed.add_field(name="📊 Stats personales", value=(
        "`/stats show` — Tus stats totales del año actual\n"
        "`/stats show mes:true` — Tus stats del mes actual\n"
        "`/stats games` — Tus últimas 5 partidas"
    ), inline=False)
    embed.add_field(name="🏆 Rankings", value=(
        "`/leaderboard` — Top 20 por kills (año actual)\n"
        "`/leaderboard mes:true` — Top 20 del mes actual"
    ), inline=False)
    embed.add_field(name="🔫 Armas", value=(
        "`/weapon <nombre>` — Top 20 jugadores con esa arma\n"
        "ej: `/weapon M1 GARAND`"
    ), inline=False)
    embed.set_footer(text="[LATAM] Hagamos Garris · HLL Stats Bot")
    await interaction.response.send_message(embed=embed)