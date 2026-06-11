#!/usr/bin/env python3
"""
main.py  –  Punto de entrada de HLL Stats
Uso:
    python main.py init-db
    python main.py collect [--pages N]
    python main.py report-top [--limit N]
    python main.py post-match <match_id>
"""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("hll_stats")


def cmd_init_db(_args):
    from db.database import init_db
    init_db()
    print("✅ Base de datos inicializada.")


def cmd_collect(args):
    from collectors.history_collector import collect_history
    from discord.webhook import send_collection_report

    pages = args.pages
    logger.info("Iniciando recolección — %s páginas", pages or "todas")
    counters = collect_history(max_pages=pages)

    print(
        f"\n📦 Resultado:\n"
        f"  Nuevas partidas:      {counters['new_matches']}\n"
        f"  Ya existían:          {counters['skipped']}\n"
        f"  Players actualizados: {counters['players_upserted']}\n"
        f"  Errores:              {counters['errors']}\n"
    )

    if args.notify:
        send_collection_report(counters)
        print("📣 Reporte enviado a Discord.")


def cmd_report_top(args):
    from db.database import get_player_totals
    from discord.webhook import send_top_players

    players = get_player_totals(limit=args.limit)
    if not players:
        print("⚠️  No hay jugadores en la DB. Corré 'collect' primero.")
        return

    # Mostrar en consola
    print(f"\n{'Pos':<4} {'Jugador':<25} {'Kills':>6} {'Deaths':>7} {'KD':>6} {'Partidas':>9}")
    print("-" * 65)
    for i, p in enumerate(players, 1):
        print(
            f"{i:<4} {p['name']:<25} {p['total_kills']:>6} "
            f"{p['total_deaths']:>7} {float(p['overall_kd'] or 0):>6.2f} {p['matches_played']:>9}"
        )

    if args.notify:
        send_top_players(players)
        print("\n📣 Ranking enviado a Discord.")


def cmd_post_match(args):
    from db.database import get_recent_matches, get_match_top_players
    from discord.webhook import send_match_summary

    match_id = args.match_id
    matches  = get_recent_matches(limit=100)
    match    = next((m for m in matches if m["match_id"] == match_id), None)

    if not match:
        print(f"❌ Match {match_id} no encontrado en la DB.")
        return

    top = get_match_top_players(match_id, limit=5)
    ok  = send_match_summary(match, top)
    print("✅ Enviado a Discord." if ok else "❌ Error al enviar.")


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="HLL Stats CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # init-db
    sub.add_parser("init-db", help="Crea las tablas en PostgreSQL")

    # collect
    p_collect = sub.add_parser("collect", help="Descarga historial y guarda en DB")
    p_collect.add_argument("--pages", type=int, default=None,
                           help="Cantidad de páginas a procesar (default: settings.HISTORY_PAGES)")
    p_collect.add_argument("--notify", action="store_true",
                           help="Enviar reporte a Discord al terminar")

    # report-top
    p_top = sub.add_parser("report-top", help="Muestra / postea top jugadores")
    p_top.add_argument("--limit", type=int, default=10)
    p_top.add_argument("--notify", action="store_true")

    # post-match
    p_pm = sub.add_parser("post-match", help="Postea resumen de una partida específica")
    p_pm.add_argument("match_id", type=int)

    args = parser.parse_args()
    commands = {
        "init-db":    cmd_init_db,
        "collect":    cmd_collect,
        "report-top": cmd_report_top,
        "post-match": cmd_post_match,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
