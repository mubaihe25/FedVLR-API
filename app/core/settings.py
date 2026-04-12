from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str
    api_root: Path
    fedvlr_root: Path
    results_dir: Path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    api_root = Path(__file__).resolve().parents[2]
    workspace_root = api_root.parent

    fedvlr_root_env = os.getenv("FEDVLR_ROOT")
    fedvlr_results_env = os.getenv("FEDVLR_RESULTS_DIR")

    if fedvlr_root_env:
        fedvlr_root = Path(fedvlr_root_env).expanduser()
        if not fedvlr_root.is_absolute():
            fedvlr_root = (api_root / fedvlr_root).resolve()
    else:
        fedvlr_root = (workspace_root / "FedVLR").resolve()

    if fedvlr_results_env:
        results_dir = Path(fedvlr_results_env).expanduser()
        if not results_dir.is_absolute():
            results_dir = (api_root / results_dir).resolve()
    else:
        results_dir = (fedvlr_root / "outputs" / "results").resolve()

    return Settings(
        app_name="FedVLR API",
        api_root=api_root,
        fedvlr_root=fedvlr_root,
        results_dir=results_dir,
    )
