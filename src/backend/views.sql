CREATE OR REPLACE VIEW v_games_with_details AS
SELECT
    g.id,
    g.slug,
    g.name,
    g.released,
    g.rating,
    g.ratings_count,
    g.metacritic,
    g.playtime,
    g.updated_at,
    g.created_at,
    STRING_AGG(DISTINCT gen.name, ', ') AS genres,
    STRING_AGG(DISTINCT p.name, ', ') AS platforms,
    STRING_AGG(DISTINCT s.name, ', ') AS stores,
    STRING_AGG(DISTINCT t.name, ', ') AS tags
FROM
    games g
LEFT JOIN
    game_genres gg ON g.id = gg.game_id
LEFT JOIN
    genres gen ON gg.genre_id = gen.id
LEFT JOIN
    game_platforms gp ON g.id = gp.game_id
LEFT JOIN
    platforms p ON gp.platform_id = p.id
LEFT JOIN
    game_stores gs ON g.id = gs.store_id
LEFT JOIN
    stores s ON gs.store_id = s.id
LEFT JOIN
    game_tags gt ON g.id = gt.game_id
LEFT JOIN
    tags t ON gt.tag_id = t.id
GROUP BY
    g.id;
