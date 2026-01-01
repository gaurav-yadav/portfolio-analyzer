/**
 * Portfolio Analyzer Dashboard
 * Reads analysis CSV output and displays comprehensive dashboard
 */

const state = {
    stocks: [],
    filteredStocks: [],
    portfolioHealth: null,
    sortColumn: 'overall_score',
    sortDirection: 'desc',
    charts: { recommendation: null, score: null }
};

const RECOMMENDATIONS = {
    'STRONG BUY': { class: 'strong-buy', color: '#059669' },
    'BUY': { class: 'buy', color: '#10b981' },
    'HOLD': { class: 'hold', color: '#f59e0b' },
    'SELL': { class: 'sell', color: '#ef4444' },
    'STRONG SELL': { class: 'strong-sell', color: '#b91c1c' }
};

function init() {
    document.getElementById('fileInput').addEventListener('change', e => {
        if (e.target.files[0]) processFile(e.target.files[0]);
    });

    const uploadArea = document.getElementById('uploadArea');
    uploadArea.addEventListener('dragover', e => { e.preventDefault(); uploadArea.classList.add('drag-over'); });
    uploadArea.addEventListener('dragleave', e => { e.preventDefault(); uploadArea.classList.remove('drag-over'); });
    uploadArea.addEventListener('drop', e => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        if (e.dataTransfer.files[0]) processFile(e.dataTransfer.files[0]);
    });
    uploadArea.addEventListener('click', () => document.getElementById('fileInput').click());

    document.getElementById('searchInput').addEventListener('input', handleSearch);
    document.getElementById('resetBtn').addEventListener('click', handleReset);
    document.getElementById('modalClose').addEventListener('click', closeModal);
    document.getElementById('stockModal').addEventListener('click', e => {
        if (e.target.id === 'stockModal') closeModal();
    });

    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => handleSort(th.dataset.sort));
    });
}

function processFile(file) {
    Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: results => {
            const { stocks, health } = parseAnalysisData(results.data);
            if (stocks.length > 0) {
                state.stocks = stocks;
                state.filteredStocks = [...stocks];
                state.portfolioHealth = health;
                document.getElementById('uploadSection').style.display = 'none';
                document.getElementById('dashboard').style.display = 'block';
                updateDashboard();
            } else {
                alert('No valid stock data found. Make sure this is an analysis output CSV.');
            }
        },
        error: err => alert('Error parsing CSV: ' + err.message)
    });
}

function parseAnalysisData(rows) {
    const stocks = [];
    let health = null;

    // Check for portfolio health footer rows
    for (const row of rows) {
        const firstCol = Object.values(row)[0] || '';

        // Skip header/separator rows
        if (firstCol.includes('===') || firstCol.includes('PORTFOLIO HEALTH')) continue;

        // Parse health summary rows
        if (firstCol.includes('Total Stocks Analyzed')) {
            health = health || {};
            health.totalStocks = parseInt(Object.values(row)[1]) || 0;
            continue;
        }
        if (firstCol.includes('Portfolio Health Score')) {
            health = health || {};
            health.score = parseFloat(Object.values(row)[1]) || 0;
            continue;
        }
        if (firstCol.includes('Portfolio Health:')) {
            health = health || {};
            health.rating = Object.values(row)[1] || '';
            continue;
        }
        if (firstCol.includes('Top Performer')) {
            health = health || {};
            health.topPerformer = Object.values(row)[1] || '';
            health.topScore = Object.values(row)[2] || '';
            continue;
        }
        if (firstCol.includes('Needs Attention') || firstCol.includes('Worst')) {
            health = health || {};
            health.needsAttention = Object.values(row)[1] || '';
            health.worstScore = Object.values(row)[2] || '';
            continue;
        }
        if (firstCol.includes('OVERALL RECOMMENDATION')) {
            health = health || {};
            health.recommendation = Object.values(row)[1] || '';
            continue;
        }
        if (firstCol.includes('STRONG BUY:') || firstCol.includes('BUY:') ||
            firstCol.includes('HOLD:') || firstCol.includes('SELL:')) {
            continue; // Skip distribution rows
        }

        // Parse stock rows
        const stock = parseStockRow(row);
        if (stock) stocks.push(stock);
    }

    // Calculate health from stocks if not in footer
    if (!health && stocks.length > 0) {
        const avgScore = stocks.reduce((s, st) => s + st.overall_score, 0) / stocks.length;
        health = {
            totalStocks: stocks.length,
            score: avgScore,
            rating: getHealthRating(avgScore)
        };
    }

    return { stocks, health };
}

function parseStockRow(row) {
    // Map various column names to our expected fields
    const get = (...keys) => {
        for (const k of keys) {
            const val = row[k] || row[k.toLowerCase()] || row[k.toUpperCase()];
            if (val !== undefined && val !== '') return val;
        }
        return null;
    };

    const symbol = get('symbol', 'Symbol', 'SYMBOL', 'instrument', 'Instrument');
    if (!symbol || symbol.includes('===') || symbol.includes('Total') || symbol.includes('Portfolio') ||
        symbol.includes('RECOMMENDATION') || symbol.includes('Report Generated') || symbol.includes('OVERALL')) return null;

    const parseNum = v => v ? parseFloat(String(v).replace(/[₹,%]/g, '')) : 0;

    return {
        symbol: symbol,
        name: get('name', 'Name', 'company', 'instrument') || symbol,
        quantity: parseNum(get('quantity', 'qty', 'Qty.')),
        avg_price: parseNum(get('avg_price', 'Avg. cost', 'average_price')),
        current_price: parseNum(get('current_price', 'LTP', 'ltp', 'cmp')),
        pnl_pct: parseNum(get('pnl_pct', 'pnl_percent', 'Net chg.', 'P&L %')),

        // Technical indicators
        rsi: parseNum(get('rsi', 'RSI')),
        rsi_score: parseNum(get('rsi_score')),
        macd_score: parseNum(get('macd_score')),
        trend_score: parseNum(get('trend_score')),
        bollinger_score: parseNum(get('bollinger_score')),
        adx_score: parseNum(get('adx_score')),
        volume_score: parseNum(get('volume_score')),

        // Component scores
        technical_score: parseNum(get('technical_score')),
        fundamental_score: parseNum(get('fundamental_score')),
        news_sentiment_score: parseNum(get('news_sentiment_score', 'news_score')),
        legal_corporate_score: parseNum(get('legal_corporate_score', 'legal_score')),

        // Final
        overall_score: parseNum(get('overall_score', 'score')),
        recommendation: get('recommendation', 'Recommendation') || 'HOLD',
        red_flags: get('red_flags', 'Red Flags') || '',
        summary: get('summary', 'Summary') || ''
    };
}

function getHealthRating(score) {
    if (score >= 7.5) return 'Excellent';
    if (score >= 6.0) return 'Good';
    if (score >= 5.0) return 'Fair';
    if (score >= 4.0) return 'Needs Attention';
    return 'At Risk';
}

function updateDashboard() {
    updateHealthSummary();
    updateSummaryCards();
    updateCharts();
    updateTable();
}

function updateHealthSummary() {
    const health = state.portfolioHealth;
    const stocks = state.stocks;

    // Count recommendations
    const counts = { 'STRONG BUY': 0, 'BUY': 0, 'HOLD': 0, 'SELL': 0, 'STRONG SELL': 0 };
    stocks.forEach(s => counts[s.recommendation] = (counts[s.recommendation] || 0) + 1);

    // Find top and worst performers
    const sorted = [...stocks].sort((a, b) => b.overall_score - a.overall_score);
    const top = sorted[0];
    const worst = sorted[sorted.length - 1];

    const healthHtml = `
        <div class="health-summary">
            <h2>Portfolio Health Summary</h2>
            <div class="health-grid">
                <div class="health-item">
                    <span class="health-label">Total Stocks</span>
                    <span class="health-value">${stocks.length}</span>
                </div>
                <div class="health-item">
                    <span class="health-label">Health Score</span>
                    <span class="health-value score-${getScoreClass(health?.score || 0)}">${(health?.score || 0).toFixed(1)}/10</span>
                </div>
                <div class="health-item">
                    <span class="health-label">Rating</span>
                    <span class="health-value">${health?.rating || getHealthRating(health?.score || 0)}</span>
                </div>
            </div>

            <div class="distribution">
                <h3>Recommendation Distribution</h3>
                <div class="dist-bars">
                    ${Object.entries(counts).map(([rec, count]) => `
                        <div class="dist-row">
                            <span class="dist-label">${rec}</span>
                            <div class="dist-bar-container">
                                <div class="dist-bar dist-${RECOMMENDATIONS[rec]?.class || 'hold'}"
                                     style="width: ${stocks.length ? (count/stocks.length*100) : 0}%"></div>
                            </div>
                            <span class="dist-count">${count} (${stocks.length ? (count/stocks.length*100).toFixed(0) : 0}%)</span>
                        </div>
                    `).join('')}
                </div>
            </div>

            <div class="performers">
                ${top ? `
                <div class="performer top">
                    <span class="performer-label">🏆 Top Performer</span>
                    <span class="performer-value">${top.symbol} - ${top.overall_score.toFixed(1)}/10 (${top.recommendation})</span>
                </div>` : ''}
                ${worst ? `
                <div class="performer worst">
                    <span class="performer-label">⚠️ Needs Attention</span>
                    <span class="performer-value">${worst.symbol} - ${worst.overall_score.toFixed(1)}/10 (${worst.recommendation})</span>
                </div>` : ''}
            </div>
        </div>
    `;

    document.getElementById('healthSummary').innerHTML = healthHtml;
}

function updateSummaryCards() {
    const stocks = state.stocks;
    const avgScore = stocks.reduce((s, st) => s + st.overall_score, 0) / stocks.length || 0;
    const totalValue = stocks.reduce((s, st) => s + (st.quantity * st.current_price), 0);

    document.getElementById('totalStocks').textContent = stocks.length;
    document.getElementById('avgScore').textContent = avgScore.toFixed(1);

    const healthEl = document.getElementById('portfolioHealth');
    healthEl.textContent = getHealthRating(avgScore);
    healthEl.className = `card-value score-${getScoreClass(avgScore)}`;

    document.getElementById('totalValue').textContent = formatCurrency(totalValue);
}

function updateCharts() {
    // Recommendation chart
    const counts = { 'STRONG BUY': 0, 'BUY': 0, 'HOLD': 0, 'SELL': 0, 'STRONG SELL': 0 };
    state.stocks.forEach(s => counts[s.recommendation] = (counts[s.recommendation] || 0) + 1);

    const ctx1 = document.getElementById('recommendationChart').getContext('2d');
    if (state.charts.recommendation) state.charts.recommendation.destroy();
    state.charts.recommendation = new Chart(ctx1, {
        type: 'doughnut',
        data: {
            labels: Object.keys(counts),
            datasets: [{
                data: Object.values(counts),
                backgroundColor: Object.keys(counts).map(k => RECOMMENDATIONS[k]?.color || '#888'),
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'right' } },
            cutout: '60%'
        }
    });

    // Score chart
    const buckets = { '0-3': 0, '3-4.5': 0, '4.5-6.5': 0, '6.5-8': 0, '8-10': 0 };
    state.stocks.forEach(s => {
        if (s.overall_score < 3) buckets['0-3']++;
        else if (s.overall_score < 4.5) buckets['3-4.5']++;
        else if (s.overall_score < 6.5) buckets['4.5-6.5']++;
        else if (s.overall_score < 8) buckets['6.5-8']++;
        else buckets['8-10']++;
    });

    const ctx2 = document.getElementById('scoreChart').getContext('2d');
    if (state.charts.score) state.charts.score.destroy();
    state.charts.score = new Chart(ctx2, {
        type: 'bar',
        data: {
            labels: Object.keys(buckets),
            datasets: [{
                label: 'Stocks',
                data: Object.values(buckets),
                backgroundColor: ['#b91c1c', '#ef4444', '#f59e0b', '#10b981', '#059669'],
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: { beginAtZero: true, ticks: { stepSize: 1 } }
            }
        }
    });
}

function updateTable() {
    const stocks = state.filteredStocks;
    const tbody = document.getElementById('stocksTableBody');

    if (stocks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No stocks found</td></tr>';
        return;
    }

    tbody.innerHTML = stocks.map(s => `
        <tr onclick="showStockDetails('${s.symbol}')" class="${s.red_flags ? 'has-red-flag' : ''}">
            <td><strong>${s.symbol}</strong></td>
            <td class="tech-preview">
                <span class="mini-score" title="Technical Score (RSI: ${s.rsi?.toFixed(1) || 'N/A'})">T:${s.technical_score?.toFixed(1) || '-'}</span>
                <span class="mini-score" title="Fundamental Score (P/E, Revenue, Growth)">F:${s.fundamental_score?.toFixed(1) || '-'}</span>
                <span class="mini-score" title="News Sentiment Score (Recent news & analyst ratings)">N:${s.news_sentiment_score?.toFixed(1) || '-'}</span>
                <span class="mini-score" title="Legal/Corporate Score (Red flags, lawsuits, governance)">L:${s.legal_corporate_score?.toFixed(1) || '-'}</span>
            </td>
            <td class="${s.pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative'}">${s.pnl_pct >= 0 ? '+' : ''}${s.pnl_pct?.toFixed(1) || 0}%</td>
            <td><span class="score-badge score-${getScoreClass(s.overall_score)}">${s.overall_score?.toFixed(1) || '-'}</span></td>
            <td><span class="recommendation-badge recommendation-${RECOMMENDATIONS[s.recommendation]?.class || 'hold'}">${s.recommendation}</span></td>
            <td class="summary-cell" title="${s.summary}">${truncate(s.summary, 50)}</td>
            <td class="red-flag-cell">${s.red_flags ? '⚠️ ' + truncate(s.red_flags, 30) : '✓'}</td>
        </tr>
    `).join('');
}

function showStockDetails(symbol) {
    const s = state.stocks.find(st => st.symbol === symbol);
    if (!s) return;

    document.getElementById('modalTitle').textContent = `${s.symbol} - ${s.name}`;
    document.getElementById('modalBody').innerHTML = `
        <div class="detail-section">
            <h3>Overall Assessment</h3>
            <div class="detail-row">
                <span class="score-badge score-${getScoreClass(s.overall_score)} large">${s.overall_score?.toFixed(1)}/10</span>
                <span class="recommendation-badge recommendation-${RECOMMENDATIONS[s.recommendation]?.class || 'hold'} large">${s.recommendation}</span>
            </div>
        </div>

        <div class="detail-section">
            <h3>Technical Analysis</h3>
            <div class="indicator-grid">
                <div class="indicator">
                    <span class="ind-label">RSI (14)</span>
                    <span class="ind-value">${s.rsi?.toFixed(1) || 'N/A'}</span>
                    <span class="ind-score">Score: ${s.rsi_score || '-'}/10</span>
                </div>
                <div class="indicator">
                    <span class="ind-label">MACD</span>
                    <span class="ind-score">Score: ${s.macd_score || '-'}/10</span>
                </div>
                <div class="indicator">
                    <span class="ind-label">Trend (SMA)</span>
                    <span class="ind-score">Score: ${s.trend_score || '-'}/10</span>
                </div>
                <div class="indicator">
                    <span class="ind-label">Bollinger</span>
                    <span class="ind-score">Score: ${s.bollinger_score || '-'}/10</span>
                </div>
                <div class="indicator">
                    <span class="ind-label">ADX</span>
                    <span class="ind-score">Score: ${s.adx_score || '-'}/10</span>
                </div>
                <div class="indicator">
                    <span class="ind-label">Volume</span>
                    <span class="ind-score">Score: ${s.volume_score || '-'}/10</span>
                </div>
            </div>
            <div class="score-bar">
                <span class="sb-label">Technical Score</span>
                <div class="sb-track"><div class="sb-fill score-${getScoreClass(s.technical_score)}" style="width:${(s.technical_score||0)*10}%"></div></div>
                <span class="sb-value">${s.technical_score?.toFixed(1) || '-'}/10</span>
            </div>
        </div>

        <div class="detail-section">
            <h3>Component Scores</h3>
            <div class="score-bar">
                <span class="sb-label">Fundamental (30%)</span>
                <div class="sb-track"><div class="sb-fill score-${getScoreClass(s.fundamental_score)}" style="width:${(s.fundamental_score||0)*10}%"></div></div>
                <span class="sb-value">${s.fundamental_score?.toFixed(1) || '-'}/10</span>
            </div>
            <div class="score-bar">
                <span class="sb-label">News Sentiment (20%)</span>
                <div class="sb-track"><div class="sb-fill score-${getScoreClass(s.news_sentiment_score)}" style="width:${(s.news_sentiment_score||0)*10}%"></div></div>
                <span class="sb-value">${s.news_sentiment_score?.toFixed(1) || '-'}/10</span>
            </div>
            <div class="score-bar">
                <span class="sb-label">Legal/Corporate (15%)</span>
                <div class="sb-track"><div class="sb-fill score-${getScoreClass(s.legal_corporate_score)}" style="width:${(s.legal_corporate_score||0)*10}%"></div></div>
                <span class="sb-value">${s.legal_corporate_score?.toFixed(1) || '-'}/10</span>
            </div>
        </div>

        <div class="detail-section">
            <h3>Summary</h3>
            <p class="summary-text">${s.summary || 'No summary available.'}</p>
        </div>

        ${s.red_flags ? `
        <div class="detail-section red-flag-section">
            <h3>⚠️ Red Flags</h3>
            <p class="red-flag-text">${s.red_flags}</p>
        </div>
        ` : ''}

        <div class="detail-section">
            <h3>Holdings</h3>
            <div class="holdings-grid">
                <div><span class="h-label">Quantity</span><span class="h-value">${s.quantity}</span></div>
                <div><span class="h-label">Avg Price</span><span class="h-value">${formatCurrency(s.avg_price)}</span></div>
                <div><span class="h-label">Current Price</span><span class="h-value">${formatCurrency(s.current_price)}</span></div>
                <div><span class="h-label">P&L %</span><span class="h-value ${s.pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative'}">${s.pnl_pct >= 0 ? '+' : ''}${s.pnl_pct?.toFixed(2) || 0}%</span></div>
            </div>
        </div>
    `;

    document.getElementById('stockModal').classList.add('active');
}

function closeModal() {
    document.getElementById('stockModal').classList.remove('active');
}

function handleSearch(e) {
    const q = e.target.value.toLowerCase();
    state.filteredStocks = q ? state.stocks.filter(s =>
        s.symbol.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q) ||
        s.recommendation.toLowerCase().includes(q)
    ) : [...state.stocks];
    updateTable();
}

function handleSort(col) {
    if (state.sortColumn === col) {
        state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        state.sortColumn = col;
        state.sortDirection = col === 'overall_score' ? 'desc' : 'asc';
    }

    state.filteredStocks.sort((a, b) => {
        let av = a[col], bv = b[col];
        if (typeof av === 'string') { av = av.toLowerCase(); bv = bv.toLowerCase(); }
        if (av < bv) return state.sortDirection === 'asc' ? -1 : 1;
        if (av > bv) return state.sortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    updateTable();
}

function handleReset() {
    document.getElementById('searchInput').value = '';
    state.filteredStocks = [...state.stocks];
    state.sortColumn = 'overall_score';
    state.sortDirection = 'desc';
    state.filteredStocks.sort((a, b) => b.overall_score - a.overall_score);
    updateTable();
}

function getScoreClass(score) {
    if (score >= 8) return 'excellent';
    if (score >= 6.5) return 'good';
    if (score >= 4.5) return 'neutral';
    if (score >= 3) return 'poor';
    return 'bad';
}

function formatCurrency(v) {
    if (!v || isNaN(v)) return '-';
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(v);
}

function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '...' : str;
}

document.addEventListener('DOMContentLoaded', init);
