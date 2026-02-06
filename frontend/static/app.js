// Helper to show loading state
function setLoading(elementId, isLoading) {
  const el = document.getElementById(elementId);
  if (!el) return;
  if (isLoading) {
    el.classList.add('loading');
    el.innerHTML = '<div class="spinner"></div> Loading...';
  } else {
    el.classList.remove('loading');
  }
}

// Helper to show error message
function showError(elementId, message) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.classList.add('error');
  el.innerHTML = `<span class="error-icon">⚠</span> ${message}`;
  setTimeout(() => {
    el.classList.remove('error');
  }, 5000);
}

async function apiGet(path) {
  try {
    const res = await fetch(path, { credentials: 'same-origin' });
    if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error('apiGet error', path, err);
    return {};
  }
}

async function apiPost(path, payload) {
  try {
    const res = await fetch(path, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) throw new Error(`POST ${path} -> ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error('apiPost error', path, err);
    return {};
  }
}

async function loadDashboard() {
  setLoading('workforce-flux', true);
  setLoading('decision-list', true);
  
  const [summary, workforce, rss, decisions, logs, flux] = await Promise.all([
    apiGet('/api/polymarket/results/summary'),
    apiGet('/api/polymarket/workforce/status'),
    apiGet('/api/polymarket/rss/cache'),
    apiGet('/api/polymarket/decisions?limit=10'),
    apiGet('/api/polymarket/logs?limit=20'),
    apiGet('/api/polymarket/flux/status'),
  ]);

  document.getElementById('kpi-total-trades').textContent = (summary.summary && summary.summary.total_trades) || 0;
  document.getElementById('kpi-open-positions').textContent = (workforce.limits_status && workforce.limits_status.open_positions) || 0;
  const rssCount = rss && rss.count ? rss.count : 0;
  const openPositions = (workforce.limits_status && workforce.limits_status.open_positions) || 0;
  document.getElementById('kpi-rss-bets').textContent = rssCount || openPositions || 0;

  const fluxStatus = (flux && flux.status === 'ok' && flux.scheduler_running) ? 'running' : (workforce.active_flux || 'unknown');
  document.getElementById('workforce-flux').textContent = fluxStatus;
  document.getElementById('workforce-flux').className = `tag ${fluxStatus === 'running' ? 'ok' : fluxStatus === 'stopped' ? 'warn' : 'muted'}`;


  const decisionList = document.getElementById('decision-list');
  decisionList.innerHTML = '';
  (decisions.decisions || []).forEach(d => {
    const li = document.createElement('div');
    li.className = 'decision-item';
    const ts = d.timestamp ? new Date(d.timestamp).toLocaleTimeString() : '';
    li.innerHTML = `<div class="decision-header">${ts} | ${d.market_id || d.bet_id || 'market'}</div><div class="decision-body">${d.action || d.outcome || 'decision'} (confidence: ${d.confidence ?? 'n/a'})</div>`;
    decisionList.appendChild(li);
  });
  if (!decisions.decisions || decisions.decisions.length === 0) {
    decisionList.innerHTML = '<div class="muted">No recent decisions</div>';
  }

  const logBox = document.getElementById('log-box');
  logBox.textContent = (logs.events || []).map(l => `${l.timestamp} [${l.level}] ${l.message}`).join('\n');

  await Promise.all([loadClobSnapshot(), loadResults(), loadSettings()].map(p => p.catch && p.catch(() => {})));
}

async function loadMarkets() {
  const query = document.getElementById('market-query').value || 'market';
  const data = await apiGet(`/api/polymarket/markets/search?q=${encodeURIComponent(query)}&limit=20`);
  const list = document.getElementById('market-results');
  list.innerHTML = '';
  const arr = data.markets || data.results || [];
  arr.forEach(m => {
    const title = m.title || m.question || m.name || '';
    const row = document.createElement('tr');
    row.innerHTML = `<td>${m.id || m.market_id || ''}</td><td>${title}</td><td>${(m.liquidity||0).toLocaleString()}</td><td>${(m.volume_24h||0).toLocaleString()}</td>`;
    list.appendChild(row);
  });
}

async function loadResults() {
  const summary = await apiGet('/api/polymarket/results/summary');
  const trades = await apiGet('/api/polymarket/results/trades?limit=50');
  const s = summary.summary || {};
  document.getElementById('results-total-trades').textContent = s.total_trades ?? 0;
  document.getElementById('results-win-rate').textContent = s.win_rate ? `${(s.win_rate * 100).toFixed(1)}%` : 'n/a';
  document.getElementById('results-net-pnl').textContent = s.net_pnl ?? 'n/a';
  document.getElementById('results-roi').textContent = s.roi ? `${(s.roi * 100).toFixed(2)}%` : 'n/a';

  const tradesTable = document.getElementById('results-trades-table');
  const tradesEmpty = document.getElementById('results-trades-empty');
  tradesTable.innerHTML = '';
  const items = trades.trades || [];
  if (!items.length) {
    tradesEmpty.style.display = 'block';
  } else {
    tradesEmpty.style.display = 'none';
    items.slice(0, 100).forEach(t => {
      const row = document.createElement('tr');
      row.innerHTML = `<td>${t.market_id || t.bet_id || ''}</td><td>${t.outcome || ''}</td><td>${t.quantity ?? ''}</td><td>${t.price ?? ''}</td><td>${t.status || ''}</td>`;
      tradesTable.appendChild(row);
    });
  }
}

async function loadSettings() {
  setLoading('settings-container', true);
  const data = await apiGet('/api/polymarket/config');
  setLoading('settings-container', false);
  
  const cfg = data.config || data.settings || data;
  
  // Build form from config
  const form = document.getElementById('settings-form');
  if (form) {
    form.innerHTML = '';
    
    // Active flux selector
    const fluxGroup = document.createElement('div');
    fluxGroup.className = 'form-group';
    fluxGroup.innerHTML = `
      <label>Active Flux</label>
      <select id="setting-active-flux">
        <option value="polymarket_rss_flux" ${cfg.active_flux === 'polymarket_rss_flux' ? 'selected' : ''}>Polymarket RSS Flux</option>
        <option value="manual_trigger" ${cfg.active_flux === 'manual_trigger' ? 'selected' : ''}>Manual Trigger</option>
        <option value="scheduled" ${cfg.active_flux === 'scheduled' ? 'selected' : ''}>Scheduled</option>
      </select>
    `;
    form.appendChild(fluxGroup);
    
    // Trade frequency
    const freqGroup = document.createElement('div');
    freqGroup.className = 'form-group';
    freqGroup.innerHTML = `
      <label>Trade Frequency (hours)</label>
      <input type="number" id="setting-frequency" value="${cfg.trade_frequency_hours || 24}" min="1" max="168" />
    `;
    form.appendChild(freqGroup);
    
    // Max positions
    if (cfg.limits_status) {
      const maxPosGroup = document.createElement('div');
      maxPosGroup.className = 'form-group';
      maxPosGroup.innerHTML = `
        <label>Max Concurrent Positions</label>
        <input type="number" id="setting-max-positions" value="${cfg.limits_status.max_positions || 10}" min="1" max="100" />
      `;
      form.appendChild(maxPosGroup);
    }
    
    // Confidence threshold
    const confGroup = document.createElement('div');
    confGroup.className = 'form-group';
    confGroup.innerHTML = `
      <label>Min Confidence Threshold</label>
      <input type="number" id="setting-min-confidence" value="${cfg.min_confidence || 0.65}" min="0" max="1" step="0.05" />
    `;
    form.appendChild(confGroup);
    
    // Save button
    const btnGroup = document.createElement('div');
    btnGroup.className = 'form-group';
    btnGroup.innerHTML = `<button onclick="window.ui.saveSettings()" class="btn-primary">Save Settings</button>`;
    form.appendChild(btnGroup);
  }
  
  // Show JSON in read-only area
  document.getElementById('settings-json').textContent = JSON.stringify(cfg, null, 2);
}

async function saveSettings() {
  const activeFlux = document.getElementById('setting-active-flux').value;
  const frequency = parseInt(document.getElementById('setting-frequency').value);
  const minConf = parseFloat(document.getElementById('setting-min-confidence').value);
  
  const payload = {
    active_flux: activeFlux,
    trade_frequency_hours: frequency,
    min_confidence: minConf,
  };
  
  try {
    const data = await apiPost('/api/polymarket/config', payload);
    document.getElementById('settings-json').textContent = JSON.stringify(data.config || data, null, 2);
    alert('Settings saved successfully');
  } catch (err) {
    showError('settings-container', 'Failed to save settings');
  }
}

async function startFlux() {
  const res = await apiPost('/api/polymarket/flux/start', {});
  if (res.success) {
    document.getElementById('workforce-flux').textContent = 'running';
    document.getElementById('workforce-flux').className = 'tag ok';
  }
}

async function stopFlux() {
  const res = await apiPost('/api/polymarket/flux/stop', {});
  if (res.success) {
    document.getElementById('workforce-flux').textContent = 'stopped';
    document.getElementById('workforce-flux').className = 'tag warn';
  }
}

async function loadWorkforce() {
  setLoading('wf-status', true);
  setLoading('rss-cache', true);
  setLoading('mcp-status', true);
  
  const [status, rss, flux, fluxConfig, mcp] = await Promise.all([
    apiGet('/api/polymarket/workforce/status'),
    apiGet('/api/polymarket/rss/cache'),
    apiGet('/api/polymarket/flux/status'),
    apiGet('/api/polymarket/flux/config'),
    apiGet('/api/polymarket/workforce/mcp'),
  ]);
  
  setLoading('wf-status', false);
  setLoading('rss-cache', false);
  setLoading('mcp-status', false);
  
  // Workforce Status
  const wfEl = document.getElementById('wf-status');
  if (status && status.status === 'ok') {
    const triggerType = fluxConfig?.trigger_type || 'manual';
    const triggerSelect = document.getElementById('trigger-type-select');
    if (triggerSelect) {
      triggerSelect.value = triggerType;
    }
    const intervalInput = document.getElementById('trigger-interval-hours');
    if (intervalInput && fluxConfig?.interval_hours) {
      intervalInput.value = fluxConfig.interval_hours;
    }
    wfEl.innerHTML = `
      <div class="status-item">
        <span class="label">Status:</span>
        <span class="value ok">Active</span>
      </div>
      <div class="status-item">
        <span class="label">Flux:</span>
        <span class="value">${status.active_flux || 'unknown'}</span>
      </div>
      <div class="status-item">
        <span class="label">Trigger Type:</span>
        <span class="value">${triggerType}</span>
      </div>
      <div class="status-item">
        <span class="label">Trade Frequency:</span>
        <span class="value">${status.trade_frequency_hours || 'n/a'}h</span>
      </div>
      ${status.limits_status ? `
        <div class="status-item">
          <span class="label">Open Positions:</span>
          <span class="value">${status.limits_status.open_positions || 0}</span>
        </div>
        <div class="status-item">
          <span class="label">Max Positions:</span>
          <span class="value">${status.limits_status.max_positions || 'unlimited'}</span>
        </div>
      ` : ''}
      ${flux ? `
        <div class="status-item">
          <span class="label">Scan In Progress:</span>
          <span class="value">${flux.scan_in_progress ? 'yes' : 'no'}</span>
        </div>
        <div class="status-item">
          <span class="label">Last Trigger:</span>
          <span class="value">${flux.last_trigger_type || 'n/a'} ${flux.last_trigger_at ? `@ ${new Date(flux.last_trigger_at).toLocaleTimeString()}` : ''}</span>
        </div>
      ` : ''}
    `;
  } else {
    wfEl.innerHTML = '<div class="error">Failed to load workforce status</div>';
  }
  
  // RSS Cache
  const rssEl = document.getElementById('rss-cache');
  if (rss && rss.status === 'ok') {
    const lastUpdate = rss.updated_at ? new Date(rss.updated_at).toLocaleString() : 'Never';
    rssEl.innerHTML = `
      <div class="status-item">
        <span class="label">Cached Markets:</span>
        <span class="value">${rss.count || 0}</span>
      </div>
      <div class="status-item">
        <span class="label">Last Updated:</span>
        <span class="value">${lastUpdate}</span>
      </div>
      <div class="markets-list" style="margin-top: 10px; max-height: 200px; overflow-y: auto;">
        ${Object.keys(rss.markets || {}).slice(0, 5).map(key => `
          <div class="market-item" style="padding: 5px; border-bottom: 1px solid #eee;">
            <strong>${key}</strong>: ${rss.markets[key]?.title || 'N/A'}
          </div>
        `).join('')}
      </div>
    `;
  } else {
    rssEl.innerHTML = '<div class="muted">No RSS cache available</div>';
  }

  // MCP Status
  const mcpEl = document.getElementById('mcp-status');
  if (mcpEl) {
    if (mcp && mcp.status === 'ok') {
      const meta = mcp.mcp || {};
      const nameInput = document.getElementById('mcp-name');
      const hostInput = document.getElementById('mcp-host');
      const portInput = document.getElementById('mcp-port');
      if (nameInput && meta.name) nameInput.value = meta.name;
      if (hostInput && meta.host) hostInput.value = meta.host;
      if (portInput && meta.port) portInput.value = meta.port;
      mcpEl.innerHTML = `
        <div class="status-item">
          <span class="label">Server:</span>
          <span class="value">${mcp.started ? 'running' : 'stopped'}</span>
        </div>
        <div class="status-item">
          <span class="label">Host:</span>
          <span class="value">${meta.host || 'n/a'}</span>
        </div>
        <div class="status-item">
          <span class="label">Port:</span>
          <span class="value">${meta.port || 'n/a'}</span>
        </div>
      `;
    } else {
      mcpEl.innerHTML = '<div class="muted">MCP server not initialized</div>';
    }
  }
}

async function triggerWorkforce() {
  const btn = document.getElementById('trigger-wf');
  if (btn) btn.disabled = true;
  
  setLoading('wf-trigger-result', true);
  const res = await apiPost('/api/polymarket/flux/trigger-scan?verify_positions=false&start_if_stopped=true', {});
  setLoading('wf-trigger-result', false);
  
  const resultEl = document.getElementById('wf-trigger-result');
  if (res.status === 'ok' || res.status === 'triggered') {
    resultEl.innerHTML = `<div class="success">✓ ${res.message || 'Flux triggered'}</div>`;
    resultEl.style.display = 'block';
    setTimeout(() => loadWorkforce(), 1000);
  } else {
    resultEl.innerHTML = `<div class="error">✗ ${res.message || 'Trigger failed'}</div>`;
    resultEl.style.display = 'block';
  }
  
  if (btn) {
    btn.disabled = false;
    setTimeout(() => {
      resultEl.style.display = 'none';
    }, 5000);
  }
}

async function changeTriggerType() {
  const select = document.getElementById('trigger-type-select');
  const intervalInput = document.getElementById('trigger-interval-hours');
  if (!select) return;

  const newType = select.value;
  const intervalHours = intervalInput ? parseInt(intervalInput.value || '4', 10) : 4;
  const qs = new URLSearchParams({
    trigger_type: newType,
    interval_hours: String(Math.max(1, intervalHours)),
  }).toString();

  try {
    await apiPost(`/api/polymarket/flux/config?${qs}`, {});
    await loadWorkforce();
  } catch (err) {
    showError('wf-status', 'Failed to change trigger type');
  }
}

async function startMcp() {
  const name = document.getElementById('mcp-name')?.value || 'CAMEL-Workforce';
  const host = document.getElementById('mcp-host')?.value || 'localhost';
  const port = document.getElementById('mcp-port')?.value || '8001';
  const payload = {
    name,
    host,
    port: parseInt(port, 10) || 8001,
    start_server: true,
  };
  const res = await apiPost('/api/polymarket/workforce/mcp', payload);
  if (res.status === 'ok') {
    alert('MCP server initialized');
    await loadWorkforce();
  } else {
    showError('mcp-status', res.message || 'Failed to start MCP server');
  }
}

async function exportResultsCSV() {
  const trades = await apiGet('/api/polymarket/results/trades?limit=1000');
  const items = trades.trades || [];
  if (!items.length) return alert('No trades to export');
  const rows = items.map(t => [t.market_id||t.bet_id||'', t.outcome||'', t.quantity||'', t.price||'', t.status||''].map(v => `"${String(v).replace(/"/g,'""')}"`).join(','));
  const csv = 'market,outcome,quantity,price,status\n' + rows.join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'polymarket_results.csv'; a.click();
  URL.revokeObjectURL(url);
}

window.ui = {
  loadDashboard,
  loadMarkets,
  loadResults,
  loadSettings,
  saveSettings,
  startFlux,
  stopFlux,
  exportResultsCSV,
  loadClobSnapshot,
  loadWorkforce,
  triggerWorkforce,
  changeTriggerType,
  startMcp,
  setLoading,
  showError,
  loadOpenOrders,
  loadTrades,
  showAuthModal: () => {
    document.getElementById('auth-modal').style.display = 'flex';
  },
  closeAuthModal: () => {
    document.getElementById('auth-modal').style.display = 'none';
    document.getElementById('auth-error').style.display = 'none';
  },
  handleLogin: async (event) => {
    event.preventDefault();
    const apiKey = document.getElementById('auth-api-key').value;
    const walletAddr = document.getElementById('auth-wallet-input').value;
    
    try {
      const payload = {};
      if (apiKey && apiKey.trim()) payload.api_key = apiKey.trim();
      if (walletAddr) payload.wallet_address = walletAddr;
      
      const res = await apiPost('/api/polymarket/auth/login', payload);
      
      if (res.status === 'ok' || res.is_authenticated) {
        alert('Authenticated successfully!');
        window.ui.closeAuthModal();
        window.location.reload();
      } else {
        const errEl = document.getElementById('auth-error');
        errEl.textContent = res.message || 'Authentication failed';
        errEl.style.display = 'block';
      }
    } catch (err) {
      const errEl = document.getElementById('auth-error');
      errEl.textContent = 'Error: ' + err.message;
      errEl.style.display = 'block';
    }
  },
};

async function loadClobSnapshot() {
  const statusEl = document.getElementById('clob-status');
  const ordersTable = document.getElementById('clob-orders-table');
  const ordersEmpty = document.getElementById('clob-orders-empty');
  const tradesTable = document.getElementById('clob-trades-table');
  const tradesEmpty = document.getElementById('clob-trades-empty');

  if (!statusEl || !ordersTable || !tradesTable) return;

  try {
    const [ordersData, tradesData] = await Promise.all([
      apiGet('/api/polymarket/clob/orders/open'),
      apiGet('/api/polymarket/clob/trades'),
    ]);

    const orders = ordersData.orders || [];
    const trades = tradesData.trades || [];
    document.getElementById('kpi-open-orders').textContent = orders.length;
    document.getElementById('kpi-recent-trades').textContent = trades.length;
    document.getElementById('kpi-latest-price').textContent = trades[0]?.price ?? '-';
    statusEl.textContent = 'CLOB data synced.';

    ordersTable.innerHTML = '';
    if (!orders.length) {
      if (ordersEmpty) ordersEmpty.style.display = 'block';
    } else {
      if (ordersEmpty) ordersEmpty.style.display = 'none';
      orders.slice(0, 8).forEach(o => {
        const row = document.createElement('tr');
        row.innerHTML = `<td>${o.order_id || o.id || ''}</td><td>${o.market || o.market_id || ''}</td><td>${o.side || ''}</td><td>${o.price ?? ''}</td><td>${o.size ?? ''}</td>`;
        ordersTable.appendChild(row);
      });
    }

    tradesTable.innerHTML = '';
    if (!trades.length) {
      if (tradesEmpty) tradesEmpty.style.display = 'block';
    } else {
      if (tradesEmpty) tradesEmpty.style.display = 'none';
      trades.slice(0, 8).forEach(t => {
        const row = document.createElement('tr');
        row.innerHTML = `<td>${t.market || t.market_id || ''}</td><td>${t.side || t.taker_side || ''}</td><td>${t.price ?? ''}</td><td>${t.size ?? ''}</td>`;
        tradesTable.appendChild(row);
      });
    }
  } catch (err) {
    console.warn('loadClobSnapshot failed', err);
    statusEl.textContent = 'CLOB data unavailable (missing auth or network).';
  }
}

async function loadOpenOrders() {
  const market = document.getElementById('orders-market')?.value || '';
  const ordersTable = document.getElementById('orders-open');
  const emptyEl = document.getElementById('orders-open-empty');
  if (!ordersTable) return;

  const qs = market ? `?market=${encodeURIComponent(market)}` : '';
  const data = await apiGet(`/api/polymarket/clob/orders/open${qs}`);
  const orders = data.orders || [];
  ordersTable.innerHTML = '';
  if (!orders.length) {
    if (emptyEl) emptyEl.style.display = 'block';
    return;
  }
  if (emptyEl) emptyEl.style.display = 'none';
  orders.forEach(o => {
    const row = document.createElement('tr');
    row.innerHTML = `<td>${o.order_id || o.id || ''}</td><td>${o.market || o.market_id || ''}</td><td>${o.side || ''}</td><td>${o.price ?? ''}</td><td>${o.size ?? ''}</td><td>-</td>`;
    ordersTable.appendChild(row);
  });
}

async function loadTrades() {
  const market = document.getElementById('trades-market')?.value || '';
  const tradesTable = document.getElementById('trades-list');
  const emptyEl = document.getElementById('trades-list-empty');
  if (!tradesTable) return;

  const qs = market ? `?market=${encodeURIComponent(market)}` : '';
  const data = await apiGet(`/api/polymarket/clob/trades${qs}`);
  const trades = data.trades || [];
  tradesTable.innerHTML = '';
  if (!trades.length) {
    if (emptyEl) emptyEl.style.display = 'block';
    return;
  }
  if (emptyEl) emptyEl.style.display = 'none';
  trades.forEach(t => {
    const row = document.createElement('tr');
    const ts = t.timestamp ? new Date(t.timestamp).toLocaleString() : '';
    row.innerHTML = `<td>${t.market || t.market_id || ''}</td><td>${t.side || t.taker_side || ''}</td><td>${t.price ?? ''}</td><td>${t.size ?? ''}</td><td>${ts}</td>`;
    tradesTable.appendChild(row);
  });
}

// Initialize event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Dashboard buttons
  const btnSearchMarkets = document.getElementById('btn-search-markets');
  if (btnSearchMarkets) btnSearchMarkets.addEventListener('click', window.ui.loadMarkets);
  
  const btnRefreshDashboard = document.getElementById('btn-refresh-dashboard');
  if (btnRefreshDashboard) btnRefreshDashboard.addEventListener('click', window.ui.loadDashboard);
  
  const btnRefreshResults = document.getElementById('btn-refresh-results');
  if (btnRefreshResults) btnRefreshResults.addEventListener('click', window.ui.loadResults);
  
  const btnExportResults = document.getElementById('btn-export-results');
  if (btnExportResults) btnExportResults.addEventListener('click', window.ui.exportResultsCSV);
  
  const btnStartFlux = document.getElementById('btn-start-flux');
  if (btnStartFlux) btnStartFlux.addEventListener('click', window.ui.startFlux);
  
  const btnStopFlux = document.getElementById('btn-stop-flux');
  if (btnStopFlux) btnStopFlux.addEventListener('click', window.ui.stopFlux);
  
  // Market query input - search on enter key
  const marketQuery = document.getElementById('market-query');
  if (marketQuery) {
    marketQuery.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') window.ui.loadMarkets();
    });
  }
});
