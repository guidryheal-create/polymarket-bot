#!/usr/bin/env python3
"""
Portfolio Agentic One-Shot Test

Runs the new portfolio-level workforce task (process_portfolio) and checks
that a wallet response_format is produced without falling back.
"""
import pytest

pytest.skip(
    "Legacy portfolio agentic test not applicable to Polymarket-only backend.",
    allow_module_level=True,
)

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

from core.redis_client import RedisClient
from core.logging import log
from core.pipelines.daily_process import DailyProcess
from core.camel_runtime.societies import TradingWorkforceSociety


async def run_portfolio_test():
    # Load .env
    agentic_root = Path(__file__).parent
    env_file = agentic_root / ".env"
    root_env_file = agentic_root.parent / ".env"

    loaded_envs = []
    if env_file.exists():
        load_dotenv(env_file, override=True)
        loaded_envs.append(env_file)
    if root_env_file.exists():
        load_dotenv(root_env_file, override=True)
        loaded_envs.append(root_env_file)

    if loaded_envs:
        log.info(f"✅ Loaded .env files: {', '.join(str(p) for p in loaded_envs)}")
    else:
        log.warning(f"⚠️ No .env file found at {env_file} or {root_env_file}")

    # Fail fast if API key missing
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY not found. Please set it in .env (agentic or project root).")
    log.info(f"✅ OPENAI_API_KEY loaded (len={len(openai_key)})")

    # Prefer local Redis for test
    os.environ.setdefault("REDIS_HOST", "localhost")
    os.environ.setdefault("REDIS_PORT", "6379")

    redis_client = RedisClient()
    try:
        await redis_client.connect()
        log.info("✅ Redis connected")
    except Exception as e:
        log.warning(f"⚠️ Redis unavailable: {e}")

    # Build workforce and initialize DailyProcess
    society = TradingWorkforceSociety()
    workforce = await society.build()
    if not workforce:
        raise RuntimeError("Failed to build workforce")
    
    daily_process = DailyProcess(workforce, redis_client)
    
    tickers = ["BTC", "ETH", "SOL"]
    result = await daily_process.process(tickers, strategies=["wallet_balancing"])
    log.info(f"Portfolio result: {result}")

    assert result.get("success"), f"Portfolio run failed: {result}"
    # Check Redis for wallet distribution
    key = "response_format:wallet:wallet_balancing:combined"
    wallet_data = await redis_client.get_json(key)
    assert wallet_data, "Wallet distribution not found in Redis"
    dist = wallet_data.get("wallet_distribution", {})
    assert dist and sum(dist.values()) > 0, "Empty or zero allocation wallet_distribution"

    await redis_client.disconnect()
    log.info("✅ Portfolio test completed")


if __name__ == "__main__":
    asyncio.run(run_portfolio_test())

