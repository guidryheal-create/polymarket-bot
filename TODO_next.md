UI enhancement
workforce manual trigger
workforce RSS flux management and enhancemenent
filter query -> the query might not been taken into account

"detail": "Polymarket client not authenticated. Set POLYGON_PRIVATE_KEY/PK and API creds."
} {
    "detail": "Polymarket client not authenticated. Set POLYGON_PRIVATE_KEY/PK and API creds."
} ts-trading-api  | INFO:     172.19.0.1:58412 - "GET /api/polymarket/clob/orders/open HTTP/1.1" 400 Bad Request
ats-trading-api  | INFO:     172.19.0.1:58416 - "GET /api/polymarket/clob/trades HTTP/1.1" 400 Bad Request
ats-ollama       | [GIN] 2026/02/04 - 12:07:59 | 200 |      22.243µs |       127.0.0.1 | HEAD     "/"
ats-ollama       | [GIN] 2026/02/04 - 12:07:59 | 200 |     291.207µs |       127.0.0.1 | GET      "/api/tags"
ats-trading-api  | INFO:     

POLYGON_PRIVATE_KEY-> set in .env

      - POLYGON_PRIVATE_KEY=${POLYGON_PRIVATE_KEY:-}

it is set so check pydantic-settings or else