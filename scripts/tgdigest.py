"""Kept so the old path keeps working (skills, MCP client configs, docs): the code is in
summarix_telegram/scripts/tgdigest.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from summarix_telegram.scripts.tgdigest import main  # noqa: E402

if __name__ == "__main__":
    main()
