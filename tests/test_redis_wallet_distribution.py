#!/usr/bin/env python3
"""
Test script to check Redis data for wallet distribution.
Verifies:
1. response_format keys exist for daily and hourly intervals
2. Wallet distribution can be calculated
3. Frontend API endpoint returns correct data
"""
import pytest

pytest.skip(
    "Legacy wallet distribution test not applicable to Polymarket-only backend.",
    allow_module_level=True,
)

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import json

# Load .env
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file, override=True)

if os.getenv("REDIS_HOST") == "redis":
    os.environ["REDIS_HOST"] = "localhost"

os.environ.setdefault("LOG_LEVEL", "INFO")
os.environ.setdefault("LOGURU_LEVEL", "INFO")
os.environ.setdefault("TEST_MODE", "true")

from core.logging import setup_logging, log
from core.redis_client import RedisClient
from api.services.wallet_service import WalletService

setup_logging()

async def test_redis_wallet_distribution():
    """Test Redis data for wallet distribution."""
    print("=" * 80)
    print("REDIS WALLET DISTRIBUTION TEST")
    print("=" * 80)
    
    redis_client = RedisClient()
    try:
        await redis_client.connect()
        print("✅ Redis connected\n")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False
    
    try:
        # Step 1: Check response_format keys
        print("=" * 80)
        print("STEP 1: Checking response_format keys in Redis...")
        print("=" * 80)
        
        # Find all response_format keys
        daily_keys = await redis_client.keys("pipeline:fusion:*:*:days:response_format")
        hourly_keys = await redis_client.keys("pipeline:fusion:*:*:hours:response_format")
        old_keys = await redis_client.keys("pipeline:fusion:*:*:response_format")
        
        print(f"Daily response_format keys: {len(daily_keys)}")
        print(f"Hourly response_format keys: {len(hourly_keys)}")
        print(f"Old format keys (no interval): {len(old_keys)}")
        
        if daily_keys:
            print("\nSample daily keys:")
            for key in daily_keys[:5]:
                print(f"  {key}")
                data = await redis_client.get_json(key)
                if data:
                    print(f"    - ticker: {data.get('ticker', 'N/A')}")
                    print(f"    - strategy: {data.get('strategy', 'N/A')}")
                    print(f"    - interval: {data.get('interval', 'N/A')}")
                    print(f"    - agentic: {data.get('agentic', False)}")
                    print(f"    - decision_id: {data.get('decision_id', 'N/A')}")
        
        if hourly_keys:
            print("\nSample hourly keys:")
            for key in hourly_keys[:5]:
                print(f"  {key}")
                data = await redis_client.get_json(key)
                if data:
                    print(f"    - ticker: {data.get('ticker', 'N/A')}")
                    print(f"    - strategy: {data.get('strategy', 'N/A')}")
                    print(f"    - interval: {data.get('interval', 'N/A')}")
                    print(f"    - agentic: {data.get('agentic', False)}")
                    print(f"    - decision_id: {data.get('decision_id', 'N/A')}")
        
        # Step 2: Test wallet distribution calculation
        print("\n" + "=" * 80)
        print("STEP 2: Testing wallet distribution calculation...")
        print("=" * 80)
        
        wallet_service = WalletService(redis_client)
        
        # Test without strategy filter
        print("\nTesting get_distribution() without filter...")
        result_all = await wallet_service.get_distribution(strategy=None, request_id="test-redis")
        
        print(f"Result structure: {list(result_all.keys())}")
        strategies = result_all.get('strategies', {})
        print(f"Strategies found: {len(strategies)}")
        
        for strategy, dist in strategies.items():
            wallet_dist = dist.get('wallet_distribution', {})
            print(f"  {strategy}: {len(wallet_dist)} tickers")
            if wallet_dist:
                for ticker, alloc in list(wallet_dist.items())[:3]:
                    action = alloc.get('weighted_action', 'N/A')
                    total = alloc.get('total_allocation', 0) * 100
                    print(f"    {ticker}: {action} - {total:.2f}%")
        
        # Test with strategy filter
        print("\nTesting get_distribution(strategy='wallet_balancing')...")
        result_filtered = await wallet_service.get_distribution(strategy="wallet_balancing", request_id="test-redis")
        
        print(f"Result structure: {list(result_filtered.keys())}")
        combined = result_filtered.get('combined', {})
        daily_dist = result_filtered.get('daily', {})
        hourly_dist = result_filtered.get('hourly', {})
        
        wallet_dist_combined = combined.get('wallet_distribution', {})
        wallet_dist_daily = daily_dist.get('wallet_distribution', {}) if isinstance(daily_dist, dict) else {}
        wallet_dist_hourly = hourly_dist.get('wallet_distribution', {}) if isinstance(hourly_dist, dict) else {}
        
        print(f"Combined: {len(wallet_dist_combined)} tickers")
        print(f"Daily: {len(wallet_dist_daily)} tickers")
        print(f"Hourly: {len(wallet_dist_hourly)} tickers")
        
        if wallet_dist_combined:
            print("\nCombined wallet distribution:")
            for ticker, alloc in list(wallet_dist_combined.items())[:5]:
                action = alloc.get('weighted_action', 'N/A')
                total = alloc.get('total_allocation', 0) * 100
                print(f"  {ticker}: {action} - {total:.2f}%")
        
        # Step 3: Check cached wallet distribution
        print("\n" + "=" * 80)
        print("STEP 3: Checking cached wallet distribution in Redis...")
        print("=" * 80)
        
        cached_keys = await redis_client.keys("wallet_distribution:*")
        print(f"Cached wallet distribution keys: {len(cached_keys)}")
        
        for key in cached_keys[:5]:
            print(f"  {key}")
            data = await redis_client.get_json(key)
            if data:
                wallet_dist = data.get('wallet_distribution', {})
                print(f"    - {len(wallet_dist)} tickers")
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"✅ Daily response_format keys: {len(daily_keys)}")
        print(f"✅ Hourly response_format keys: {len(hourly_keys)}")
        print(f"✅ Total strategies in wallet distribution: {len(strategies)}")
        print(f"✅ Cached wallet distribution keys: {len(cached_keys)}")
        
        if len(daily_keys) > 0 or len(hourly_keys) > 0:
            print("\n✅ Redis has response_format data - wallet distribution should work")
        else:
            print("\n⚠️  No response_format keys found - wallet distribution will be empty")
            print("   Run the scheduler to generate fusion pipeline data")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await redis_client.disconnect()

if __name__ == "__main__":
    success = asyncio.run(test_redis_wallet_distribution())
    sys.exit(0 if success else 1)
import pytest

pytest.skip(
    "Legacy wallet distribution test not applicable to Polymarket-only backend.",
    allow_module_level=True,
)
