"""CSV formatter for trend data (T-3 to T+3) to minimize tokens and optimize readability."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple, Any, Dict
import csv
import io

from core.logging import log


def format_trend_table_csv(
    historical_data: List[Dict[str, Any]],
    forecast_data: List[Dict[str, Any]],
    current_time: Optional[datetime] = None,
) -> str:
    """
    Format trend table as CSV: [date, real|"_", pred] for T-3 to T+3.
    
    Args:
        historical_data: List of dicts with keys: date, real_price, pred_price (T-3 to T-0)
        forecast_data: List of dicts with keys: date, pred_price (T+1 to T+3)
        current_time: Current timestamp to determine which real prices are available
    
    Returns:
        CSV string with columns: date,real,pred
    """
    if current_time is None:
        current_time = datetime.utcnow()
    
    rows = []
    
    # Historical data (T-3 to T-0): real prices should be available
    for item in historical_data[-4:]:  # Last 4 historical points
        date = item.get('date') or item.get('timestamp')
        real_price = item.get('real_price') or item.get('real')
        pred_price = item.get('pred_price') or item.get('pred') or item.get('forecast_price')
        
        if not date:
            continue
        
        # Format date as ISO8601
        if isinstance(date, str):
            date_str = date
        elif isinstance(date, datetime):
            date_str = date.isoformat() + 'Z' if date.tzinfo is None else date.isoformat()
        else:
            continue
        
        # Real price: use actual if available, otherwise "_"
        real_str = f"{real_price:.4f}" if real_price is not None else "_"
        
        # Pred price: always include
        pred_str = f"{pred_price:.4f}" if pred_price is not None else "_"
        
        rows.append({
            'date': date_str,
            'real': real_str,
            'pred': pred_str
        })
    
    # Forecast data (T+1 to T+3): real prices are "_"
    for item in forecast_data[:3]:  # Next 3 forecast points
        date = item.get('date') or item.get('timestamp')
        pred_price = item.get('pred_price') or item.get('pred') or item.get('forecast_price')
        
        if not date:
            continue
        
        # Format date as ISO8601
        if isinstance(date, str):
            date_str = date
        elif isinstance(date, datetime):
            date_str = date.isoformat() + 'Z' if date.tzinfo is None else date.isoformat()
        else:
            continue
        
        # Real price: always "_" for future
        real_str = "_"
        
        # Pred price: always include
        pred_str = f"{pred_price:.4f}" if pred_price is not None else "_"
        
        rows.append({
            'date': date_str,
            'real': real_str,
            'pred': pred_str
        })
    
    # Format as CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['date', 'real', 'pred'])
    writer.writeheader()
    writer.writerows(rows)
    
    csv_str = output.getvalue()
    log.debug(f"[TREND CSV] Formatted {len(rows)} rows as CSV ({len(csv_str)} chars)")
    
    return csv_str


def format_trend_table_compact(
    historical_data: List[Dict[str, Any]],
    forecast_data: List[Dict[str, Any]],
    current_time: Optional[datetime] = None,
) -> str:
    """
    Format trend table as compact text (minimal tokens): [date, real|"_", pred].
    
    Returns compact format like:
    ```
    T-3: 2025-11-12,101.2,101.0
    T-2: 2025-11-13,102.5,102.1
    T-1: 2025-11-14,103.0,103.2
    T+1: 2025-11-16,_,103.8
    ```
    """
    if current_time is None:
        current_time = datetime.utcnow()
    
    lines = []
    
    # Historical data (T-3 to T-0)
    for idx, item in enumerate(historical_data[-4:], start=-3):
        date = item.get('date') or item.get('timestamp')
        real_price = item.get('real_price') or item.get('real')
        pred_price = item.get('pred_price') or item.get('pred') or item.get('forecast_price')
        
        if not date:
            continue
        
        # Format date as YYYY-MM-DD
        if isinstance(date, str):
            date_str = date[:10]  # Take first 10 chars (YYYY-MM-DD)
        elif isinstance(date, datetime):
            date_str = date.strftime('%Y-%m-%d')
        else:
            continue
        
        real_str = f"{real_price:.2f}" if real_price is not None else "_"
        pred_str = f"{pred_price:.2f}" if pred_price is not None else "_"
        
        lines.append(f"T{idx:+d}: {date_str},{real_str},{pred_str}")
    
    # Forecast data (T+1 to T+3)
    for idx, item in enumerate(forecast_data[:3], start=1):
        date = item.get('date') or item.get('timestamp')
        pred_price = item.get('pred_price') or item.get('pred') or item.get('forecast_price')
        
        if not date:
            continue
        
        # Format date as YYYY-MM-DD
        if isinstance(date, str):
            date_str = date[:10]
        elif isinstance(date, datetime):
            date_str = date.strftime('%Y-%m-%d')
        else:
            continue
        
        real_str = "_"
        pred_str = f"{pred_price:.2f}" if pred_price is not None else "_"
        
        lines.append(f"T+{idx}: {date_str},{real_str},{pred_str}")
    
    result = "\n".join(lines)
    log.debug(f"[TREND CSV] Formatted {len(lines)} rows as compact text ({len(result)} chars)")
    
    return result


def parse_trend_table_csv(csv_str: str) -> List[Dict[str, Any]]:
    """Parse CSV trend table back into list of dicts."""
    reader = csv.DictReader(io.StringIO(csv_str))
    rows = []
    for row in reader:
        rows.append({
            'date': row['date'],
            'real': None if row['real'] == '_' else float(row['real']),
            'pred': None if row['pred'] == '_' else float(row['pred'])
        })
    return rows

