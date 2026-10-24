import json
import os
from pathlib import Path

from frontier import connect, add_url

sources = json.loads(
    Path(__file__).with_name("general_sources.json").read_text()
)

frontier_path = os.environ.get("KSEARCH_FRONTIER_DB")
db = connect(Path(frontier_path)) if frontier_path else connect()

try:
    for url in sources:
        add_url(db, url)
        print("Source ajoutée :", url)
finally:
    db.close()
