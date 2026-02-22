"""ModeKeeper package."""

__all__ = ["__version__"]
from importlib.metadata import PackageNotFoundError, version as _dist_version

try:
    __version__ = _dist_version("modekeeper")
except PackageNotFoundError:
    __version__ = "0.0.0"