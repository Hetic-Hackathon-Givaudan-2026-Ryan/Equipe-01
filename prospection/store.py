"""Jeu de données courant et rédactions déjà faites, gardés en mémoire."""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

from . import writer
from .data import Dataset, load_path
from .scoring import score_dataset

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = Path(os.getenv("PROSPECT_DATASET", BASE_DIR / "givaudan_crm_data.csv"))
DEFAULT_MAPPING = os.getenv("PROSPECT_MAPPING")  # fichier JSON, optionnel


class Store:
    def __init__(self) -> None:
        self.dataset: Dataset | None = None
        self.prospects: list[dict] = []
        self.written: dict[str, dict] = {}  # id -> rédaction du LLM
        self.lock = Lock()

    def use(self, ds: Dataset) -> None:
        prospects = score_dataset(ds)
        with self.lock:
            self.dataset, self.prospects, self.written = ds, prospects, {}

    def load_default(self) -> None:
        if DEFAULT_DATASET.exists():
            self.use(load_path(DEFAULT_DATASET, DEFAULT_MAPPING))

    def get(self, pid: str) -> dict | None:
        return next((p for p in self.prospects if p["id"] == pid), None)

    def render(self, p: dict, use_llm: bool | None) -> dict:
        """Le prospect au format du front, avec sa rédaction.
        use_llm : True force le LLM, False les règles, None le réglage par défaut."""
        text = None if use_llm is False else self.written.get(p["id"])
        if text is None:
            text = writer.write(p, use_llm=use_llm)
            if text["engine"] == "llm":
                self.written[p["id"]] = text
        out = {k: v for k, v in p.items() if not k.startswith("_")}
        out.update(why=text["why"], takeaways=text["takeaways"], questions=text["questions"])
        out["writer"] = text["engine"]
        return out

    def info(self) -> dict:
        ds = self.dataset
        if not ds:
            return {"loaded": False}
        return {
            "loaded": True,
            "name": ds.name,
            "rows": len(ds.rows),
            "prospects": len(self.prospects),
            "columns": ds.columns,
            "ignoredColumns": ds.ignored,
            "llmWritten": len(self.written),
        }


store = Store()
