import argparse
import sqlite3
from pathlib import Path


def snapshot(source, destination):
    source = Path(source)
    destination = Path(destination)

    if not source.is_file():
        raise FileNotFoundError(source)

    destination.parent.mkdir(parents=True, exist_ok=True)

    if source.resolve() == destination.resolve():
        raise ValueError("Source et destination identiques")

    temporary = destination.with_name(destination.name + ".tmp")

    if temporary.exists():
        raise FileExistsError(temporary)

    try:
        with sqlite3.connect(
            f"file:{source.resolve()}?mode=ro",
            uri=True
        ) as original:
            with sqlite3.connect(temporary) as copy:
                original.backup(copy)

        with sqlite3.connect(temporary) as check:
            integrity = check.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

        if integrity != "ok":
            raise RuntimeError("Intégrité SQLite : " + integrity)

        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()

    snapshot(args.source, args.destination)
    print("Sauvegarde SQLite vérifiée :", args.destination)
