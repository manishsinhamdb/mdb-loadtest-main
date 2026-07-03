/**
 * Intent Designer V2 - Complete Implementation
 *
 * Features:
 * - 8 intent cards with visual selection
 * - Intensity/duration/concurrency knobs
 * - PRIMARY and SECONDARY metric impact visualization
 * - Real-time configuration calculation
 * - Metric-driven mode toggle
 */
class IntentDesignerV2 {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.selectedIntent = null;
        this.config = null;
        this.mode = 'intent'; // 'intent' or 'metric-driven'
        this.selectedMetrics = [];
    }

    async init() {
        await this.loadIntents();
        this.render();
    }

    async loadIntents() {
        try {
            const response = await fetch('/api/intent/types');
            const data = await response.json();
            this.intents = data.intents;
        } catch (error) {
            console.error('Failed to load intents:', error);
            this.intents = [];
        }
    }

    render() {
        if (!this.container) return;

        this.container.innerHTML = `
            <div class="intent-designer-v2">
                <!-- Mode Toggle -->
                <div class="mode-toggle">
                    <button class="mode-btn ${this.mode === 'intent' ? 'active' : ''}"
                            onclick="window.intentDesigner.switchMode('intent')">
                        🎯 Guided Intent Mode
                    </button>
                    <button class="mode-btn ${this.mode === 'metric-driven' ? 'active' : ''}"
                            onclick="window.intentDesigner.switchMode('metric-driven')">
                        📊 Metric-Driven Mode
                    </button>
                </div>

                ${this.mode === 'intent' ? this.renderIntentMode() : this.renderMetricMode()}
            </div>
        `;
    }

    renderIntentMode() {
        return `
            <div class="intent-mode">
                <h2>Choose Your Testing Goal</h2>
                <p class="subtitle">Select an intent below. System will calculate optimal configuration based on your hardware.</p>

                <div class="intent-grid">
                    ${this.renderIntentCards()}
                </div>

                ${this.selectedIntent ? this.renderConfigPanel() : ''}
            </div>
        `;
    }

    renderIntentCards() {
        const icons = {
            connection_stress: '🔌',
            read_performance: '📖',
            write_throughput: '✍️',
            aggregation_pipeline: '🔄',
            concurrency_contention: '⚡',
            cache_pressure: '💾',
            mixed_production: '🎯',
            custom: '⚙️'
        };

        const descriptions = {
            connection_stress: 'Test connection pool limits and concurrent connection handling',
            read_performance: 'Benchmark query throughput (indexed + unindexed reads)',
            write_throughput: 'Max out write capacity with batch inserts',
            aggregation_pipeline: 'Test complex pipelines (groupBy, unwind, sorting)',
            concurrency_contention: 'Find lock contention limits on hot documents',
            cache_pressure: 'Overflow WiredTiger cache to test disk I/O fallback',
            mixed_production: 'Realistic blend: 80% reads, 15% writes, 5% aggregations',
            custom: 'Full manual control over all workload parameters'
        };

        return this.intents.map(intent => `
            <div class="intent-card ${this.selectedIntent === intent.id ? 'selected' : ''}"
                 onclick="window.intentDesigner.selectIntent('${intent.id}')">
                <div class="intent-icon">${icons[intent.id] || '⚙️'}</div>
                <div class="intent-name">${intent.name}</div>
                <div class="intent-description">${descriptions[intent.id] || intent.description}</div>

                <!-- Metric Impact Badges -->
                <div class="metric-impact">
                    <div class="impact-badge primary"
                         title="${intent.primary_metrics?.slice(0, 3).join(', ') || 'No metrics'}">
                        🎯 ${intent.primary_metrics?.length || 0} Primary
                    </div>
                    <div class="impact-badge secondary"
                         title="Secondary metrics affected">
                        ↗️ ${intent.secondary_metrics?.length || 0} Secondary
                    </div>
                </div>
            </div>
        `).join('');
    }

    renderConfigPanel() {
        const intent = this.intents.find(i => i.id === this.selectedIntent);
        if (!intent) return '';

        return `
            <div class="config-panel">
                <h3>Configure: ${intent.name}</h3>

                <!-- Knobs Section -->
                <div class="knobs-section">
                    <div class="knob-group">
                        <label class="knob-label">
                            <span class="label-text">Intensity</span>
                            <span class="label-help" title="Controls thread count, concurrency, and operation rates">ℹ️</span>
                        </label>
                        <select id="intensity-knob" class="knob-select" onchange="window.intentDesigner.updatePreview()">
                            <option value="light">Light (20-40% load)</option>
                            <option value="medium" selected>Medium (60-70% load)</option>
                            <option value="heavy">Heavy (80-90% load)</option>
                            <option value="extreme">Extreme (max capacity)</option>
                        </select>
                    </div>

                    <div class="knob-group">
                        <label class="knob-label">
                            <span class="label-text">Duration</span>
                            <span class="label-help" title="Test duration in seconds">ℹ️</span>
                        </label>
                        <input type="number" id="duration-knob" value="600" min="60" max="7200"
                               class="knob-input" onchange="window.intentDesigner.updatePreview()">
                        <span class="knob-unit">seconds</span>
                    </div>

                    <div class="knob-group">
                        <label class="knob-label">
                            <span class="label-text">Concurrency</span>
                            <span class="label-help" title="Concurrent operations multiplier">ℹ️</span>
                        </label>
                        <input type="range" id="concurrency-knob" min="1" max="50" value="10"
                               class="knob-slider" oninput="window.intentDesigner.updateConcurrencyLabel(this.value)"
                               onchange="window.intentDesigner.updatePreview()">
                        <span id="concurrency-value" class="knob-value">10</span>
                    </div>
                </div>

                <!-- Metric Impact Visualization -->
                <div class="impact-visualization">
                    <div class="impact-section">
                        <h4>🎯 Primary Metrics (Will Spike)</h4>
                        <div class="metric-pills">
                            ${(intent.primary_metrics || []).slice(0, 10).map(m =>
                                `<span class="metric-pill primary" title="${this.getMetricDescription(m)}">${m}</span>`
                            ).join('')}
                            ${(intent.primary_metrics?.length || 0) > 10 ?
                                `<span class="metric-pill more">+${intent.primary_metrics.length - 10} more</span>` : ''}
                        </div>
                    </div>

                    ${intent.secondary_metrics && intent.secondary_metrics.length > 0 ? `
                    <div class="impact-section">
                        <h4>↗️ Secondary Metrics (Will Be Affected)</h4>
                        <div class="metric-pills">
                            ${intent.secondary_metrics.slice(0, 8).map(m =>
                                `<span class="metric-pill secondary" title="${this.getMetricDescription(m)}">${m}</span>`
                            ).join('')}
                            ${intent.secondary_metrics.length > 8 ?
                                `<span class="metric-pill more">+${intent.secondary_metrics.length - 8} more</span>` : ''}
                        </div>
                    </div>
                    ` : ''}
                </div>

                <!-- Action Buttons -->
                <div class="config-actions">
                    <button class="btn-calculate" onclick="window.intentDesigner.calculateConfig()">
                        Calculate Configuration
                    </button>
                </div>

                <!-- Config Preview (appears after calculation) -->
                <div id="config-preview-area"></div>
            </div>
        `;
    }

    renderMetricMode() {
        return `
            <div class="metric-mode">
                <h2>Metric-Driven Test Generation</h2>
                <p class="subtitle">Select metrics you want to spike. System will generate optimal test configuration.</p>

                <div class="metric-selector">
                    <div class="metric-search">
                        <input type="text" id="metric-search" placeholder="Search 130+ metrics..."
                               onkeyup="window.intentDesigner.filterMetrics(this.value)">
                    </div>

                    <div class="metric-categories">
                        ${this.renderMetricCategories()}
                    </div>

                    <div class="selected-metrics-panel">
                        <h3>Selected Metrics (${this.selectedMetrics.length})</h3>
                        <div id="selected-metrics-list">
                            ${this.selectedMetrics.length === 0 ?
                                '<p class="empty-state">No metrics selected yet</p>' :
                                this.selectedMetrics.map(m =>
                                    `<span class="metric-pill selected">${m}
                                     <button onclick="window.intentDesigner.deselectMetric('${m}')">×</button>
                                     </span>`
                                ).join('')}
                        </div>
                        <button class="btn-generate"
                                ${this.selectedMetrics.length === 0 ? 'disabled' : ''}
                                onclick="window.intentDesigner.generateFromMetrics()">
                            Generate Test Configuration
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    renderMetricCategories() {
        const categories = [
            { name: 'Connections & Network', count: 15 },
            { name: 'Operations (Opcounters)', count: 12 },
            { name: 'Memory & Cache', count: 18 },
            { name: 'Query Execution', count: 22 },
            { name: 'Replication', count: 14 },
            { name: 'Storage & I/O', count: 16 },
            { name: 'Network Throughput', count: 8 },
            { name: 'Cursors & Sessions', count: 10 },
            { name: 'Index Performance', count: 9 },
            { name: 'Locks & Contention', count: 6 }
        ];

        return categories.map(cat => `
            <div class="metric-category">
                <h4>${cat.name} <span class="count">(${cat.count})</span></h4>
                <div class="metric-checkboxes" data-category="${cat.name}">
                    <!-- Loaded dynamically -->
                </div>
            </div>
        `).join('');
    }

    getMetricDescription(metricName) {
        // Abbreviated descriptions for tooltips
        const descriptions = {
            'OPCOUNTER_QUERY': 'Number of query operations per second',
            'OPCOUNTER_INSERT': 'Number of insert operations per second',
            'OPCOUNTER_UPDATE': 'Number of update operations per second',
            'OPCOUNTER_DELETE': 'Number of delete operations per second',
            'OPCOUNTER_GETMORE': 'Number of getmore operations (cursor iteration)',
            'OPCOUNTER_COMMAND': 'Number of command operations per second',
            'CONNECTIONS': 'Current active connections to MongoDB',
            'CONNECTIONS_AVAILABLE': 'Available connection slots remaining',
            'CACHE_BYTES_READ': 'Bytes read from WiredTiger cache',
            'CACHE_BYTES_WRITTEN': 'Bytes written to WiredTiger cache',
            'CACHE_DIRTY_BYTES': 'Dirty bytes in cache (pending write to disk)',
            'TICKETS_AVAILABLE_READS': 'Available read tickets (concurrency slots)',
            'TICKETS_AVAILABLE_WRITES': 'Available write tickets (concurrency slots)',
            'QUERY_EXECUTOR_SCANNED': 'Documents scanned by query executor',
            'QUERY_EXECUTOR_SCANNED_OBJECTS': 'Objects examined by queries',
            'QUERY_TARGETING_SCANNED_PER_RETURNED': 'Scan efficiency ratio'
        };
        return descriptions[metricName] || 'Impact description available in detail view';
    }

    // ===== EVENT HANDLERS =====

    switchMode(mode) {
        this.mode = mode;
        this.render();

        if (mode === 'metric-driven') {
            this.loadMetricCatalog();
        }
    }

    selectIntent(intentId) {
        this.selectedIntent = intentId;
        this.render();
    }

    updateConcurrencyLabel(value) {
        document.getElementById('concurrency-value').textContent = value;
    }

    updatePreview() {
        // Real-time preview as knobs adjust
        const intensity = document.getElementById('intensity-knob')?.value || 'medium';
        const duration = document.getElementById('duration-knob')?.value || 600;
        const concurrency = document.getElementById('concurrency-knob')?.value || 10;

        console.log(`Preview update: intensity=${intensity}, duration=${duration}s, concurrency=${concurrency}x`);
        // Could show real-time estimated load here
    }

    async calculateConfig() {
        const intensity = document.getElementById('intensity-knob').value;
        const duration = parseInt(document.getElementById('duration-knob').value);
        const concurrency = parseInt(document.getElementById('concurrency-knob').value);

        const previewArea = document.getElementById('config-preview-area');
        previewArea.innerHTML = '<p class="loading">Calculating optimal configuration...</p>';

        try {
            const response = await fetch('/api/intent/calculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    intent_id: this.selectedIntent,
                    intensity,
                    duration,
                    concurrency_multiplier: concurrency
                })
            });

            if (!response.ok) {
                throw new Error(`Calculation failed: ${response.statusText}`);
            }

            const result = await response.json();
            this.displayCalculatedConfig(result);

        } catch (error) {
            previewArea.innerHTML = `<p class="error">Calculation failed: ${error.message}</p>`;
            console.error('Config calculation error:', error);
        }
    }

    displayCalculatedConfig(result) {
        const previewArea = document.getElementById('config-preview-area');

        previewArea.innerHTML = `
            <div class="config-result">
                <h3>Calculated Configuration</h3>

                <div class="config-summary">
                    <div class="summary-row">
                        <span class="label">Estimated Load:</span>
                        <span class="value">${result.estimated_load_pct}% capacity</span>
                    </div>
                    <div class="summary-row">
                        <span class="label">Thread Count:</span>
                        <span class="value">${result.thread_count} threads</span>
                    </div>
                    <div class="summary-row">
                        <span class="label">Operations/sec:</span>
                        <span class="value">~${result.estimated_ops_per_sec}</span>
                    </div>
                    <div class="summary-row">
                        <span class="label">Total Duration:</span>
                        <span class="value">${result.duration}s</span>
                    </div>
                </div>

                ${result.warnings && result.warnings.length > 0 ? `
                <div class="warnings-section">
                    <h4>⚠️ Warnings</h4>
                    <ul>
                        ${result.warnings.map(w => `<li>${w}</li>`).join('')}
                    </ul>
                </div>
                ` : ''}

                <div class="config-actions">
                    <button class="btn-primary" onclick="window.intentDesigner.applyConfig()">
                        Apply & Go to Run Tab
                    </button>
                    <button class="btn-secondary" onclick="window.intentDesigner.exportConfig()">
                        Export Config JSON
                    </button>
                </div>
            </div>
        `;

        // Store calculated config
        this.config = result;
    }

    applyConfig() {
        if (!this.config) {
            alert('No configuration calculated yet');
            return;
        }

        // Store config globally for main app to pick up
        window.intentConfig = this.config;

        // Switch to Run tab (Tab 3)
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));

        const runTab = document.querySelector('[data-tab="workloads"]');
        const runPanel = document.querySelector('[data-panel="workloads"]');

        if (runTab && runPanel) {
            runTab.classList.add('active');
            runPanel.classList.add('active');
        }

        alert('Configuration applied! Review in Advanced Config tab.');
    }

    exportConfig() {
        if (!this.config) {
            alert('No configuration to export');
            return;
        }

        const blob = new Blob([JSON.stringify(this.config, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `loadtest-config-${this.selectedIntent}-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    // ===== METRIC-DRIVEN MODE =====

    async loadMetricCatalog() {
        try {
            const response = await fetch('/api/metrics/catalog');
            const data = await response.json();
            this.metricCatalog = data.metrics;

            // Populate checkboxes
            this.populateMetricCheckboxes();
        } catch (error) {
            console.error('Failed to load metric catalog:', error);
            this.metricCatalog = [];
        }
    }

    populateMetricCheckboxes() {
        // Group metrics by category
        const grouped = {};
        (this.metricCatalog || []).forEach(metric => {
            if (!grouped[metric.category_name]) {
                grouped[metric.category_name] = [];
            }
            grouped[metric.category_name].push(metric);
        });

        // Populate each category
        Object.keys(grouped).forEach(categoryName => {
            const container = document.querySelector(`[data-category="${categoryName}"] .metric-checkboxes`);
            if (!container) return;

            container.innerHTML = grouped[categoryName].map(metric => `
                <label class="metric-checkbox">
                    <input type="checkbox" value="${metric.metric_name}"
                           onchange="window.intentDesigner.toggleMetric('${metric.metric_name}', this.checked)">
                    <span title="${metric.description}">${metric.metric_name}</span>
                </label>
            `).join('');
        });
    }

    filterMetrics(query) {
        const checkboxes = document.querySelectorAll('.metric-checkbox');
        const lowerQuery = query.toLowerCase();

        checkboxes.forEach(checkbox => {
            const metricName = checkbox.querySelector('span').textContent.toLowerCase();
            const visible = metricName.includes(lowerQuery);
            checkbox.style.display = visible ? 'flex' : 'none';
        });
    }

    toggleMetric(metricName, checked) {
        if (checked) {
            if (!this.selectedMetrics.includes(metricName)) {
                this.selectedMetrics.push(metricName);
            }
        } else {
            this.selectedMetrics = this.selectedMetrics.filter(m => m !== metricName);
        }

        this.updateSelectedMetricsList();
    }

    deselectMetric(metricName) {
        this.selectedMetrics = this.selectedMetrics.filter(m => m !== metricName);

        // Uncheck checkbox
        const checkbox = document.querySelector(`input[value="${metricName}"]`);
        if (checkbox) checkbox.checked = false;

        this.updateSelectedMetricsList();
    }

    updateSelectedMetricsList() {
        const listContainer = document.getElementById('selected-metrics-list');
        const generateBtn = document.querySelector('.btn-generate');

        if (this.selectedMetrics.length === 0) {
            listContainer.innerHTML = '<p class="empty-state">No metrics selected yet</p>';
            generateBtn.disabled = true;
        } else {
            listContainer.innerHTML = this.selectedMetrics.map(m =>
                `<span class="metric-pill selected">${m}
                 <button onclick="window.intentDesigner.deselectMetric('${m}')">×</button>
                 </span>`
            ).join('');
            generateBtn.disabled = false;
        }
    }

    async generateFromMetrics() {
        if (this.selectedMetrics.length === 0) {
            alert('Please select at least one metric');
            return;
        }

        const listContainer = document.getElementById('selected-metrics-list');
        listContainer.innerHTML = '<p class="loading">Generating test configuration...</p>';

        try {
            const response = await fetch('/api/metrics/generate-test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    metrics: this.selectedMetrics
                })
            });

            if (!response.ok) {
                throw new Error(`Generation failed: ${response.statusText}`);
            }

            const result = await response.json();
            this.displayGeneratedConfig(result);

        } catch (error) {
            listContainer.innerHTML = `<p class="error">Generation failed: ${error.message}</p>`;
            console.error('Metric-driven generation error:', error);
        }
    }

    displayGeneratedConfig(result) {
        // Similar to displayCalculatedConfig but for metric-driven mode
        alert(`Generated configuration for ${this.selectedMetrics.length} metrics!\n\nWorkloads: ${result.workloads.join(', ')}`);
        this.config = result;
    }
}

// Export as global
window.IntentDesignerV2 = IntentDesignerV2;
