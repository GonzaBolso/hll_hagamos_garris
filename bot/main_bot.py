"""
bot/main_bot.py  –  Bot de Discord para HLL Stats
"""
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from discord import app_commands

from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("hll_bot")

intents = discord.Intents.default()
client  = discord.Client(intents=intents)
tree    = app_commands.CommandTree(client)
GUILD   = discord.Object(id=settings.GUILD_ID)


async def weapon_autocomplete_cb(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    from bot.commands.weapon import weapon_autocomplete
    return await weapon_autocomplete(interaction, current)


def _check_channel(interaction: discord.Interaction) -> bool:
    if settings.CHANNEL_ID and interaction.channel_id != settings.CHANNEL_ID:
        return False
    return True


# ── /hll ──────────────────────────────────────

hll_group = app_commands.Group(name="hll", description="Comandos HLL Stats")

@hll_group.command(name="help", description="Muestra todos los comandos disponibles")
async def hll_help(interaction: discord.Interaction):
    if not _check_channel(interaction):
        await interaction.response.send_message(f"❌ Este comando solo funciona en <#{settings.CHANNEL_ID}>", ephemeral=True)
        return
    from bot.commands.help import cmd_help
    await cmd_help(interaction)

@hll_group.command(name="register", description="Vinculá tu Steam ID con tu cuenta de Discord")
@app_commands.describe(steam_id="Tu Steam ID de 64 bits (ej: 76561198012345678)")
async def hll_register(interaction: discord.Interaction, steam_id: str):
    if not _check_channel(interaction):
        await interaction.response.send_message(f"❌ Este comando solo funciona en <#{settings.CHANNEL_ID}>", ephemeral=True)
        return
    from bot.commands.register import cmd_register
    await cmd_register(interaction, steam_id)

tree.add_command(hll_group, guild=GUILD)


# ── /stats ────────────────────────────────────

stats_group = app_commands.Group(name="stats", description="Tus estadísticas personales")

@stats_group.command(name="show", description="Tus stats del año actual (o mes actual)")
@app_commands.describe(mes="True para ver solo este mes")
async def stats_show(interaction: discord.Interaction, mes: bool = False):
    if not _check_channel(interaction):
        await interaction.response.send_message(f"❌ Este comando solo funciona en <#{settings.CHANNEL_ID}>", ephemeral=True)
        return
    from bot.commands.stats import cmd_stats_show
    await cmd_stats_show(interaction, mes=mes)

@stats_group.command(name="games", description="Tus últimas 5 partidas")
async def stats_games(interaction: discord.Interaction):
    if not _check_channel(interaction):
        await interaction.response.send_message(f"❌ Este comando solo funciona en <#{settings.CHANNEL_ID}>", ephemeral=True)
        return
    from bot.commands.stats import cmd_stats_games
    await cmd_stats_games(interaction)

tree.add_command(stats_group, guild=GUILD)


# ── /leaderboard ──────────────────────────────

@tree.command(name="leaderboard", description="Top 20 jugadores por kills", guild=GUILD)
@app_commands.describe(mes="True para ver solo este mes")
async def leaderboard(interaction: discord.Interaction, mes: bool = False):
    if not _check_channel(interaction):
        await interaction.response.send_message(f"❌ Este comando solo funciona en <#{settings.CHANNEL_ID}>", ephemeral=True)
        return
    from bot.commands.leaderboard import cmd_leaderboard
    await cmd_leaderboard(interaction, mes=mes)


# ── /weapon ───────────────────────────────────

@tree.command(name="weapon", description="Top 20 jugadores con un arma específica", guild=GUILD)
@app_commands.describe(weapon_name="Nombre del arma (ej: M1 GARAND, MP40, STG44)")
@app_commands.autocomplete(weapon_name=weapon_autocomplete_cb)
async def weapon(interaction: discord.Interaction, weapon_name: str):
    if not _check_channel(interaction):
        await interaction.response.send_message(f"❌ Este comando solo funciona en <#{settings.CHANNEL_ID}>", ephemeral=True)
        return
    from bot.commands.weapon import cmd_weapon
    await cmd_weapon(interaction, weapon_name)


# ── Eventos ───────────────────────────────────

@client.event
async def on_ready():
    await tree.sync(guild=GUILD)
    logger.info("Bot conectado como %s | Guild %s", client.user, settings.GUILD_ID)


if __name__ == "__main__":
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN no configurado.")
        sys.exit(1)
    client.run(settings.BOT_TOKEN)