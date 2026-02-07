"""Process configuration service for Polymarket API."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4

from core.services.workforce_config_service import (
    WorkforceConfigService,
    TradingControls,
    WorkforceTriggerConfig,
    AgentWeightConfig,
)
from core.logging import log

CONFIG_FILE_PATH = "config/polymarket_config.json"


class ProcessConfigService:
    """In-memory runtime configuration with validation hooks and JSON persistence."""

    def __init__(self) -> None:
        self._config_service = WorkforceConfigService()
        self._active_flux = "polymarket_flux"
        self._trade_frequency_hours = 4
        self._max_ai_weighted_daily = 1.0
        self._max_ai_weighted_per_trade = 1.0
        self._last_updated = datetime.now(timezone.utc).isoformat()
        self._load_config_from_file()

    def _load_config_from_file(self):
        """Loads configuration from the JSON file if it exists."""
        if os.path.exists(CONFIG_FILE_PATH):
            try:
                with open(CONFIG_FILE_PATH, "r") as f:
                    config = json.load(f)
                    self.update_config(config)
                    log.info(f"Loaded configuration from {CONFIG_FILE_PATH}")
            except (json.JSONDecodeError, IOError) as e:
                log.error(f"Error loading configuration from {CONFIG_FILE_PATH}: {e}")

    def _save_config_to_file(self):
        """Saves the current configuration to the JSON file."""
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
            with open(CONFIG_FILE_PATH, "w") as f:
                json.dump(self.get_config(), f, indent=4)
            log.info(f"Saved configuration to {CONFIG_FILE_PATH}")
        except IOError as e:
            log.error(f"Error saving configuration to {CONFIG_FILE_PATH}: {e}")

    def get_config(self) -> Dict[str, Any]:
        return {
            "config_id": str(uuid4()),
            "active_flux": self._active_flux,
            "trade_frequency_hours": self._trade_frequency_hours,
            "max_ai_weighted_daily": self._max_ai_weighted_daily,
            "max_ai_weighted_per_trade": self._max_ai_weighted_per_trade,
            "trading_controls": asdict(self._config_service.trading_controls),
            "trigger_config": asdict(self._config_service.trigger_config),
            "agent_weights": asdict(self._config_service.agent_weights),
            "limits_status": self._config_service.get_limits_status(),
            "last_updated": self._last_updated,
        }

    def update_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        process = payload.get("process", {})
        trading_controls = payload.get("trading_controls", {})
        trigger_config = payload.get("trigger_config", {})
        agent_weights = payload.get("agent_weights", {})

        if "active_flux" in process:
            self._active_flux = str(process["active_flux"])
        if "trade_frequency_hours" in process:
            self._trade_frequency_hours = int(process["trade_frequency_hours"])
        if "max_ai_weighted_daily" in process:
            self._max_ai_weighted_daily = float(process["max_ai_weighted_daily"])
        if "max_ai_weighted_per_trade" in process:
            self._max_ai_weighted_per_trade = float(process["max_ai_weighted_per_trade"])

        # Update TradingControls
        for key, value in trading_controls.items():
            if hasattr(self._config_service.trading_controls, key):
                setattr(self._config_service.trading_controls, key, value)

        # Update TriggerConfig
        for key, value in trigger_config.items():
            if hasattr(self._config_service.trigger_config, key):
                setattr(self._config_service.trigger_config, key, value)

        # Update AgentWeightConfig
        for key, value in agent_weights.items():
            if hasattr(self._config_service.agent_weights, key):
                setattr(self._config_service.agent_weights, key, value)

        # Validate
        self._config_service.trading_controls.validate()
        self._config_service.trigger_config.validate()
        self._config_service.agent_weights.validate()

        self._last_updated = datetime.now(timezone.utc).isoformat()
        self._save_config_to_file()  # Persist changes
        return self.get_config()

    def get_workforce_config(self) -> WorkforceConfigService:
        return self._config_service


process_config_service = ProcessConfigService()
