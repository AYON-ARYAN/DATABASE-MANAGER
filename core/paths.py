"""Shared filesystem paths for the DATABASE-MANAGER app."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def repo_path(*parts: str) -> Path:
    return BASE_DIR.joinpath(*parts)


def db_path(*parts: str) -> Path:
    return repo_path("db", *parts)
