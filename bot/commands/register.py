import re
import discord
from db.database import db_cursor, register_discord_player

# Steam ID: 17 dígitos empezando con 7656
STEAM_ID_RE = re.compile(r'^7656\d{13}$')
# Console ID: 32 caracteres hex
CONSOLE_ID_RE = re.compile(r'^[0-9a-f]{32}$', re.IGNORECASE)


async def cmd_register(interaction: discord.Interaction, steam_id: str):
    player_id = steam_id.strip()

    is_steam   = bool(STEAM_ID_RE.match(player_id))
    is_console = bool(CONSOLE_ID_RE.match(player_id))

    if not is_steam and not is_console:
        embed = discord.Embed(
            title="❌ ID inválido",
            description=(
                "El ID debe ser uno de estos formatos:\n\n"
                "**Steam ID** (17 dígitos)\n"
                "`76561198012345678`\n"
                "→ Encontralo en [steamid.io](https://steamid.io)\n\n"
                "**ID de consola** (32 caracteres hex)\n"
                "`d66c722930f492700a933ecbecd8824b`\n"
                "→ Visible en el scoreboard del juego"
            ),
            color=0xE74C3C,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await interaction.response.defer()

    with db_cursor(commit=False) as cur:
        cur.execute("SELECT player_id, name, avatar_url FROM players WHERE player_id = %s", (player_id,))
        row = cur.fetchone()

    if not row:
        id_type = "Steam ID" if is_steam else "ID de consola"
        embed = discord.Embed(
            title="❌ Jugador no encontrado",
            description=(
                f"El {id_type} `{player_id}` no tiene partidas registradas en el servidor.\n\n"
                "Asegurate de haber jugado al menos una partida en **[LATAM] Hagamos Garris**."
            ),
            color=0xE74C3C,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    player_name = row["name"]
    avatar_url  = row.get("avatar_url")

    is_new = register_discord_player(
        discord_id=str(interaction.user.id),
        discord_name=str(interaction.user),
        player_id=player_id,
    )

    embed = discord.Embed(
        title="✅ Registro exitoso" if is_new else "🔄 Registro actualizado",
        description=f"Tu cuenta de Discord fue vinculada con **{player_name}**.",
        color=0x2ECC71,
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)
    id_type = "Steam ID" if is_steam else "ID de consola"
    embed.add_field(name=id_type, value=f"`{player_id}`", inline=True)
    embed.add_field(name="Discord", value=interaction.user.mention, inline=True)
    embed.set_footer(text="[LATAM] Hagamos Garris · HLL Stats Bot")
    await interaction.followup.send(embed=embed)