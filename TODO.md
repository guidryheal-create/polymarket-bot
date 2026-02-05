# Trading System TODO

This document outlines the current development priorities for the agentic trading system.

## High-Level Goals

- Complete the Polymarket trading bot with a focus on crypto markets.
- Integrate a robust workforce management system.
- Use RSS feeds as a signal source for trading decisions.
- Implement comprehensive testing and deployment procedures.
- Add and maintain clear documentation for developers and users.

## Documentation

- [x] Create `LICENSE` file (MIT).
- [x] Create `CONTRIBUTING.md` file.
- [x] Create `README.md` with basic information.
- [ ] Add architecture diagrams and more detailed documentation to the `README.md`.

## Current Priorities

### 1. RSS Feed Integration

- **Service:** `core/services/rss_flux_service.py`
- **Features:**
    - [ ] Parse RSS/Atom feeds (title, description, timestamp).
    - [ ] Extract trading signals from articles (sentiment, asset mentions, confidence).
    - [ ] Score signals based on reliability, relevance, and time.
    - [ ] Store and manage signals, including deduplication and time-series tracking.
    - [ ] Provide an API to fetch the latest signals and consensus for a given asset.
    - [ ] Track which signals lead to trades and update signal accuracy based on trade outcomes.

### 2. Workforce Management

- **Service:** `core/camel_runtime/polymarket_workforce_manager.py`
- **Features:**
    - [ ] Implement the main `run_trading_cycle` function.
    - [ ] Enforce trading limits (max trades, max amount, max exposure).
    - [ ] Log all trade executions and decisions.
    - [ ] Provide a summary of trading activity.

### 3. Trading Controls & Configuration

- **Service:** `core/services/workforce_config_service.py`
- **Features:**
    - [ ] Load trading configurations from `.env` and a potential YAML file.
    - [ ] Implement logic for trade approval based on configuration.
    - [ ] Implement trigger conditions for the workforce.
    - [ ] Use agent weights in trade proposal scoring.

### 4. Logging & Monitoring

- **Service:** `core/services/trading_metrics_service.py`
- **Features:**
    - [ ] Log every trade with full context.
    - [ ] Log each trading cycle execution.
    - [ ] Log RSS signals used in trading decisions.
    - [ ] Update signal accuracy after trades are completed.
    - [ ] Provide performance metrics for each agent.
    - [ ] Generate daily trading reports.

## Testing

- [ ] `tests/test_trading_workflow_full.py`: Test the full trading workflow with mock orders.
- [ ] `tests/test_rss_signal_integration.py`: Test the integration of RSS signals into the trading logic.
- [ ] `tests/test_trading_limits_enforced.py`: Test that all trading limits are correctly enforced.
- [ ] `tests/test_filter_rules.py`: Test all filtering rules for assets, categories, liquidity, and probability.
- [ ] `tests/test_workforce_config.py`: Test the workforce configuration service.
- [ ] `tests/test_rss_flux_service.py`: Test the RSS flux service.
- [ ] `tests/test_performance.py`: Add performance tests for market scanning, position sizing, and RSS parsing.

## Backlog / Future Ideas

- [ ] Explore additional signal sources (e.g., social media, other news APIs).
- [ ] Improve the signal extraction and scoring algorithms.
- [ ] Enhance the agent decision-making process with more sophisticated models.
- [ ] Develop a more comprehensive front-end for monitoring and manual intervention.
- [ ] Add support for other exchanges besides Polymarket.
