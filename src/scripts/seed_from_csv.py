import os
import csv
import ast
from pathlib import Path
from datetime import datetime

from src.backend.database import SessionLocal
from src.backend import crud, schemas

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
                        schemas.PlatformCreate(
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
                        schemas.StoreCreate(
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
                        schemas.GenreCreate(
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
                        schemas.TagCreate(
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
                try:
                    db.rollback()
                except Exception:
                    pass
                skipped += 1
                continue
    print(f"Done {csv_path.name}: created={created}, skipped={skipped}")
    return created, skipped


def main():
    if not DATA_DIR.exists():
        print(f"Data directory not found: {DATA_DIR}")
        raise SystemExit(1)

    csv_files = sorted(DATA_DIR.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {DATA_DIR}")
        return

    total_created = 0
    total_skipped = 0

    db = SessionLocal()
    try:
        for csv_path in csv_files:
            c, s = seed_csv_file(db, csv_path)
            total_created += c
            total_skipped += s
    finally:
        db.close()

    print("Seeding complete.")
    print(f"Total created: {total_created}")
    print(f"Total skipped: {total_skipped}")


if __name__ == "__main__":
    main()
