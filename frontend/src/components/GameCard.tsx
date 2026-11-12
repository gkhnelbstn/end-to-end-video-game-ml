import { Link } from "react-router-dom";

import type { Game } from "../types";
import { Cover, CriticScore, ExpectedLine, RECEPTION_LABEL, ReceptionStrip, receptionOf, year } from "./ui";

export default function GameCard({ game }: { game: Game }) {
  const platforms = game.platforms.map((p) => p.name);
  const genres = game.genres.slice(0, 2).map((g) => g.name);
  return (
    <Link to={`/games/${game.id}`} className="card">
      <div className="card-media">
        <Cover game={game} />
      </div>
      <div className="card-body">
        <span className="card-title">{game.name}</span>
        <span className="card-meta">
          {[year(game.released), genres.join(" / "), platforms.length > 0 && platformSummary(platforms)]
            .filter(Boolean)
            .join(" · ")}
        </span>
        <div className="card-reception">
          {game.metacritic !== null ? (
            <>
              <ReceptionStrip actual={game.metacritic} />
              <span className="card-verdict">
                <CriticScore value={game.metacritic} size="sm" />
                {RECEPTION_LABEL[receptionOf(game.metacritic)]}
              </span>
            </>
          ) : game.expected ? (
            <>
              <ReceptionStrip expected={game.expected} />
              <ExpectedLine expected={game.expected} />
            </>
          ) : (
            <span className="card-unscored">Not reviewed yet</span>
          )}
        </div>
      </div>
    </Link>
  );
}

function platformSummary(platforms: string[]): string {
  return platforms.length > 2 ? `${platforms[0]} +${platforms.length - 1}` : platforms.join(", ");
}
