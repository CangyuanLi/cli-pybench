import subprocess
import time
from pathlib import Path
from typing import Optional, Union

import toml

PathLike = Union[str, Path]


def _get_commit_id() -> Optional[str]:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout
    except subprocess.CalledProcessError:
        return None


def _get_branch_name() -> Optional[str]:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None


def _get_version(rootdir: PathLike):
    rootdir = Path(rootdir)

    if not rootdir.exists():
        return None

    with open(rootdir / "pyproject.toml", "r") as f:
        pyproject_toml = toml.load(f)

    return pyproject_toml["project"]["version"]


def _get_time():
    return time.time()
