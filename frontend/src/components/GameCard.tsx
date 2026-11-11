import { Link } from "react-router-dom";

import type { Game } from "../types";
import { Cover, Score, year } from "./ui";

export default function GameCard({ game }: { game: Game }) {
  const platforms = game.platforms.map((p) => p.name);
  return (
    <Link to={`/games/${game.id}`} className="game-card">
      <div className="game-card-media">
        <Cover game={game} />
        {game.metacritic !== null && (
          <span className="game-card-score">
            <Score value={game.metacritic} size="sm" title="Metacritic" />
          </span>
        )}
      </div>
      <div className="game-card-body">
        <span className="game-card-title">{game.name}</span>
        <span className="game-card-meta">
          {year(game.released)}
          {platforms.length > 0 && (
            <>
              {" · "}
              {platforms.slice(0, 2).join(", ")}
              {platforms.length > 2 && ` +${platforms.length - 2}`}
            </>
          )}
        </span>
        {game.genres.length > 0 && (
          <div className="chips">
            {game.genres.slice(0, 3).map((g) => (
              <span className="chip" key={g.id}>
                {g.name}
              </span>
            ))}
          </div>
        )}
      </div>
    </Link>
  );
}
