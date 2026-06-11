# HLL Stats 🎖️


# Por fecha específica
python main.py report-top --mode kills --date 2026-06-10 --limit 15 --notify

# Hoy
python main.py report-top --mode kills --period day --limit 15 --notify

# Esta semana
python main.py report-top --mode efficiency --period week --limit 15 --notify

Sistema de estadísticas para Hell Let Loose que recolecta datos históricos del servidor
**[LATAM] Hagamos Garris**, los persiste en PostgreSQL y los publica en Discord via webhook.

## Estructura

```
hll_stats/
├── config/
│   └── settings.py          # Variables de entorno / configuración
├── collectors/
│   ├── api_client.py        # Wrapper para los endpoints HLL
│   └── history_collector.py # Descarga historial y guarda en DB
├── db/
│   ├── schema.sql           # Tablas, índices y vistas
│   └── database.py          # Conexión y operaciones CRUD
├── discord/
│   └── webhook.py           # Embeds y envío a Discord
├── main.py                  # CLI principal
├── requirements.txt
└── .env.example
```

## Instalación

```bash
# 1. Clonar / descomprimir el proyecto
cd hll_stats

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables
cp .env.example .env
# Editar .env con tus datos de DB y Discord

# 5. Cargar .env (o exportar las variables manualmente)
export $(grep -v '^#' .env | xargs)
```

## Uso

### Inicializar la base de datos
```bash
python main.py init-db
```

### Recolectar historial
```bash
# 5 páginas (250 partidas)
python main.py collect

# N páginas específicas
python main.py collect --pages 20

# Recolectar Y notificar a Discord
python main.py collect --pages 10 --notify
```

### Ver / postear top jugadores
```bash
# Solo consola
python main.py report-top --limit 10

# Consola + Discord
python main.py report-top --limit 10 --notify
```

### Postear resumen de una partida
```bash
python main.py post-match 2297
```

## Base de datos

### Tablas principales
| Tabla | Descripción |
|---|---|
| `players` | Jugadores únicos con su última info de Steam |
| `matches` | Partidas históricas (una fila por partida) |
| `match_player_stats` | Estadísticas por jugador por partida |

### Vistas útiles
```sql
-- Top jugadores global
SELECT * FROM player_totals ORDER BY total_kills DESC LIMIT 20;

-- Resumen de últimas partidas
SELECT * FROM match_summary LIMIT 10;

-- Stats de un jugador específico
SELECT m.map_name, mps.kills, mps.deaths, mps.kill_death_ratio, mps.combat
FROM match_player_stats mps
JOIN matches m USING (match_id)
WHERE mps.player_name ILIKE '%Dimitri%'
ORDER BY m.start_time DESC;
```

## Endpoints de la API usados

| Endpoint | Uso |
|---|---|
| `get_scoreboard_maps` | Lista paginada de partidas históricas |
| `get_map_scoreboard`  | Detalle con player_stats de una partida |
| `get_public_info`     | Info actual del servidor (disponible para futuro live) |
| `get_live_game_stats` | Stats en vivo (disponible para futuro live) |

## Próximos pasos sugeridos
- Agregar un scheduler (APScheduler o cron) para recolectar automáticamente
- Comando `!stats <jugador>` via bot de Discord (discord.py)
- Dashboard web con FastAPI + Chart.js
- Detección automática de partidas nuevas y post inmediato
