/**
 * Connection Manager Component
 *
 * Handles connection profile CRUD operations, profile selection,
 * and connection testing with auto-discovery.
 */

class ConnectionManager {
    constructor(apiClient) {
        this.api = apiClient;
        this.profiles = [];
        this.selectedProfile = null;
        this.isAddingNew = false;
    }

    /**
     * Load all profiles from API
     */
    async loadProfiles() {
        try {
            const response = await this.api.get('/api/connections');
            this.profiles = response.data || [];
            return this.profiles;
        } catch (error) {
            console.error('Failed to load profiles:', error);
            throw error;
        }
    }

    /**
     * Create a new profile
     */
    async createProfile(data) {
        try {
            const response = await this.api.post('/api/connections', data);
            const newProfile = response.data;
            this.profiles.push(newProfile);
            return newProfile;
        } catch (error) {
            console.error('Failed to create profile:', error);
            throw error;
        }
    }

    /**
     * Update an existing profile
     */
    async updateProfile(profileId, data) {
        try {
            const response = await this.api.put(`/api/connections/${profileId}`, data);
            const updated = response.data;

            // Update in local array
            const index = this.profiles.findIndex(p => p.id === profileId);
            if (index !== -1) {
                this.profiles[index] = updated;
            }

            return updated;
        } catch (error) {
            console.error('Failed to update profile:', error);
            throw error;
        }
    }

    /**
     * Delete a profile
     */
    async deleteProfile(profileId) {
        try {
            await this.api.delete(`/api/connections/${profileId}`);
            this.profiles = this.profiles.filter(p => p.id !== profileId);
            if (this.selectedProfile && this.selectedProfile.id === profileId) {
                this.selectedProfile = null;
            }
        } catch (error) {
            console.error('Failed to delete profile:', error);
            throw error;
        }
    }

    /**
     * Test connection and run auto-discovery
     */
    async testConnection(profileId) {
        try {
            const response = await this.api.post(`/api/connections/${profileId}/test`);
            const result = response.data;

            // Update profile in local array
            const index = this.profiles.findIndex(p => p.id === profileId);
            if (index !== -1 && result.profile) {
                this.profiles[index] = result.profile;
            }

            return result;
        } catch (error) {
            console.error('Failed to test connection:', error);
            throw error;
        }
    }

    /**
     * Set Atlas API credentials
     */
    async setAtlasCredentials(profileId, credentials) {
        try {
            const response = await this.api.post(`/api/connections/${profileId}/atlas`, credentials);
            const updated = response.data;

            const index = this.profiles.findIndex(p => p.id === profileId);
            if (index !== -1) {
                this.profiles[index] = updated;
            }

            return updated;
        } catch (error) {
            console.error('Failed to set Atlas credentials:', error);
            throw error;
        }
    }

    /**
     * Render profile selector UI
     */
    renderSelector(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        let html = '<div class="profile-selector">';

        if (this.profiles.length === 0) {
            html += '<p class="muted">No connection profiles yet. Add one below.</p>';
        } else {
            html += '<div class="profile-list">';
            this.profiles.forEach(profile => {
                const isSelected = this.selectedProfile && this.selectedProfile.id === profile.id;
                const testIcon = profile.last_test_success === true ? '✓' :
                               profile.last_test_success === false ? '✗' : '?';
                const testClass = profile.last_test_success === true ? 'ok' :
                                 profile.last_test_success === false ? 'fail' : 'warn';

                html += `
                    <div class="profile-item ${isSelected ? 'selected' : ''}" data-profile-id="${profile.id}">
                        <div class="profile-radio">
                            <input type="radio" name="profile" value="${profile.id}"
                                   ${isSelected ? 'checked' : ''}
                                   onchange="window.connManager.selectProfile(${profile.id})">
                        </div>
                        <div class="profile-info">
                            <div class="profile-name">${this.escapeHtml(profile.name)}</div>
                            <div class="profile-meta">
                                <span class="pill ${testClass}">${testIcon}</span>
                                <code>${this.escapeHtml(profile.redacted_uri || '***')}</code>
                                <span class="muted">→ ${this.escapeHtml(profile.database_name)}</span>
                            </div>
                            ${profile.server_version ? `
                                <div class="profile-server">
                                    ${profile.server_version} | ${profile.server_topology}
                                    ${profile.server_cluster_tier ? ` | ${profile.server_cluster_tier}` : ''}
                                </div>
                            ` : ''}
                        </div>
                        <div class="profile-actions">
                            <button class="secondary small" onclick="window.connManager.editProfile(${profile.id})">Edit</button>
                            <button class="secondary small" onclick="window.connManager.deletePrompt(${profile.id})">Delete</button>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        }

        html += `
            <div class="btnrow" style="margin-top: 16px;">
                <button class="secondary" onclick="window.connManager.showAddForm()">
                    + Add New Connection Profile
                </button>
                ${this.selectedProfile ? `
                    <button onclick="window.connManager.testSelectedProfile()">
                        Test Connection
                    </button>
                ` : ''}
            </div>
        `;

        html += '</div>';
        container.innerHTML = html;
    }

    /**
     * Render add/edit form
     */
    renderForm(containerId, profile = null) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const isEdit = profile !== null;
        const title = isEdit ? 'Edit Connection Profile' : 'Add New Connection Profile';

        let html = `
            <div class="connection-form">
                <h3>${title}</h3>
                <form id="profile-form" onsubmit="return window.connManager.submitForm(event, ${isEdit ? profile.id : 'null'})">
                    <label>Profile Name</label>
                    <input type="text" name="name" value="${profile ? this.escapeHtml(profile.name) : ''}"
                           placeholder="e.g., Production M40 Cluster" required />

                    ${!isEdit ? `
                    <label>Connection URI</label>
                    <input type="password" name="uri" placeholder="mongodb://user:pass@host:27017/?authSource=admin" required />
                    <div class="btnrow">
                        <button type="button" class="secondary small" onclick="window.connManager.toggleUriVisibility()">Show</button>
                    </div>
                    ` : `
                    <label>Connection URI (leave blank to keep current)</label>
                    <input type="password" name="uri" placeholder="Enter new URI or leave blank" />
                    <div class="btnrow">
                        <button type="button" class="secondary small" onclick="window.connManager.toggleUriVisibility()">Show</button>
                    </div>
                    `}

                    <label>Database Name</label>
                    <input type="text" name="database_name" value="${profile ? this.escapeHtml(profile.database_name) : 'loadtest'}" required />

                    <label>Auth Source (optional)</label>
                    <input type="text" name="auth_source" value="${profile && profile.auth_source ? this.escapeHtml(profile.auth_source) : ''}"
                           placeholder="admin" />

                    <div class="btnrow">
                        <button type="submit">${isEdit ? 'Update' : 'Create'} Profile</button>
                        <button type="button" class="secondary" onclick="window.connManager.cancelForm()">Cancel</button>
                    </div>
                </form>
            </div>
        `;

        container.innerHTML = html;
        container.style.display = 'block';
    }

    /**
     * Render auto-discovery results
     */
    renderDiscoveryResults(containerId, results) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const conn = results.connection;
        const perm = results.permission;
        const skew = results.clock_skew;
        const profile = results.profile;

        let html = '';

        if (conn.ok) {
            html += `
                <div class="discovery-results">
                    <div class="result-section success">
                        <h3>✓ CONNECTION SUCCESSFUL</h3>
                    </div>

                    <div class="result-section">
                        <h4>CLIENT MACHINE (Driver Host)</h4>
                        <div class="result-grid">
                            <div>CPU Cores: <b>${profile.client_cpu_cores || 'detecting...'}</b></div>
                            <div>RAM: <b>${profile.client_ram_gb ? profile.client_ram_gb.toFixed(2) + ' GB' : 'detecting...'}</b></div>
                            <div>Storage: <b>${profile.client_storage_gb ? profile.client_storage_gb.toFixed(2) + ' GB' : 'detecting...'}</b></div>
                        </div>
                        <button class="secondary small" onclick="window.connManager.showOverrideForm()">Edit Override</button>
                    </div>

                    <div class="result-section">
                        <h4>MONGODB TARGET</h4>
                        <div class="result-grid">
                            <div>Version: <b>${conn.server_version}</b></div>
                            <div>Topology: <b>${conn.topology}</b></div>
                            <div>Primary: <b>${conn.is_primary ? 'Yes' : 'No'}</b></div>
                            <div>Edition: <b>${conn.edition}</b></div>
                            ${conn.set_name ? `<div>Replica Set: <b>${conn.set_name}</b></div>` : ''}
                            ${profile.server_cluster_tier ? `<div>Cluster Tier: <b>${profile.server_cluster_tier}</b></div>` : ''}
                        </div>
                    </div>

                    ${perm ? `
                    <div class="result-section">
                        <h4>PERMISSION CHECK ${perm.ok ? '<span class="pill ok">✓ ALL PASSED</span>' : '<span class="pill fail">✗ FAILED</span>'}</h4>
                        <div class="capability-grid">
                            ${perm.capabilities.map(cap => `
                                <div class="capability ${cap.pass ? 'pass' : 'fail'}">
                                    ${cap.pass ? '✓' : '✗'} ${cap.name}
                                    ${!cap.pass ? `<br><small class="error">${cap.detail}</small>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    ` : ''}

                    ${skew ? `
                    <div class="result-section">
                        <h4>CLOCK SKEW CHECK ${skew.ok ? '<span class="pill ok">✓ OK</span>' : '<span class="pill warn">⚠ WARNING</span>'}</h4>
                        <div>Skew: <b>${skew.skew_seconds}s</b> (threshold: ${skew.threshold_seconds}s)</div>
                        ${skew.warning ? `<div class="note warn">${skew.warning}</div>` : ''}
                    </div>
                    ` : ''}
                </div>
            `;
        } else {
            html += `
                <div class="discovery-results">
                    <div class="result-section error">
                        <h3>✗ CONNECTION FAILED</h3>
                        <p><b>Cause:</b> ${conn.error.cause}</p>
                        <p><b>Hint:</b> ${conn.error.hint}</p>
                        <details>
                            <summary>Raw error</summary>
                            <pre>${conn.error.message}</pre>
                        </details>
                    </div>
                </div>
            `;
        }

        container.innerHTML = html;
        container.style.display = 'block';
    }

    // ---- Event Handlers ----

    selectProfile(profileId) {
        this.selectedProfile = this.profiles.find(p => p.id === profileId);
        this.renderSelector('profile-selector-container');
    }

    async testSelectedProfile() {
        if (!this.selectedProfile) return;

        const resultContainer = document.getElementById('discovery-results-container');
        if (resultContainer) {
            resultContainer.innerHTML = '<p class="muted">Testing connection...</p>';
        }

        try {
            const results = await this.testConnection(this.selectedProfile.id);
            this.renderDiscoveryResults('discovery-results-container', results);

            // Refresh selector to show updated test status
            this.renderSelector('profile-selector-container');
        } catch (error) {
            if (resultContainer) {
                resultContainer.innerHTML = `<div class="result-section error"><p>Test failed: ${error.message}</p></div>`;
            }
        }
    }

    showAddForm() {
        this.isAddingNew = true;
        this.renderForm('profile-form-container', null);
    }

    editProfile(profileId) {
        const profile = this.profiles.find(p => p.id === profileId);
        if (profile) {
            this.renderForm('profile-form-container', profile);
        }
    }

    cancelForm() {
        const container = document.getElementById('profile-form-container');
        if (container) {
            container.innerHTML = '';
            container.style.display = 'none';
        }
        this.isAddingNew = false;
    }

    async submitForm(event, profileId) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);

        const data = {
            name: formData.get('name'),
            uri: formData.get('uri') || undefined,
            database_name: formData.get('database_name'),
            auth_source: formData.get('auth_source') || null,
        };

        try {
            if (profileId) {
                // Update
                await this.updateProfile(profileId, data);
            } else {
                // Create
                await this.createProfile(data);
            }

            this.cancelForm();
            await this.loadProfiles();
            this.renderSelector('profile-selector-container');
        } catch (error) {
            alert(`Failed to save profile: ${error.message}`);
        }

        return false;
    }

    deletePrompt(profileId) {
        const profile = this.profiles.find(p => p.id === profileId);
        if (!profile) return;

        if (confirm(`Delete profile "${profile.name}"?`)) {
            this.deleteProfile(profileId).then(() => {
                this.renderSelector('profile-selector-container');
            }).catch(error => {
                alert(`Failed to delete: ${error.message}`);
            });
        }
    }

    toggleUriVisibility() {
        const input = document.querySelector('input[name="uri"]');
        if (input) {
            input.type = input.type === 'password' ? 'text' : 'password';
        }
    }

    showOverrideForm() {
        // TODO: Implement override form
        alert('Hardware override form - to be implemented');
    }

    // ---- Utilities ----

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export for use in main app
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ConnectionManager;
}

    showOverrideModal() {
        if (!this.currentDiscovery) return;

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content override-modal">
                <h3>Override Hardware Specifications</h3>
                <p class="modal-description">Override auto-detected values. System will use these for limit calculations.</p>

                <div class="override-section">
                    <h4>Client Hardware (Driver Host)</h4>
                    <div class="override-form">
                        <div class="form-row">
                            <label>CPU Cores</label>
                            <input type="number" id="override-cpu" value="${this.currentDiscovery.client?.cpu_cores || 0}" min="1" max="256">
                        </div>
                        <div class="form-row">
                            <label>RAM (GB)</label>
                            <input type="number" id="override-ram" value="${this.currentDiscovery.client?.ram_gb || 0}" min="1" max="2048" step="0.1">
                        </div>
                        <div class="form-row">
                            <label>Storage (GB)</label>
                            <input type="number" id="override-storage" value="${this.currentDiscovery.client?.storage_gb || 0}" min="1" max="100000">
                        </div>
                    </div>
                </div>

                <div class="override-section">
                    <h4>MongoDB Target</h4>
                    <div class="override-form">
                        <div class="form-row">
                            <label>Max Connections</label>
                            <input type="number" id="override-max-conn" value="${this.currentDiscovery.server?.max_connections || 1000}" min="10" max="100000">
                        </div>
                        <div class="form-row">
                            <label>Server RAM (GB)</label>
                            <input type="number" id="override-server-ram" value="${this.currentDiscovery.server?.ram_gb || 16}" min="1" max="10000" step="0.1">
                        </div>
                        <div class="form-row">
                            <label>Server vCPUs</label>
                            <input type="number" id="override-vcpus" value="${this.currentDiscovery.server?.vcpus || 4}" min="1" max="512">
                        </div>
                    </div>
                </div>

                <div class="modal-actions">
                    <button class="btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                    <button class="btn-primary" onclick="window.connManager.saveOverrides()">Apply Overrides</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    }

    saveOverrides() {
        const overrides = {
            client: {
                cpu_cores: parseInt(document.getElementById('override-cpu').value),
                ram_gb: parseFloat(document.getElementById('override-ram').value),
                storage_gb: parseFloat(document.getElementById('override-storage').value),
            },
            server: {
                max_connections: parseInt(document.getElementById('override-max-conn').value),
                ram_gb: parseFloat(document.getElementById('override-server-ram').value),
                vcpus: parseInt(document.getElementById('override-vcpus').value),
            }
        };

        // Update current discovery with overrides
        this.currentDiscovery = {
            ...this.currentDiscovery,
            client: { ...this.currentDiscovery.client, ...overrides.client },
            server: { ...this.currentDiscovery.server, ...overrides.server }
        };

        // Re-render discovery results
        this.displayDiscoveryResults(this.currentDiscovery);

        // Close modal
        document.querySelector('.modal-overlay').remove();

        console.log('Hardware overrides applied:', overrides);
    }
}

// Export
window.ConnectionManager = ConnectionManager;
