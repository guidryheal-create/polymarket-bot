"""Manual Polymarket trade CLI (explicit execution only).

Usage examples:
  python scripts/polymarket_trade_cli.py --search "bitcoin"
  python scripts/polymarket_trade_cli.py --market-id <id> --details
  python scripts/polymarket_trade_cli.py --market-id <id> --outcome YES --quantity 5 --price 0.45 --confirm
  python scripts/polymarket_trade_cli.py --market-id <id> --outcome NO --quantity 5 --price 0.55 --dry-run
"""

import argparse
from typing import Optional
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

from core.clients.polymarket_client import PolymarketClient


def _load_env() -> None:
    if load_dotenv:
        project_root = Path(__file__).resolve().parents[1]
        load_dotenv(project_root / ".env", override=False)


def _resolve_market_and_token(
    client: PolymarketClient,
    market_id: Optional[str],
    outcome: str,
    condition_id: Optional[str] = None,
    slug: Optional[str] = None,
    market_maker_address: Optional[str] = None,
):
    outcome = outcome.upper()
    try:
        import asyncio
        details = asyncio.run(
            client.get_market_details(
                market_id=market_id,
                condition_id=condition_id,
                slug=slug,
                market_maker_address=market_maker_address,
            )
        )
    except Exception:
        details = None
    if not isinstance(details, dict):
        return None, None
    tokens = client.extract_outcome_token_ids(details)
    if not tokens or outcome not in tokens:
        return details, None
    return details, tokens[outcome]


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual Polymarket trade CLI")
    parser.add_argument("--search", help="Search markets by query")
    parser.add_argument("--market-id", help="Market ID to trade (numeric id or market maker address)")
    parser.add_argument("--condition-id", help="Condition ID to trade")
    parser.add_argument("--slug", help="Market slug to trade")
    parser.add_argument("--details", action="store_true", help="Fetch market details for market-id")
    parser.add_argument("--outcome", choices=["YES", "NO"], help="Outcome to buy")
    parser.add_argument("--quantity", type=float, help="Order size (shares)")
    parser.add_argument("--price", type=float, help="Limit price")
    parser.add_argument("--dry-run", action="store_true", help="Print intended order without executing")
    parser.add_argument("--confirm", action="store_true", help="Execute trade (must be set to place order)")

    args = parser.parse_args()

    _load_env()
    client = PolymarketClient()

    if args.search:
        import asyncio
        results = asyncio.run(client.search_markets(query=args.search, limit=20))
        print(results)
        return

    if args.market_id and args.details:
        import asyncio
        details = asyncio.run(client.get_market_details(market_id=args.market_id))
        print(details)
        return

    if not (args.market_id or args.condition_id or args.slug) or not args.outcome or not args.quantity or not args.price:
        raise SystemExit("Provide --market-id or --condition-id or --slug, plus --outcome, --quantity, --price for trading.")

    if not args.confirm and not args.dry_run:
        raise SystemExit("Refusing to place order without --confirm or --dry-run")

    if not client.is_authenticated:
        raise SystemExit("Client not authenticated. Set POLYGON_PRIVATE_KEY and CLOB_* creds in .env")

    details, token_id = _resolve_market_and_token(
        client,
        args.market_id,
        args.outcome,
        condition_id=args.condition_id,
        slug=args.slug,
        market_maker_address=args.market_id if isinstance(args.market_id, str) and args.market_id.startswith("0x") and len(args.market_id) == 42 else None,
    )
    if not token_id:
        raise SystemExit("Unable to resolve token_id for market/outcome")
    if isinstance(details, dict):
        if details.get("closed") is True or details.get("active") is False:
            raise SystemExit("Market is closed or inactive; cannot trade on CLOB.")

    print("\nOrder Preview")
    print(f"  market_id: {args.market_id}")
    print(f"  outcome:   {args.outcome}")
    print(f"  token_id:  {token_id}")
    print(f"  quantity:  {args.quantity}")
    print(f"  price:     {args.price}")

    if args.dry_run and not args.confirm:
        print("\nDry run complete. No order placed.")
        return

    print("\nPlacing order...")
    resp = None
    try:
        resp = client._clob_client is not None and client._clob_client or None
        # Use client.place_order (async) via a simple sync runner
        import asyncio
        resp = asyncio.run(
            client.place_order(
                token_id=token_id,
                side="BUY",
                quantity=float(args.quantity),
                price=float(args.price),
            )
        )
    except Exception as exc:
        raise SystemExit(f"Order failed: {exc}")

    print("Order response:")
    print(resp)

    print("\nFetching open positions...")
    positions = client.get_open_positions()
    print(positions)


if __name__ == "__main__":
    main()
