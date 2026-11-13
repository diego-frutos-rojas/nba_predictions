"""Fixtures compartidas: copia ligera del proyecto y estado del portal calculado sin red (test_daily y test_site)."""
import json
import shutil
from pathlib import Path

import pytest

from nba_model import daily, espn

ROOT = Path(__file__).resolve().parent
FIX = ROOT / "tests/fixtures"
load = lambda name: json.load(open(FIX / name, encoding="utf-8"))      # noqa: E731


@pytest.fixture(scope="session")
def make_root(tmp_path_factory):
    """Crea una copia ligera del proyecto: enlaces a las carpetas pedidas y `data/` propio (live y predictions vacíos)."""
    def make(name: str, parts: tuple[str, ...]) -> Path:
        root = tmp_path_factory.mktemp(name)
        (root / "data").mkdir()
        for rel in parts:
            try:
                (root / rel).symlink_to(ROOT / rel, target_is_directory=True)
            except OSError:
                # Windows sin modo desarrollador no permite enlaces simbólicos: se copia la carpeta.
                shutil.copytree(ROOT / rel, root / rel)
        return root
    return make


@pytest.fixture(scope="session")
def offline_root(make_root):
    """Copia ligera del proyecto (enlaces a datos, modelos y plantilla) con data/live y data/predictions vacíos."""
    return make_root("portal", ("data/raw", "models", "docs", "web"))


@pytest.fixture(scope="session")
def state(offline_root):
    """Estado del portal del 10-nov-2026 calculado con los fixtures de ESPN (sin red)."""
    mp = pytest.MonkeyPatch()
    mp.setattr(espn, "fetch_scoreboard", lambda date: espn.parse_scoreboard(load("scoreboard_2026-11-10.json")))
    mp.setattr(espn, "fetch_injuries", lambda: espn.parse_injuries(load("injuries.json")))
    mp.setattr(espn, "fetch_props", lambda gid: espn.parse_props(load("props_401909960.json")["items"]) if gid == "401909960" else [])
    try:
        return daily.build_state(offline_root, "2026-11-10", fetch=False, log=lambda *a: None)
    finally:
        mp.undo()
