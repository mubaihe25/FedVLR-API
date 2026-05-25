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
    showcase_artifact_root: Path
    amazon_beauty_image_manifest: Path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    api_root = Path(__file__).resolve().parents[2]
    workspace_root = api_root.parent

    fedvlr_root_env = os.getenv("FEDVLR_ROOT")
    fedvlr_results_env = os.getenv("FEDVLR_RESULTS_DIR")
    showcase_artifact_root_env = os.getenv("SHOWCASE_ARTIFACT_ROOT")

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

    if showcase_artifact_root_env:
        showcase_artifact_root = Path(showcase_artifact_root_env).expanduser()
        if not showcase_artifact_root.is_absolute():
            showcase_artifact_root = (api_root / showcase_artifact_root).resolve()
    else:
        showcase_artifact_root = (
            fedvlr_root / "outputs" / "showcase_artifacts"
        ).resolve()

    return Settings(
        app_name="FedVLR API",
        api_root=api_root,
        fedvlr_root=fedvlr_root,
        results_dir=results_dir,
        showcase_artifact_root=showcase_artifact_root,
        amazon_beauty_image_manifest=(
            fedvlr_root / "datasets" / "AMAZON_BEAUTY_POC" / "item_image_manifest.json"
        ).resolve(),
    )
