# UI Quick Start Guide - February 5, 2026

## Getting Started

### 1. **Launch the Application**
```bash
cd /home/pizzaburger/Documents/agentic-system-trading
python -m uvicorn api.main_polymarket:app --host 0.0.0.0 --port 8000 --reload
```

Then navigate to: `http://localhost:8000/ui`

### 2. **Authentication**
If you're not already authenticated:
1. Click the "Login" button in the top-right corner
2. Enter your Polymarket API key (optional: wallet address)
3. Click "Login"
4. You'll see your wallet address in the header once authenticated

## Navigation

### Dashboard (`/ui`)
**Main overview page showing:**
- Total trades and open positions count
- Active flux status and trigger type
- Latest decisions from the workforce
- CLOB (Orderbook) snapshot
- Market search functionality
- Results summary

**Auto-refreshes every 15 seconds**

### Markets (`/ui/markets`)
**Search and explore Polymarket markets:**
- Type keywords to search (e.g., "bitcoin", "election")
- Click popular searches for quick access
- View liquidity and 24h volume
- Press Enter to search

### Workforce (`/ui/workforce`)
**Control and monitor the trading workforce:**
- **Trigger Type Dropdown**: Select manual, scheduled, event-driven, or RSS-feed based triggering
- **Flux Controls**: Start/Stop the RSS feed
- **Manual Trigger**: Execute a workforce cycle immediately
- **Status Display**: Current flux status, trigger type, trade frequency
- **RSS Cache**: View cached markets from the feed

**Auto-refreshes every 30 seconds**

### Results (`/ui/results`)
**View trading performance:**
- Summary stats: total trades, win rate, P&L, ROI
- Filter trades by status (All, Won, Lost, Pending)
- Export results to CSV
- Auto-refreshes every 20 seconds

### Settings (`/ui/settings`)
**Configure system parameters:**
- **Active Flux**: Choose between polymarket_rss_flux, manual_trigger, or scheduled
- **Trade Frequency**: Set hours between trades
- **Max Concurrent Positions**: Limit open positions
- **Min Confidence Threshold**: Filter low-confidence trades

All settings saved immediately with validation.

### Orders (`/ui/orders`)
**Manage trading orders:**
- View open orders with details
- View recent trades
- Cancel orders by ID
- Order status legend for reference

### Chat (`/ui/chat`)
**Communicate with the workforce agent:**
- Enter context tags like #bitcoin or #election
- Ask questions about markets, strategies, or positions
- View conversation history
- Tips and hints for better results

## Features Overview

### Loading Indicators
- Spinner animation while fetching data
- Clear feedback on data updates
- Auto-dismiss success/error messages

### Status Indicators
- **Green (OK)**: Running/Active
- **Yellow (Warn)**: Stopped/Caution
- **Red (Error)**: Failed/Issue

### Auto-Refresh
- Dashboard: 15 seconds
- Workforce: 30 seconds  
- Results: 20 seconds

### Keyboard Shortcuts
- **Enter** in search box: Execute search
- **Enter** in chat: Send message
- **Tab**: Navigate form fields

## Common Tasks

### Change Trigger Type
1. Go to Workforce page
2. Select new trigger type from dropdown
3. Changes apply immediately
4. Confirmation message appears

### View Latest Decisions
1. Dashboard page shows latest 10 decisions
2. Each decision shows:
   - Timestamp
   - Market/Bet ID
   - Action taken
   - Confidence score

### Manage Settings
1. Go to Settings page
2. Fill in form fields
3. Click "Save Settings"
4. JSON display updates automatically
5. Success message appears

### Monitor Workforce Status
1. Go to Workforce page
2. View status panel with:
   - Current flux type
   - Trigger configuration
   - Trade frequency
   - Open positions
   - Max positions
3. Auto-refreshes every 30 seconds

### Export Results
1. Go to Results page
2. Click "Export CSV"
3. CSV file downloads automatically
4. Contains all trade details

## API Endpoints

### Authentication
- `POST /api/polymarket/auth/login` - User login
- `GET /api/polymarket/auth/status` - Check auth status
- `POST /api/polymarket/auth/logout` - User logout

### Workforce
- `GET /api/polymarket/workforce/status` - Get workforce status
- `POST /api/polymarket/workforce/trigger` - Manual trigger
- `POST /api/polymarket/flux/start` - Start RSS flux
- `POST /api/polymarket/flux/stop` - Stop RSS flux

### Decisions
- `GET /api/polymarket/decisions?limit=10` - List recent decisions
- `GET /api/polymarket/decisions/{id}` - Get specific decision
- `GET /api/polymarket/decisions/by-market/{market_id}` - Decisions for market
- `GET /api/polymarket/decisions/performance` - Decision performance metrics

### Configuration
- `GET /api/polymarket/config` - Get current config
- `POST /api/polymarket/config` - Update config

### Results
- `GET /api/polymarket/results/summary` - Get summary stats
- `GET /api/polymarket/results/trades?limit=50` - Get recent trades

### Markets
- `GET /api/polymarket/markets/search?q=...&limit=20` - Search markets

### RSS Cache
- `GET /api/polymarket/rss/cache` - Get cached markets

### CLOB
- `GET /api/polymarket/clob/orders/open` - Get open orders
- `GET /api/polymarket/clob/trades` - Get recent trades

## Troubleshooting

### Page Not Loading
- Check browser console (F12) for errors
- Verify server is running: `http://localhost:8000/health`
- Clear browser cache and reload

### Authentication Failed
- Verify API key is correct
- Check for extra spaces in key
- Try logging out and back in
- Check server logs for auth errors

### Data Not Updating
- Check auto-refresh indicators (green pulsing dots)
- Manually click refresh button
- Check network tab for API errors
- Verify workforce is running

### Settings Not Saving
- Check all form fields are valid
- Look for error message above form
- Verify network connection
- Check server logs

### Orders/Trades Not Showing
- Ensure authenticated first
- Verify CLOB client has network access
- Check if any trades exist
- Review API documentation for required auth headers

## Performance Notes

- Pages load quickly with caching
- Auto-refresh intervals optimized to reduce server load
- Lazy loading for large datasets
- Tables show only recent 50-100 items

## Security Tips

- Never share your API key
- Use strong passwords if added
- Log out when done
- Clear browser history on shared computers
- Check auth status regularly

## Support & Logs

Check logs in `/logs/` directory:
- API server logs: Check terminal output
- Event logs: Review in Logs endpoint
- Cache: View RSS cache status on Workforce page

---

**Last Updated**: February 5, 2026
**Version**: 0.1.0
