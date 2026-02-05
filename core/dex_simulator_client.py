"""
Compatibility wrapper for the canonical DEX simulator client.

The implementation is maintained at `core.clients.dex_simulator_client`.
This module re-exports it for backward compatibility.
"""

from core.clients.dex_simulator_client import *  # noqa: F401,F403
from core.clients.dex_simulator_client import DEXSimulatorClient, DEXSimulatorError, dex_simulator_client

__all__ = ["DEXSimulatorClient", "DEXSimulatorError", "dex_simulator_client"]
