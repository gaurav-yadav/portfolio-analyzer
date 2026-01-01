/**
 * Portfolio Analyzer Dashboard
 * Minimal, decision-oriented UI per UI_SPEC.md
 */

const state = {
    stocks: [],
    filteredStocks: [],
    activeFilter: 'all',
    sortColumn: 'overall_score',
    sortDirection: 'desc'
};

const RECOMMENDATIONS = {
    'STRONG BUY': { class: 'strong-buy', color: '#059669', order: 1 },
    'BUY': { class: 'buy', color: '#10b981', order: 2 },
    'HOLD': { class: 'hold', color: '#f59e0b', order: 3 },
    'SELL': { class: 'sell', color: '#ef4444', order: 4 },
    'STRONG SELL': { class: 'strong-sell', color: '#b91c1c', order: 5 },
    'INSUFFICIENT DATA': { class: 'insufficient', color: '#94a3b8', order: 6 }
};

function init() {
    // File upload handlers
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

    // Search
    document.getElementById('searchInput').addEventListener('input', handleSearch);

    // Filter tabs
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.addEventListener('click', () => handleFilter(tab.dataset.filter));
    });

    // Table sorting
    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => handleSort(th.dataset.sort));
    });

    // Modal
    document.getElementById('modalClose').addEventListener('click', closeModal);
    document.getElementById('stockModal').addEventListener('click', e => {
        if (e.target.id === 'stockModal') closeModal();
    });
}

function processFile(file) {
    Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: results => {
            const stocks = parseAnalysisData(results.data);
            if (stocks.length > 0) {
                state.stocks = stocks;
                state.filteredStocks = [...stocks];
                document.getElementById('uploadSection').style.display = 'none';
                document.getElementById('dashboard').style.display = 'block';
                updateDashboard();
            } else {
                alert('No valid stock data found.');
            }
        },
        error: err => alert('Error parsing CSV: ' + err.message)
    });
}

function parseAnalysisData(rows) {
    const stocks = [];

    for (const row of rows) {
        const firstCol = Object.values(row)[0] || '';
        // Skip metadata rows
        if (firstCol.includes('===') || firstCol.includes('PORTFOLIO') ||
            firstCol.includes('Total Stocks') || firstCol.includes('Health') ||
            firstCol.includes('RECOMMENDATION') || firstCol.includes('SIGNAL') ||
            firstCol.includes('HIGH:') || firstCol.includes('MEDIUM:') ||
            firstCol.includes('LOW:') || firstCol.includes('Gated') ||
            firstCol.includes('Top Performer') || firstCol.includes('Needs Attention')) {
            continue;
        }

        const stock = parseStockRow(row);
        if (stock) stocks.push(stock);
    }

    return stocks;
}

function parseStockRow(row) {
    const get = (...keys) => {
        for (const k of keys) {
            const val = row[k] || row[k.toLowerCase()] || row[k.toUpperCase()];
            if (val !== undefined && val !== '') return val;
        }
        return null;
    };

    const isMissing = v => {
        if (v === null || v === undefined) return true;
        const s = String(v).trim().toUpperCase();
        return !s || s === 'N/A' || s === 'NA' || s === '-' || s === 'NULL';
    };

    const parseNum = v => {
        if (isMissing(v)) return null;
        const cleaned = String(v).replace(/[₹,%]/g, '').replace(/,/g, '').trim();
        const num = Number(cleaned);
        return Number.isFinite(num) ? num : null;
    };

    const symbol = get('symbol', 'Symbol', 'SYMBOL');
    if (!symbol || symbol.includes('===') || symbol.includes('Total')) return null;

    return {
        symbol,
        name: get('name', 'Name') || symbol,
        quantity: parseNum(get('quantity', 'qty')),
        avg_price: parseNum(get('avg_price', 'Avg. cost')),
        current_price: parseNum(get('current_price', 'LTP', 'cmp')),
        pnl_pct: parseNum(get('pnl_pct', 'pnl_percent', 'P&L %')),
        rsi: parseNum(get('rsi')),
        rsi_score: parseNum(get('rsi_score')),
        macd_score: parseNum(get('macd_score')),
        trend_score: parseNum(get('trend_score')),
        bollinger_score: parseNum(get('bollinger_score')),
        adx_score: parseNum(get('adx_score')),
        volume_score: parseNum(get('volume_score')),
        technical_score: parseNum(get('technical_score')),
        fundamental_score: parseNum(get('fundamental_score')),
        news_sentiment_score: parseNum(get('news_sentiment_score', 'news_score')),
        legal_corporate_score: parseNum(get('legal_corporate_score', 'legal_score')),
        overall_score: parseNum(get('overall_score', 'score')),
        recommendation: get('recommendation') || 'HOLD',
        confidence: get('confidence') || 'MEDIUM',
        coverage: get('coverage'),
        coverage_pct: parseNum(get('coverage_pct')),
        gate_flags: get('gate_flags') || '',
        red_flags: get('red_flags') || '',
        summary: get('summary') || ''
    };
}

function updateDashboard() {
    updateKPI();
    updateDistribution();
    applySort();
    updateTable();
}

function updateKPI() {
    const stocks = state.stocks;
    const avgScore = stocks.length ? stocks.reduce((s, st) => s + (st.overall_score || 0), 0) / stocks.length : 0;
    const totalValue = stocks.reduce((s, st) => s + ((st.quantity || 0) * (st.current_price || 0)), 0);

    document.getElementById('totalStocks').textContent = stocks.length;
    document.getElementById('healthScore').textContent = avgScore.toFixed(1);
    document.getElementById('healthRating').textContent = getHealthRating(avgScore);
    document.getElementById('healthRating').className = `kpi-value rating-${getScoreClass(avgScore)}`;
    document.getElementById('totalValue').textContent = formatCurrency(totalValue);
}

function getHealthRating(score) {
    if (score >= 7.5) return 'Excellent';
    if (score >= 6.0) return 'Good';
    if (score >= 5.0) return 'Fair';
    if (score >= 4.0) return 'Needs Attention';
    return 'At Risk';
}

function updateDistribution() {
    const counts = {};
    Object.keys(RECOMMENDATIONS).forEach(r => counts[r] = 0);
    state.stocks.forEach(s => counts[s.recommendation] = (counts[s.recommendation] || 0) + 1);

    const total = state.stocks.length || 1;

    // Stacked bar
    const barHtml = Object.entries(RECOMMENDATIONS)
        .filter(([rec]) => counts[rec] > 0)
        .map(([rec, cfg]) => {
            const pct = (counts[rec] / total * 100);
            return `<div class="bar-segment bar-${cfg.class}" style="width:${pct}%" title="${rec}: ${counts[rec]}"></div>`;
        }).join('');

    document.getElementById('stackedBar').innerHTML = barHtml;

    // Legend
    const legendHtml = Object.entries(RECOMMENDATIONS)
        .map(([rec, cfg]) => {
            const count = counts[rec];
            const pct = (count / total * 100).toFixed(0);
            return `<span class="legend-item"><span class="legend-dot legend-${cfg.class}"></span>${rec.replace('INSUFFICIENT DATA', 'N/A')} ${count} (${pct}%)</span>`;
        }).join('');

    document.getElementById('distributionLegend').innerHTML = legendHtml;
}

function handleFilter(filter) {
    state.activeFilter = filter;

    // Update active tab
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.filter === filter);
    });

    applyFilters();
}

function handleSearch(e) {
    applyFilters();
}

function applyFilters() {
    const query = document.getElementById('searchInput').value.toLowerCase();
    const filter = state.activeFilter;

    state.filteredStocks = state.stocks.filter(s => {
        // Search filter
        if (query && !s.symbol.toLowerCase().includes(query) && !s.name.toLowerCase().includes(query)) {
            return false;
        }

        // Tab filter
        switch (filter) {
            case 'buy':
                return s.recommendation === 'BUY' || s.recommendation === 'STRONG BUY';
            case 'hold':
                return s.recommendation === 'HOLD';
            case 'sell':
                return s.recommendation === 'SELL' || s.recommendation === 'STRONG SELL';
            case 'red-flags':
                return s.red_flags && s.red_flags.length > 0;
            default:
                return true;
        }
    });

    applySort();
    updateTable();
}

function handleSort(col) {
    if (state.sortColumn === col) {
        state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        state.sortColumn = col;
        state.sortDirection = col === 'overall_score' || col === 'pnl_pct' ? 'desc' : 'asc';
    }

    applySort();
    updateTable();
}

function applySort() {
    const col = state.sortColumn;
    const dir = state.sortDirection;

    state.filteredStocks.sort((a, b) => {
        let av = a[col], bv = b[col];

        // Handle recommendation by severity order
        if (col === 'recommendation') {
            av = RECOMMENDATIONS[av]?.order || 99;
            bv = RECOMMENDATIONS[bv]?.order || 99;
        }

        // Handle nulls
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;

        if (typeof av === 'string') {
            av = av.toLowerCase();
            bv = bv.toLowerCase();
        }

        if (av < bv) return dir === 'asc' ? -1 : 1;
        if (av > bv) return dir === 'asc' ? 1 : -1;
        return 0;
    });
}

function updateTable() {
    const stocks = state.filteredStocks;
    const tbody = document.getElementById('stocksTableBody');

    if (stocks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No stocks found</td></tr>';
        return;
    }

    tbody.innerHTML = stocks.map(s => {
        const pnlClass = s.pnl_pct == null ? '' : (s.pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative');
        const pnlText = s.pnl_pct == null ? '-' : `${s.pnl_pct >= 0 ? '+' : ''}${s.pnl_pct.toFixed(1)}%`;
        const flagCount = s.red_flags ? s.red_flags.split(',').length : 0;
        const recClass = RECOMMENDATIONS[s.recommendation]?.class || 'hold';

        return `
            <tr onclick="showStockDetails('${s.symbol}')" class="${s.red_flags ? 'has-red-flag' : ''}">
                <td class="symbol-cell">
                    <strong>${s.symbol}</strong>
                    <span class="stock-name">${truncate(s.name, 20)}</span>
                </td>
                <td><span class="reco-badge reco-${recClass}">${s.recommendation}</span></td>
                <td class="num"><span class="score-pill score-${getScoreClass(s.overall_score)}">${s.overall_score?.toFixed(1) || '-'}</span></td>
                <td class="num ${pnlClass}">${pnlText}</td>
                <td class="flags-cell">${flagCount > 0 ? `<span class="flag-badge">${flagCount}</span>` : '<span class="no-flags">-</span>'}</td>
                <td class="summary-cell" title="${s.summary}">${truncate(s.summary, 60)}</td>
            </tr>
        `;
    }).join('');
}

function showStockDetails(symbol) {
    const s = state.stocks.find(st => st.symbol === symbol);
    if (!s) return;

    document.getElementById('modalTitle').textContent = `${s.symbol} - ${s.name}`;

    const recClass = RECOMMENDATIONS[s.recommendation]?.class || 'hold';
    const pnlClass = s.pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative';
    const pnlText = s.pnl_pct != null ? `${s.pnl_pct >= 0 ? '+' : ''}${s.pnl_pct.toFixed(1)}%` : '-';

    const confClass = s.confidence === 'HIGH' ? 'conf-high' : s.confidence === 'LOW' ? 'conf-low' : 'conf-medium';

    document.getElementById('modalMeta').innerHTML = `
        <span class="reco-badge reco-${recClass}">${s.recommendation}</span>
        <span class="meta-score">${s.overall_score?.toFixed(1) || '-'}/10</span>
        <span class="meta-confidence ${confClass}">${s.confidence || 'N/A'}</span>
        <span class="meta-pnl ${pnlClass}">${pnlText}</span>
    `;

    // Single scrollable content
    document.getElementById('modalBody').innerHTML = `
        <div class="modal-section">
            <p class="summary-text">${s.summary || 'No summary available.'}</p>
            ${s.gate_flags ? `<div class="gate-notice">Gated: ${s.gate_flags}</div>` : ''}
        </div>

        <div class="modal-section">
            <h4>Scores</h4>
            ${s.coverage && s.coverage !== 'TFNL' ? `<div class="coverage-notice">Coverage: ${s.coverage} (${s.coverage_pct || 0}%)</div>` : ''}
            ${renderScoreBar('Technical', s.technical_score)}
            ${renderScoreBar('Fundamental', s.fundamental_score)}
            ${renderScoreBar('News', s.news_sentiment_score)}
            ${renderScoreBar('Legal', s.legal_corporate_score)}
        </div>

        ${s.red_flags ? `
        <div class="modal-section red-flags">
            <h4>Red Flags</h4>
            <p>${s.red_flags}</p>
        </div>
        ` : ''}

        <div class="modal-section">
            <h4>Holdings</h4>
            <div class="holdings-grid">
                <div class="holding-item"><span class="h-label">Quantity</span><span class="h-value">${s.quantity || '-'}</span></div>
                <div class="holding-item"><span class="h-label">Avg Price</span><span class="h-value">${formatCurrency(s.avg_price)}</span></div>
                <div class="holding-item"><span class="h-label">Current Price</span><span class="h-value">${formatCurrency(s.current_price)}</span></div>
                <div class="holding-item"><span class="h-label">P&L %</span><span class="h-value ${s.pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative'}">${s.pnl_pct != null ? `${s.pnl_pct >= 0 ? '+' : ''}${s.pnl_pct.toFixed(2)}%` : '-'}</span></div>
            </div>
        </div>
    `;

    document.getElementById('stockModal').classList.add('active');
}

function renderScoreBar(label, score) {
    const width = score != null ? score * 10 : 0;
    const value = score != null ? score.toFixed(1) : 'N/A';
    const cls = getScoreClass(score);
    const missing = score == null ? ' missing' : '';

    return `
        <div class="score-row${missing}">
            <span class="score-label">${label}</span>
            <div class="score-track"><div class="score-fill score-${cls}" style="width:${width}%"></div></div>
            <span class="score-value">${value}</span>
        </div>
    `;
}

function closeModal() {
    document.getElementById('stockModal').classList.remove('active');
    state.currentStock = null;
}

function getScoreClass(score) {
    if (score == null) return 'neutral';
    if (score >= 8) return 'excellent';
    if (score >= 6.5) return 'good';
    if (score >= 4.5) return 'neutral';
    if (score >= 3) return 'poor';
    return 'bad';
}

function formatCurrency(v) {
    if (v == null || isNaN(v)) return '-';
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(v);
}

function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '...' : str;
}

document.addEventListener('DOMContentLoaded', init);
