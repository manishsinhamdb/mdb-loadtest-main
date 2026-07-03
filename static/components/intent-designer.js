/**
 * Intent Designer Component
 * Allows users to select testing intent and configure parameters
 */
class IntentDesigner {
    constructor(containerId, onCalculate) {
        this.container = document.getElementById(containerId);
        this.onCalculate = onCalculate;
        this.intents = [];
        this.selectedIntent = null;
        this.config = null;
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
            <div class="intent-designer">
                <h3>Choose Your Testing Goal</h3>
                <div class="intent-grid">
                    ${this.renderIntentCards()}
                </div>

                <div id="intent-config-panel" class="intent-config-panel" style="display: none;">
                    <h3>Configure Test Parameters</h3>
                    <div class="knobs-container">
                        <div class="knob-row">
                            <label>Intensity</label>
                            <select id="intensity-select" class="neon-select">
                                <option value="light">Light (20-40% load)</option>
                                <option value="medium" selected>Medium (60-70% load)</option>
                                <option value="heavy">Heavy (80-90% load)</option>
                                <option value="extreme">Extreme (max capacity)</option>
                            </select>
                        </div>
                        <div class="knob-row">
                            <label>Duration</label>
                            <input type="number" id="duration-input" value="600" min="60" max="7200" class="neon-input">
                            <span class="unit">seconds</span>
                        </div>
                        <div class="knob-row">
                            <label>Concurrency</label>
                            <input type="range" id="concurrency-slider" min="1" max="50" value="10" class="neon-slider">
                            <span id="concurrency-value" class="value-display">10</span>
                        </div>
                    </div>

                    <div class="action-buttons">
                        <button id="calculate-btn" class="btn-primary">Calculate Configuration</button>
                        <button id="run-btn" class="btn-success" style="display: none;">Run Test</button>
                    </div>

                    <div id="config-preview" class="config-preview" style="display: none;">
                        <h4>Calculated Configuration</h4>
                        <pre id="config-json"></pre>
                        <div id="validation-warnings" class="warnings"></div>
                    </div>
                </div>
            </div>
        `;

        this.attachEventListeners();
    }

    renderIntentCards() {
        const intentDescriptions = {
            connection_stress: 'Test connection pool limits and connection handling',
            read_performance: 'Benchmark query throughput (indexed + unindexed)',
            write_throughput: 'Max out write capacity with batch inserts',
            aggregation_pipeline: 'Test complex pipelines (groupBy, unwind, etc.)',
            concurrency_contention: 'Find lock contention limits on hot documents',
            cache_pressure: 'Overflow cache to test disk I/O performance',
            mixed_production: 'Realistic blend (80% reads, 15% writes, 5% agg)',
            custom: 'Full manual control over all workloads'
        };

        const intentIcons = {
            connection_stress: '🔌',
            read_performance: '📖',
            write_throughput: '✍️',
            aggregation_pipeline: '🔄',
            concurrency_contention: '⚡',
            cache_pressure: '💾',
            mixed_production: '🏭',
            custom: '⚙️'
        };

        return Object.keys(intentDescriptions).map(intentId => `
            <div class="intent-card" data-intent="${intentId}">
                <div class="intent-icon">${intentIcons[intentId]}</div>
                <div class="intent-name">${intentId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</div>
                <div class="intent-description">${intentDescriptions[intentId]}</div>
            </div>
        `).join('');
    }

    attachEventListeners() {
        // Intent card selection
        const cards = this.container.querySelectorAll('.intent-card');
        cards.forEach(card => {
            card.addEventListener('click', () => {
                cards.forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                this.selectedIntent = card.dataset.intent;
                document.getElementById('intent-config-panel').style.display = 'block';
            });
        });

        // Concurrency slider
        const slider = document.getElementById('concurrency-slider');
        const valueDisplay = document.getElementById('concurrency-value');
        if (slider && valueDisplay) {
            slider.addEventListener('input', (e) => {
                valueDisplay.textContent = e.target.value;
            });
        }

        // Calculate button
        const calculateBtn = document.getElementById('calculate-btn');
        if (calculateBtn) {
            calculateBtn.addEventListener('click', () => this.calculateConfiguration());
        }

        // Run button
        const runBtn = document.getElementById('run-btn');
        if (runBtn) {
            runBtn.addEventListener('click', () => this.runTest());
        }
    }

    async calculateConfiguration() {
        if (!this.selectedIntent) {
            alert('Please select an intent first');
            return;
        }

        const intensity = document.getElementById('intensity-select').value;
        const duration = parseInt(document.getElementById('duration-input').value);
        const concurrency = parseInt(document.getElementById('concurrency-slider').value);

        // Get hardware info
        let clientHardware, serverHardware;
        try {
            const hwResponse = await fetch('/api/discovery/hardware');
            const hwData = await hwResponse.json();
            clientHardware = hwData;

            // For now, use default server hardware (would come from selected profile)
            serverHardware = {
                vcpus: 16,
                ram_gb: 40,
                max_connections: 3200
            };
        } catch (error) {
            console.error('Failed to get hardware:', error);
            return;
        }

        // Calculate configuration
        try {
            const response = await fetch('/api/intent/calculate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    intent_id: this.selectedIntent,
                    intensity: intensity,
                    duration_seconds: duration,
                    concurrency_level: concurrency,
                    client_hardware: clientHardware,
                    server_hardware: serverHardware,
                    allow_overrides: false
                })
            });

            if (!response.ok) {
                throw new Error('Configuration calculation failed');
            }

            this.config = await response.json();
            this.displayConfiguration();
        } catch (error) {
            console.error('Failed to calculate configuration:', error);
            alert('Failed to calculate configuration. See console for details.');
        }
    }

    displayConfiguration() {
        const configPreview = document.getElementById('config-preview');
        const configJson = document.getElementById('config-json');
        const warningsDiv = document.getElementById('validation-warnings');
        const runBtn = document.getElementById('run-btn');

        if (!configPreview || !configJson) return;

        configPreview.style.display = 'block';
        configJson.textContent = JSON.stringify(this.config, null, 2);

        // Display warnings
        if (this.config.validation && this.config.validation.warnings.length > 0) {
            warningsDiv.innerHTML = `
                <h5>⚠️ Warnings</h5>
                <ul>
                    ${this.config.validation.warnings.map(w => `<li>${w}</li>`).join('')}
                </ul>
            `;
            warningsDiv.style.display = 'block';
        } else {
            warningsDiv.style.display = 'none';
        }

        // Show run button if validation passed
        if (this.config.validation && this.config.validation.ok) {
            runBtn.style.display = 'inline-block';
        }

        // Call callback
        if (this.onCalculate) {
            this.onCalculate(this.config);
        }
    }

    async runTest() {
        if (!this.config) {
            alert('Please calculate configuration first');
            return;
        }

        if (this.onCalculate) {
            this.onCalculate(this.config, true);
        }
    }

    getConfiguration() {
        return this.config;
    }
}

// Export for use in app.js
window.IntentDesigner = IntentDesigner;
