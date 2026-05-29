from importlib import metadata, PackageNotFoundError
try:
    __version__ = metadata.version(__name__)
except PackageNotFoundError:
    __version__ = "unknown"

from .MobNsLib import *

__all__ = ["nsLib"]