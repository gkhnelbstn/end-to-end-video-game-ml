import argparse
import ast
import contextlib
import csv
import os
from datetime import datetime
from pathlib import Path

from src.backend import crud, schemas
from src.backend.database import SessionLocal

# Some cells (platform requirements, tags) are far larger than csv's 128 KiB default.
csv.field_size_limit(2**31 - 1)

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data/raw")).resolve()


def parse_float(value):
    if value in (None, "", "null", "None"):
        return None
    try:
        return float(value)
    except Exception:
        return None


def parse_int(value):
    if value in (None, "", "null", "None"):
        return None
    try:
        return int(value)
    except Exception:
        return None


def parse_datetime(value):
    if not value or value in ("", "null", "None"):
        return None
    try:
        # CSV has YYYY-MM-DD or ISO timestamp
        if len(value) == 10:
            return datetime.fromisoformat(value)
        else:
            # attempt datetime with time
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def ensure_list(value):
    if not value:
        return []
    try:
        res = ast.literal_eval(value)
        if isinstance(res, list):
            return res
        return []
    except Exception:
        return []


def to_game_create(row: dict) -> schemas.GameCreate | None:
    try:
        game_id = parse_int(row.get("id"))
        slug = row.get("slug")
        name = row.get("name")
        # Require a valid ID, slug, and name; otherwise skip
        if game_id is None or not slug or not name:
            return None

        released = parse_datetime(row.get("released"))
        rating = parse_float(row.get("rating"))
        ratings_count = parse_int(row.get("ratings_count"))
        metacritic = parse_int(row.get("metacritic"))
        playtime = parse_int(row.get("playtime"))
        # Media fields (optional)
        background_image = row.get("background_image") or None
        clip = None
        # some CSVs may have 'clip' as a URL string or a JSON-like dict
        raw_clip = row.get("clip")
        if raw_clip:
            try:
                # try literal_eval to handle dict-like strings
                parsed = ast.literal_eval(raw_clip)
                if isinstance(parsed, dict):
                    clip = parsed.get("clip") or parsed.get("url") or None
                elif isinstance(parsed, str):
                    clip = parsed
            except Exception:
                clip = raw_clip

        # Parse nested lists
        platforms_raw = ensure_list(row.get("platforms"))
        stores_raw = ensure_list(row.get("stores"))
        genres_raw = ensure_list(row.get("genres"))
        tags_raw = ensure_list(row.get("tags"))

        platforms = []
        for item in platforms_raw:
            # item looks like {'platform': {'id': 4, 'name': 'PC', 'slug': 'pc'}}
            if isinstance(item, dict) and "platform" in item and isinstance(item["platform"], dict):
                p = item["platform"]
                try:
                    pid = parse_int(p.get("id"))
                    if pid is None:
                        continue
                    platforms.append(
                        schemas.Platform(
                            id=pid,
                            name=str(p.get("name")),
                            slug=str(p.get("slug")),
                        )
                    )
                except Exception:
                    continue

        stores = []
        for item in stores_raw:
            # item looks like {'store': {'id': 1, 'name': 'Steam', 'slug': 'steam'}}
            if isinstance(item, dict) and "store" in item and isinstance(item["store"], dict):
                s = item["store"]
                try:
                    sid = parse_int(s.get("id"))
                    if sid is None:
                        continue
                    stores.append(
                        schemas.Store(
                            id=sid,
                            name=str(s.get("name")),
                            slug=str(s.get("slug")),
                        )
                    )
                except Exception:
                    continue

        genres = []
        for g in genres_raw:
            if isinstance(g, dict):
                try:
                    gid = parse_int(g.get("id"))
                    if gid is None:
                        continue
                    genres.append(
                        schemas.Genre(
                            id=gid,
                            name=str(g.get("name")),
                            slug=str(g.get("slug")),
                        )
                    )
                except Exception:
                    continue

        tags = []
        for t in tags_raw:
            if isinstance(t, dict):
                try:
                    tid = parse_int(t.get("id"))
                    if tid is None:
                        continue
                    tags.append(
                        schemas.Tag(
                            id=tid,
                            name=str(t.get("name")),
                            slug=str(t.get("slug")),
                        )
                    )
                except Exception:
                    continue

        return schemas.GameCreate(
            id=game_id,
            slug=slug,
            name=name,
            released=released,
            rating=rating,
            ratings_count=ratings_count,
            metacritic=metacritic,
            playtime=playtime,
            background_image=background_image,
            clip=clip,
            genres=genres,
            platforms=platforms,
            stores=stores,
            tags=tags,
        )
    except Exception:
        return None


def seed_csv_file(db, csv_path: Path) -> tuple[int, int]:
    print(f"Seeding from {csv_path} ...")
    created = 0
    skipped = 0
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                slug = row.get("slug")
                if not slug:
                    skipped += 1
                    continue
                # Prepare parsed payload
                game_create = to_game_create(row)
                if not game_create:
                    skipped += 1
                    continue

                existing = crud.get_game_by_slug(db, slug)
                if existing:
                    # Backfill media if missing and CSV provides it
                    bg = game_create.background_image
                    cl = game_create.clip
                    should_update = False
                    if bg and not getattr(existing, "background_image", None):
                        should_update = True
                    if cl and not getattr(existing, "clip", None):
                        should_update = True
                    if should_update:
                        crud.update_game_media(db, existing, bg, cl)
                    skipped += 1
                    continue

                crud.create_game(db, game_create)
                created += 1
            except Exception as e:
                print(f"Row error in {csv_path.name}: {e}")
                # Ensure the session is usable for subsequent rows after an error
                with contextlib.suppress(Exception):
                    db.rollback()
                skipped += 1
                continue
    print(f"Done {csv_path.name}: created={created}, skipped={skipped}")
    return created, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Load RAWG CSV exports into the database.")
    parser.add_argument(
        "pattern",
        nargs="?",
        default="*.csv",
        help="glob of CSV files inside DATA_DIR to load (default: all of them)",
    )
    parser.add_argument(
        "--if-empty",
        action="store_true",
        help="do nothing when the games table already has rows",
    )
    args = parser.parse_args()

    if not DATA_DIR.exists():
        raise SystemExit(f"Data directory not found: {DATA_DIR}")

    csv_files = sorted(DATA_DIR.glob(args.pattern))
    if not csv_files:
        print(f"No CSV files matching {args.pattern!r} in {DATA_DIR}")
        return

    total_created = 0
    total_skipped = 0

    # Keep loaded look-up rows usable across commits instead of re-reading them per game.
    with SessionLocal(expire_on_commit=False) as db:
        if args.if_empty and (existing := crud.count_games(db)):
            print(f"Database already has {existing} games; skipping seeding.")
            return
        for csv_path in csv_files:
            c, s = seed_csv_file(db, csv_path)
            total_created += c
            total_skipped += s

    print("Seeding complete.")
    print(f"Total created: {total_created}")
    print(f"Total skipped: {total_skipped}")


if __name__ == "__main__":
    main()
