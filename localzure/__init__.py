"""
LocalZure: Local Azure Cloud Platform Emulator

A fully local Azure cloud platform emulator for offline development and testing.
"""

__version__ = "0.1.0"
__author__ = "Ayodele Oladeji"

from .core.runtime import LocalZureRuntime

__all__ = ["LocalZureRuntime", "__version__"]
