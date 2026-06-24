import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TrendingUp, Shield, Activity, RefreshCw, Search,
  Terminal, Wallet, ChevronRight, BarChart3, Clock,
  CheckCircle2, XCircle, MinusCircle, LineChart as LineChartIcon,
  FlaskConical
} from 'lucide-react';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, ReferenceLine, CartesianGrid
} from 'recharts';
import './App.css';

const API_BASE = "/api";
const WS_URL = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws`;

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
};

const formatChartDate = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
};

const PnlTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const pt = payload[0]?.payload;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-date">{formatChartDate(label)}</div>
      <div className="chart-tooltip-row">
        <span>Value</span>
        <strong>${pt?.total_value?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</strong>
      </div>
      <div className="chart-tooltip-row">
        <span>P&L</span>
        <strong className={pt?.pnl >= 0 ? 'positive' : 'negative'}>
          {pt?.pnl >= 0 ? '+' : ''}{pt?.pnl?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          {' '}({pt?.pnl_pct?.toFixed(2)}%)
        </strong>
      </div>
    </div>
  );
};

function App() {
  const [activeTab, setActiveTab] = useState('decisions');
  const [history, setHistory] = useState([]);
  const [pnlHistory, setPnlHistory] = useState([]);
  const [initialCash, setInitialCash] = useState(100000);
  const [backtest, setBacktest] = useState({ results: [], summary: {} });
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [ticker, setTicker] = useState("");
  const [risk, setRisk] = useState("conservative");
  const [persona, setPersona] = useState("standard");
  const [humanInsight, setHumanInsight] = useState("");
  const [targetDate, setTargetDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [loading, setLoading] = useState(false);
  const [portfolio, setPortfolio] = useState({ cash: 0, total_value: 0, holdings: {}, pnl: 0, pnl_pct: 0, holdings_value: 0 });
  const [logs, setLogs] = useState([]);
  const [serverOnline, setServerOnline] = useState(false);
  const ws = useRef(null);
  const reconnectRef = useRef(null);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/history`);
      setHistory(res.data.history);
    } catch (err) { console.error(err); }
  }, []);

  const fetchPortfolio = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/portfolio`);
      setPortfolio(res.data);
    } catch (err) { console.error(err); }
  }, []);

  const fetchPnlHistory = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/portfolio/pnl-history`);
      setPnlHistory(res.data.history || []);
      setInitialCash(res.data.initial_cash || 100000);
    } catch (err) { console.error(err); }
  }, []);

  const fetchBacktest = useCallback(async () => {
    setBacktestLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/backtest`, { timeout: 120000 });
      setBacktest({ results: res.data.results || [], summary: res.data.summary || {} });
    } catch (err) {
      console.error(err);
      setBacktest({ results: [], summary: {} });
    }
    setBacktestLoading(false);
  }, []);

  const checkHealth = useCallback(async () => {
    try {
      await axios.get(`${API_BASE}/health`, { timeout: 3000 });
      setServerOnline(true);
    } catch {
      setServerOnline(false);
    }
  }, []);

  const refreshAll = useCallback(() => {
    fetchHistory();
    fetchPortfolio();
    fetchPnlHistory();
  }, [fetchHistory, fetchPortfolio, fetchPnlHistory]);

  const connectWS = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return;

    ws.current = new WebSocket(WS_URL);

    ws.current.onopen = () => {
      setServerOnline(true);
      if (reconnectRef.current) clearInterval(reconnectRef.current);
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const msg = data.message || event.data;
        const logClass = msg.includes("complete") || msg.includes("completed")
          ? "log-complete"
          : msg.includes("error") || msg.includes("failed")
            ? "log-error"
            : "";

        setLogs(prev => [{ text: msg, cls: logClass }, ...prev].slice(0, 100));

        if (msg.includes("complete")) {
          refreshAll();
        }
      } catch {
        setLogs(prev => [{ text: event.data, cls: "" }, ...prev].slice(0, 100));
      }
    };

    ws.current.onclose = () => {
      setServerOnline(false);
      reconnectRef.current = setTimeout(connectWS, 3000);
    };

    ws.current.onerror = () => {
      ws.current?.close();
    };
  }, [refreshAll]);

  useEffect(() => {
    refreshAll();
    checkHealth();
    connectWS();

    const healthInterval = setInterval(checkHealth, 15000);

    return () => {
      ws.current?.close();
      if (reconnectRef.current) clearInterval(reconnectRef.current);
      clearInterval(healthInterval);
    };
  }, [refreshAll, checkHealth, connectWS]);

  useEffect(() => {
    if (activeTab === 'backtest' && backtest.results.length === 0 && !backtestLoading) {
      fetchBacktest();
    }
  }, [activeTab, backtest.results.length, backtestLoading, fetchBacktest]);

  const handleAnalyze = async () => {
    if (!ticker.trim()) return;
    setLoading(true);
    setLogs(prev => [{ text: `Initiating analysis for ${ticker.toUpperCase()}...`, cls: "" }, ...prev]);
    try {
      await axios.post(`${API_BASE}/analyze/${ticker}`, {
        risk_level: risk,
        persona: persona,
        human_insight: humanInsight,
        target_date: targetDate
      });
    } catch {
      setLogs(prev => [{ text: "Connection failed: Server offline", cls: "log-error" }, ...prev]);
    }
    setLoading(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !loading) handleAnalyze();
  };

  const pnlPositive = (portfolio.pnl ?? 0) >= 0;

  const chartData = useMemo(() =>
    pnlHistory.map((pt) => ({
      ...pt,
      label: pt.timestamp,
    })),
    [pnlHistory]
  );

  const { summary } = backtest;

  return (
    <>
      <div className="mesh-bg" />
      <div className="container">
        <header>
          <motion.div className="header-brand" {...fadeUp}>
            <h1>T-AGENT <span style={{ color: 'var(--primary)' }}>PRO</span></h1>
            <p className="subtitle">Intelligence-Driven Multi-Agent Trading Architecture</p>
          </motion.div>

          <motion.div
            className="glass header-portfolio"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
          >
            <div className="metric">
              <span className="metric-label">Total Value</span>
              <span className="metric-value">${portfolio.total_value?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
            </div>
            <div className="metric">
              <span className="metric-label">P&L</span>
              <span className={`metric-value ${pnlPositive ? 'positive' : 'negative'}`}>
                {pnlPositive ? '+' : ''}{portfolio.pnl?.toLocaleString(undefined, { maximumFractionDigits: 0 })} ({portfolio.pnl_pct?.toFixed(2)}%)
              </span>
            </div>
            <div className="icon-box icon-box-green">
              <Wallet color="var(--accent-green)" size={22} />
            </div>
          </motion.div>
        </header>

        <div className="stats-grid">
          {[
            { label: 'Analyses Run', value: history.length, icon: <Activity size={18} color="var(--primary)" /> },
            { label: 'Risk Profile', value: risk, icon: <Shield size={18} color="var(--accent-blue)" />, cap: true },
            { label: 'Active Persona', value: persona === 'standard' ? 'Balanced' : persona, icon: <BarChart3 size={18} color="var(--accent-gold)" /> },
            { label: 'System Status', value: serverOnline ? 'Online' : 'Offline', icon: <div className={`status-dot${serverOnline ? '' : ' offline'}`} /> },
          ].map((stat, i) => (
            <motion.div
              key={i}
              className="stat-card glass"
              {...fadeUp}
              transition={{ delay: i * 0.05 }}
            >
              <span className="label">{stat.label}</span>
              <div className="stat-row">
                <div className="stat-value" style={{ textTransform: stat.cap ? 'capitalize' : 'none', fontSize: '1.25rem' }}>
                  {stat.value}
                </div>
                {stat.icon}
              </div>
            </motion.div>
          ))}
        </div>

        <motion.div
          className="glass chart-panel"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="panel-header">
            <h2><LineChartIcon size={18} style={{ marginRight: 8, verticalAlign: 'middle' }} />Portfolio P&L</h2>
            <button className="icon-btn" onClick={fetchPnlHistory} title="Refresh chart">
              <RefreshCw size={14} />
            </button>
          </div>
          <div className="chart-wrap">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis
                    dataKey="label"
                    tickFormatter={formatChartDate}
                    stroke="var(--text-dim)"
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={40}
                  />
                  <YAxis
                    domain={['auto', 'auto']}
                    tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                    stroke="var(--text-dim)"
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    width={48}
                  />
                  <Tooltip content={<PnlTooltip />} />
                  <ReferenceLine y={initialCash} stroke="var(--text-dim)" strokeDasharray="4 4" />
                  <Area
                    type="monotone"
                    dataKey="total_value"
                    stroke="var(--primary)"
                    strokeWidth={2}
                    fill="url(#pnlGradient)"
                    dot={chartData.length <= 20}
                    activeDot={{ r: 4, fill: 'var(--primary)' }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="chart-empty">No portfolio history yet — run an analysis to begin tracking.</div>
            )}
          </div>
        </motion.div>

        <div className="main-content">
          <motion.div className="glass panel" initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}>
            <div className="panel-header">
              <div className="tab-bar">
                <button
                  className={`tab-btn${activeTab === 'decisions' ? ' active' : ''}`}
                  onClick={() => setActiveTab('decisions')}
                >
                  <BarChart3 size={14} /> Decision Archive
                </button>
                <button
                  className={`tab-btn${activeTab === 'backtest' ? ' active' : ''}`}
                  onClick={() => setActiveTab('backtest')}
                >
                  <FlaskConical size={14} /> Backtest (7d ROI)
                </button>
              </div>
              <button
                className="icon-btn"
                onClick={activeTab === 'backtest' ? fetchBacktest : refreshAll}
                title="Refresh"
              >
                <RefreshCw size={14} className={backtestLoading ? 'spin' : ''} />
              </button>
            </div>

            {activeTab === 'decisions' && (
              <div className="panel-body">
                <AnimatePresence>
                  {history.length === 0 && (
                    <div className="empty-state">
                      <BarChart3 size={40} style={{ opacity: 0.2, marginBottom: 12 }} />
                      <p>No decisions yet. Run your first analysis to begin.</p>
                    </div>
                  )}
                  {history.map((item, idx) => (
                    <motion.div
                      key={`${item.date}-${item.ticker}-${idx}`}
                      className="decision-item"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ delay: idx * 0.03 }}
                    >
                      <div className="decision-header">
                        <div className="decision-identity">
                          <span className="decision-ticker">{item.ticker}</span>
                          <span className={`badge badge-${item.action?.toLowerCase()}`}>{item.action}</span>
                        </div>
                        <span className="decision-date"><Clock size={12} style={{ marginRight: 4, verticalAlign: 'middle' }} />{item.date}</span>
                      </div>
                      <p className="decision-reasoning">{item.reasoning}</p>
                      <div className="decision-meta">
                        <span><TrendingUp size={13} /> Allocation: {item.quantity}</span>
                        <span><Shield size={13} /> Verified</span>
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}

            {activeTab === 'backtest' && (
              <div className="panel-body">
                {backtestLoading && (
                  <div className="empty-state">
                    <RefreshCw size={32} className="spin" style={{ opacity: 0.4, marginBottom: 12 }} />
                    <p>Running backtest against market data…</p>
                  </div>
                )}

                {!backtestLoading && backtest.results.length === 0 && (
                  <div className="empty-state">
                    <FlaskConical size={40} style={{ opacity: 0.2, marginBottom: 12 }} />
                    <p>No backtestable decisions found. Run BUY/SELL analyses first.</p>
                  </div>
                )}

                {!backtestLoading && backtest.results.length > 0 && (
                  <>
                    <div className="backtest-summary">
                      <div className="summary-stat">
                        <span className="label">Actionable</span>
                        <span className="value">{summary.actionable ?? 0}</span>
                      </div>
                      <div className="summary-stat">
                        <span className="label">Avg ROI (7d)</span>
                        <span className={`value ${(summary.avg_roi ?? 0) >= 0 ? 'positive' : 'negative'}`}>
                          {(summary.avg_roi ?? 0) >= 0 ? '+' : ''}{summary.avg_roi ?? 0}%
                        </span>
                      </div>
                      <div className="summary-stat">
                        <span className="label">Win Rate</span>
                        <span className="value">{summary.win_rate ?? 0}%</span>
                      </div>
                      <div className="summary-stat">
                        <span className="label">W / L</span>
                        <span className="value">{summary.wins ?? 0} / {summary.losses ?? 0}</span>
                      </div>
                    </div>

                    <div className="backtest-table-wrap">
                      <table className="backtest-table">
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th>Ticker</th>
                            <th>Action</th>
                            <th>Start</th>
                            <th>End (7d)</th>
                            <th>ROI</th>
                          </tr>
                        </thead>
                        <tbody>
                          {backtest.results.map((row, idx) => (
                            <tr key={`${row.date}-${row.ticker}-${idx}`}>
                              <td>{row.date}</td>
                              <td className="ticker-cell">{row.ticker}</td>
                              <td><span className={`badge badge-${row.action?.toLowerCase()}`}>{row.action}</span></td>
                              <td>${row.start_price?.toFixed(2)}</td>
                              <td>${row.end_price?.toFixed(2)}</td>
                              <td className={row.roi > 0 ? 'positive' : row.roi < 0 ? 'negative' : ''}>
                                {row.roi > 0 ? '+' : ''}{row.roi?.toFixed(2)}%
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </div>
            )}

            {portfolio.holdings && Object.keys(portfolio.holdings).length > 0 && (
              <div className="portfolio-section" style={{ borderTop: '1px solid var(--glass-border)' }}>
                <h3 style={{ fontSize: '1rem', marginBottom: '12px' }}>Holdings</h3>
                {Object.entries(portfolio.holdings).map(([sym, h]) => (
                  <div key={sym} className="holding-item">
                    <span className="holding-ticker">{sym}</span>
                    <span className="holding-detail">{h.qty} shares @ ${h.avg_price?.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            )}
          </motion.div>

          <aside className="control-panel">
            <motion.div className="glass control-card" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
              <h2>Analysis Controls</h2>

              <div className="input-group">
                <label>Target Symbol</label>
                <div className="input-wrapper">
                  <input
                    type="text"
                    placeholder="e.g. NVDA, BTC-USD"
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value.toUpperCase())}
                    onKeyDown={handleKeyDown}
                  />
                  <Search size={16} className="search-icon" />
                </div>
              </div>

              <div className="input-group">
                <label>Risk Matrix</label>
                <select value={risk} onChange={(e) => setRisk(e.target.value)}>
                  <option value="conservative">Conservative — Guard Capital</option>
                  <option value="aggressive">Aggressive — Maximize ROI</option>
                </select>
              </div>

              <div className="input-group">
                <label>Boardroom Persona</label>
                <select value={persona} onChange={(e) => setPersona(e.target.value)}>
                  <option value="standard">Balanced Portfolio Manager</option>
                  <option value="Warren Buffett (Value)">Warren Buffett — Value Investor</option>
                  <option value="WSB Degen">WSB Degen — Momentum Trader</option>
                  <option value="The Quant">The Quant — Data Only</option>
                </select>
              </div>

              <div className="input-group">
                <label>Target Date</label>
                <input
                  type="date"
                  value={targetDate}
                  onChange={(e) => setTargetDate(e.target.value)}
                />
              </div>

              <div className="input-group">
                <label>Human Override (Alpha Signal)</label>
                <textarea
                  rows="3"
                  placeholder="Optional: inject your own market insight..."
                  value={humanInsight}
                  onChange={(e) => setHumanInsight(e.target.value)}
                />
              </div>

              <motion.button
                className="btn-primary"
                onClick={handleAnalyze}
                disabled={loading || !ticker.trim()}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
              >
                {loading ? <RefreshCw className="spin" size={18} /> : <>Initiate Analysis <ChevronRight size={18} /></>}
              </motion.button>
            </motion.div>

            <motion.div
              className="terminal-box"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
            >
              <div className="terminal-header">
                <Terminal size={13} /> Intelligence Feed
              </div>
              <div className="terminal-content">
                {logs.map((log, i) => (
                  <motion.div
                    key={i}
                    className={`log-entry ${log.cls}`}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                  >
                    {log.text}
                  </motion.div>
                ))}
                {logs.length === 0 && (
                  <div className="terminal-empty">Awaiting connection...</div>
                )}
              </div>
            </motion.div>
          </aside>
        </div>
      </div>
    </>
  );
}

export default App;
