#!/usr/bin/env python3
"""
main.py  –  Punto de entrada de HLL Stats
Uso:
    python main.py init-db
    python main.py collect [--pages N] [--notify]
    python main.py report-top [--limit N] [--mode kills|hours|kd|efficiency] [--notify]
    python main.py post-match <match_id>
"""
import argparse
import logging

import time as _time

class _UYFormatter(logging.Formatter):
    """Formatter que muestra hora en Uruguay (UTC-3)."""
    def converter(self, timestamp):
        from datetime import datetime, timezone, timedelta
        return datetime.fromtimestamp(timestamp, tz=timezone(timedelta(hours=-3))).timetuple()

_handler = logging.StreamHandler()
_handler.setFormatter(_UYFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"))
logging.basicConfig(level=logging.INFO, handlers=[_handler])
logger = logging.getLogger("hll_stats")


def cmd_init_db(_args):
    from db.database import init_db
    init_db()
    print("✅ Base de datos inicializada.")


def cmd_collect(args):
    from datetime import datetime, timezone, timedelta
    from collectors.history_collector import collect_history
    from discord.webhook import send_collection_report

    # Ventana horaria: solo entre 15:00 y 03:00 Uruguay (UTC-3)
    TZ_UY = timezone(timedelta(hours=-3))
    now = datetime.now(TZ_UY)
    hour = now.hour
    if not (hour >= 15 or hour < 3):
        logger.info("Fuera de ventana horaria (%02d:%02d UY). No se juega, saltando recolección.", hour, now.minute)
        return

    pages = args.pages
    logger.info("Iniciando recolección — %s", f"{pages} páginas máx." if pages else "modo incremental")
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
    from db.database import (
        get_player_totals, get_top_hours,
        get_top_kd, get_top_kills_per_hour,
    )
    from discord.webhook import send_top_players, send_top_hours, send_top_kd, send_top_efficiency

    mode   = args.mode
    limit  = args.limit
    period = args.period
    date_str = getattr(args, 'date', None)

    PERIOD_LABELS = {"day": "Hoy", "week": "Esta Semana", "month": "Este Mes", None: "Histórico"}
    if date_str:
        period_label = date_str
    else:
        period_label = PERIOD_LABELS.get(period, "Histórico")

    if mode == "kills":
        players = get_player_totals(limit=limit, period=period, date_str=date_str)
        if not players:
            print("⚠️  No hay jugadores en la DB.")
            return
        print(f"\n🏆 TOP {limit} — KILLS — {period_label.upper()}")
        print(f"{'#':<4} {'Jugador':<25} {'Kills':>7} {'Deaths':>7} {'KD':>6} {'Partidas':>9}")
        print("─" * 65)
        for i, p in enumerate(players, 1):
            print(f"{i:<4} {p['name']:<25} {p['total_kills']:>7} "
                  f"{p['total_deaths']:>7} {float(p['overall_kd'] or 0):>6.2f} {p['matches_played']:>9}")
        if args.notify:
            send_top_players(players, period_label=period_label)

    elif mode == "hours":
        players = get_top_hours(limit=limit, period=period, date_str=date_str)
        if not players:
            print("⚠️  No hay datos de tiempo jugado.")
            return
        print(f"\n⏱️  TOP {limit} — HORAS JUGADAS — {period_label.upper()}")
        print(f"{'#':<4} {'Jugador':<25} {'Horas':>7} {'Kills':>7} {'Partidas':>9}")
        print("─" * 60)
        for i, p in enumerate(players, 1):
            print(f"{i:<4} {p['name']:<25} {float(p['total_hours']):>7.1f} "
                  f"{p['total_kills']:>7} {p['matches_played']:>9}")
        if args.notify:
            send_top_hours(players, period_label=period_label)

    elif mode == "kd":
        players = get_top_kd(limit=limit, min_matches=args.min_matches, period=period, date_str=date_str)
        if not players:
            print(f"⚠️  No hay jugadores con {args.min_matches}+ partidas.")
            return
        print(f"\n⚔️  TOP {limit} — MEJOR KD — {period_label.upper()} (mín. {args.min_matches} partidas)")
        print(f"{'#':<4} {'Jugador':<25} {'KD':>6} {'Kills':>7} {'Deaths':>7} {'Partidas':>9}")
        print("─" * 65)
        for i, p in enumerate(players, 1):
            print(f"{i:<4} {p['name']:<25} {float(p['kd_ratio']):>6.2f} "
                  f"{p['total_kills']:>7} {p['total_deaths']:>7} {p['matches_played']:>9}")
        if args.notify:
            send_top_kd(players, min_matches=args.min_matches, period_label=period_label)

    elif mode == "efficiency":
        players = get_top_kills_per_hour(limit=limit, min_hours=args.min_hours, period=period, date_str=date_str)
        if not players:
            print(f"⚠️  No hay jugadores con {args.min_hours}+ horas jugadas.")
            return
        print(f"\n🎯 TOP {limit} — KILLS/HORA — {period_label.upper()} (mín. {args.min_hours}h)")
        print(f"{'#':<4} {'Jugador':<25} {'K/h':>6} {'Kills':>7} {'Horas':>7} {'Partidas':>9}")
        print("─" * 65)
        for i, p in enumerate(players, 1):
            print(f"{i:<4} {p['name']:<25} {float(p['kills_per_hour']):>6.2f} "
                  f"{p['total_kills']:>7} {float(p['total_hours']):>7.1f} {p['matches_played']:>9}")
        if args.notify:
            send_top_efficiency(players, min_hours=args.min_hours, period_label=period_label)

    if args.notify:
        print("📣 Ranking enviado a Discord.")


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

def cmd_worker(_args):
    """Loop infinito: corre collect cada hora."""
    import time
    from datetime import datetime, timezone, timedelta
    TZ_UY = timezone(timedelta(hours=-3))

    logger.info("Worker iniciado. Ciclo cada 60 minutos.")
    while True:
        now = datetime.now(TZ_UY)
        logger.info("Ciclo worker — %s", now.strftime("%H:%M UY"))

        class _FakeArgs:
            pages = None
            notify = True

        cmd_collect(_FakeArgs())

        logger.info("Próximo ciclo en 60 minutos.")
        time.sleep(60 * 60)


def main():
    parser = argparse.ArgumentParser(description="HLL Stats CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # init-db
    sub.add_parser("init-db", help="Crea las tablas en PostgreSQL")

    # collect
    p_collect = sub.add_parser("collect", help="Descarga historial y guarda en DB")
    p_collect.add_argument("--pages", type=int, default=None,
                           help="Límite de páginas (default: incremental hasta no haber novedades)")
    p_collect.add_argument("--notify", action="store_true")

    # report-top
    p_top = sub.add_parser("report-top", help="Muestra / postea rankings")
    p_top.add_argument("--limit", type=int, default=10)
    p_top.add_argument(
        "--mode",
        choices=["kills", "hours", "kd", "efficiency"],
        default="kills",
        help="kills=total kills | hours=horas jugadas | kd=mejor KD | efficiency=kills/hora",
    )
    p_top.add_argument(
        "--period",
        choices=["day", "week", "month"],
        default=None,
        help="Período: day=hoy | week=7 días | month=30 días | (sin valor)=histórico",
    )
    p_top.add_argument("--date", type=str, default=None,
                       help="Fecha específica en formato YYYY-MM-DD (ej: 2026-06-10)")
    p_top.add_argument("--min-matches", type=int, default=5,
                       help="Mínimo de partidas para el ranking KD (default: 10)")
    p_top.add_argument("--min-hours", type=float, default=2.0,
                       help="Mínimo de horas para el ranking efficiency (default: 2)")
    p_top.add_argument("--notify", action="store_true")

    # worker
    sub.add_parser("worker", help="Loop infinito: collect cada hora")

    # post-match
    p_pm = sub.add_parser("post-match", help="Postea resumen de una partida")
    p_pm.add_argument("match_id", type=int)

    args = parser.parse_args()
    commands = {
        "init-db":    cmd_init_db,
        "collect":    cmd_collect,
        "report-top": cmd_report_top,
        "post-match": cmd_post_match,
        "worker":     cmd_worker,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()