import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Optional, Union

import psutil
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


def _get_processor():
    return platform.processor()


def _get_platform():
    return platform.platform()


def _get_available_cpus():
    return len(psutil.Process().cpu_affinity())


def _format_bytes(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)

    return f"{s}{size_name[i]}"


def _get_available_ram():
    size_bytes = psutil.virtual_memory().available

    return _format_bytes(size_bytes)
