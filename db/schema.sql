-- ============================================================
--  HLL Stats Database Schema
-- ============================================================

-- Jugadores conocidos
CREATE TABLE IF NOT EXISTS players (
    player_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    steam_name      TEXT,
    country         TEXT,
    level           INTEGER,
    avatar_url      TEXT,
    first_seen_at   TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Migración: agregar avatar_url si la tabla ya existe
ALTER TABLE players ADD COLUMN IF NOT EXISTS avatar_url TEXT;

-- Recrear vista con avatar_url (DROP necesario para cambiar columnas)
DROP VIEW IF EXISTS player_totals;

-- Mapas / partidas históricas
CREATE TABLE IF NOT EXISTS matches (
    match_id        INTEGER PRIMARY KEY,
    map_id          TEXT NOT NULL,
    map_name        TEXT NOT NULL,
    game_mode       TEXT NOT NULL,
    environment     TEXT,
    start_time      TIMESTAMPTZ,
    end_time        TIMESTAMPTZ,
    score_allied    INTEGER,
    score_axis      INTEGER,
    winner          TEXT GENERATED ALWAYS AS (
                        CASE
                            WHEN score_allied > score_axis THEN 'allied'
                            WHEN score_axis > score_allied THEN 'axis'
                            ELSE 'draw'
                        END
                    ) STORED,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Estadísticas por jugador por partida
CREATE TABLE IF NOT EXISTS match_player_stats (
    id              SERIAL PRIMARY KEY,
    match_id        INTEGER NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    player_id       TEXT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    player_name     TEXT NOT NULL,
    team_side       TEXT,

    kills           INTEGER DEFAULT 0,
    deaths          INTEGER DEFAULT 0,
    kill_death_ratio NUMERIC(6,2),
    kills_per_minute NUMERIC(6,2),
    deaths_per_minute NUMERIC(6,2),
    kills_streak    INTEGER DEFAULT 0,
    teamkills       INTEGER DEFAULT 0,

    combat          INTEGER DEFAULT 0,
    offense         INTEGER DEFAULT 0,
    defense         INTEGER DEFAULT 0,
    support         INTEGER DEFAULT 0,

    time_seconds    INTEGER DEFAULT 0,
    longest_life_secs INTEGER DEFAULT 0,
    shortest_life_secs INTEGER DEFAULT 0,
    level           INTEGER,

    weapons         JSONB DEFAULT '{}',
    death_by_weapons JSONB DEFAULT '{}',
    most_killed     JSONB DEFAULT '{}',
    death_by        JSONB DEFAULT '{}',

    UNIQUE(match_id, player_id)
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_mps_player    ON match_player_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_mps_match     ON match_player_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_matches_start ON matches(start_time DESC);

-- Vista: totales históricos por jugador
CREATE OR REPLACE VIEW player_totals AS
SELECT
    p.player_id,
    p.name,
    p.country,
    p.avatar_url,
    COUNT(DISTINCT mps.match_id)                        AS matches_played,
    SUM(mps.kills)                                      AS total_kills,
    SUM(mps.deaths)                                     AS total_deaths,
    ROUND(SUM(mps.kills)::NUMERIC / NULLIF(SUM(mps.deaths), 0), 2) AS overall_kd,
    SUM(mps.combat)                                     AS total_combat,
    SUM(mps.offense)                                    AS total_offense,
    SUM(mps.defense)                                    AS total_defense,
    SUM(mps.support)                                    AS total_support,
    MAX(mps.kills_streak)                               AS best_kill_streak,
    MAX(mps.level)                                      AS max_level,
    p.last_seen_at
FROM players p
JOIN match_player_stats mps USING (player_id)
GROUP BY p.player_id, p.name, p.country, p.avatar_url, p.last_seen_at;

-- Vista: resumen de partidas recientes
CREATE OR REPLACE VIEW match_summary AS
SELECT
    m.match_id,
    m.map_name,
    m.game_mode,
    m.environment,
    m.start_time,
    m.end_time,
    EXTRACT(EPOCH FROM (m.end_time - m.start_time)) / 60 AS duration_minutes,
    m.score_allied,
    m.score_axis,
    m.winner,
    COUNT(mps.id)   AS players_count,
    SUM(mps.kills)  AS total_kills
FROM matches m
LEFT JOIN match_player_stats mps USING (match_id)
GROUP BY m.match_id
ORDER BY m.start_time DESC;