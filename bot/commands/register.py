import notifications
from db.database import register_discord_player, search_player_by_name


async def cmd_register(interaction: notifications.Interaction, steam_id: str):
    steam_id = steam_id.strip()

    # Validar que sea un Steam ID válido (17 dígitos numéricos)
    if not steam_id.isdigit() or len(steam_id) != 17:
        embed = notifications.Embed(
            title="❌ Steam ID inválido",
            description=(
                "El Steam ID debe ser de 17 dígitos numéricos.\n\n"
                "**¿Cómo encontrar tu Steam ID?**\n"
                "1. Abrí [steamid.io](https://steamid.io)\n"
                "2. Ingresá tu perfil de Steam\n"
                "3. Copiá el **steamID64** (empieza con `7656...`)\n\n"
                f"Ejemplo: `/hll register 76561198012345678`"
            ),
            color=0xE74C3C,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Buscar si el player_id existe en la DB
    await interaction.response.defer()

    players = search_player_by_name("")  # no es lo que queremos, buscar por ID directo
    # Buscar directo por player_id
    from db.database import db_cursor
    with db_cursor(commit=False) as cur:
        cur.execute("SELECT player_id, name, avatar_url FROM players WHERE player_id = %s", (steam_id,))
        row = cur.fetchone()

    if not row:
        embed = notifications.Embed(
            title="❌ Jugador no encontrado",
            description=(
                f"El Steam ID `{steam_id}` no tiene partidas registradas en el servidor.\n\n"
                "Asegurate de haber jugado al menos una partida en **[LATAM] Hagamos Garris**."
            ),
            color=0xE74C3C,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    player_id   = row["player_id"]
    player_name = row["name"]
    avatar_url  = row.get("avatar_url")

    is_new = register_discord_player(
        discord_id=str(interaction.user.id),
        discord_name=str(interaction.user),
        player_id=player_id,
    )

    embed = notifications.Embed(
        title="✅ Registro exitoso" if is_new else "🔄 Registro actualizado",
        description=f"Tu cuenta de Discord fue vinculada con **{player_name}**.",
        color=0x2ECC71,
    )
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)
    embed.add_field(name="Steam ID", value=f"`{player_id}`", inline=True)
    embed.add_field(name="Discord", value=interaction.user.mention, inline=True)
    embed.set_footer(text="[LATAM] Hagamos Garris · HLL Stats Bot")

    await interaction.followup.send(embed=embed)