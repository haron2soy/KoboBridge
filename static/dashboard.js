// Dashboard JavaScript for real-time updates and interactions

class Dashboard {
    constructor() {
        this.refreshInterval = 30000; // 30 seconds
        this.intervalId = null;
        this.isTestingRunning = false;
        this.testingInterval = null;
        this.isStreamingActive = false;
        this.init();
    }

    async init() {
        this.bindEvents();
        //this.loadInitialData();
        //this.startAutoRefresh();
        this.setupWebhookUrl();
        const user = await this.checkCurrentUser();
        if (user && user.username) {
            this.loadInitialData();
            this.startAutoRefresh();
        } else {
            console.log("Not logged in — waiting until login to load dashboard data");
        }
    }
    

    bindEvents() {
        // Test EventStream button
        document.getElementById('test-eventstream').addEventListener('click', () => {
            this.testEventStream();
        });
        document.getElementById("refresh-logs").addEventListener("click", () => {
            this.refreshDashboard();
        });
        // Refresh logs button
        /*document.getElementById('refresh-logs').addEventListener('click', () => {
            this.loadRecentLogs();
            this.loadLatestDataTable();
        });*/

        // Copy webhook URL
        document.getElementById('copy-webhook-url').addEventListener('click', () => {
            this.copyWebhookUrl();
        });

        // Configuration forms
        document.getElementById('webhook-config-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveWebhookConfig();
        });

        document.getElementById('eventstream-config-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveEventStreamConfig();
        });

        document.getElementById('test-connection').addEventListener('click', () => {
            this.testEventStreamConnection();
        });

        // KoboToolbox API configuration
        document.getElementById('kobo-api-config-form').addEventListener('submit', (e) => {
            e.preventDefault();
            saveKoboApiConfig();
        });

        document.getElementById('kobo-server-url').addEventListener('change', () => {
            this.toggleCustomServer();
        });

        document.getElementById('load-kobo-projects').addEventListener('click', () => {
            loadKoboProjects();
        });

        document.getElementById('kobo-projects-select').addEventListener('change', (e) => {
            document.getElementById('kobo-project-id').value = e.target.value;
        });

        document.getElementById('test-kobo-connection').addEventListener('click', () => {
            testKoboConnection();
        });

        // Streaming controls
        document.getElementById('start-streaming').addEventListener('click', () => {
            startStreaming();
        });

        document.getElementById('stop-streaming').addEventListener('click', () => {
            this.stopStreaming();
        });

        // Load settings when modal is shown
        document.getElementById('settingsModal').addEventListener('show.bs.modal', () => {
            this.loadCurrentSettings();
        });

        // Show configuration modal
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'k') {
                e.preventDefault();
                const modal = new bootstrap.Modal(document.getElementById('settingsModal'));
                modal.show();
            }
        });


        const logoutBtn = document.getElementById('logout-btn');
        if(logoutBtn){
        logoutBtn.addEventListener('click', (e) => {
        e.preventDefault();
        this.logoutUser();
        });
        }

        const loginBtn = document.getElementById('login-btn');
        if (loginBtn) {
            loginBtn.addEventListener('click', (e) => {
                e.preventDefault();   // stop form auto-submit
                e.stopPropagation()
                this.loginUser();
            });
        }

        const registerBtn = document.getElementById('register-btn');
        if (registerBtn) {
            registerBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.registerUser();
            });
        }
    }

    async loadInitialData() {
        await Promise.all([
            this.loadStats(),
            this.loadRecentLogs(),
            this.loadLatestDataTable(),
            this.checkHealth()
        ]);
    }

    async checkCurrentUser() {
        try {
            const res = await fetch("/api/current-user", { credentials: "include" });
            
            if (!res.ok) {
                this.showAlert("Not yet logged in!");
                
                return;
            }
            else if(res.status == 401){
                this.isLoggedIn = false;   // ✅ mark as logged out
                this.showAlert("@hereYou are not logged in. Please log in first.", "danger");
                return;
            }
                
            
            const data = await res.json();  // { authenticated: true/false, username: ... }
            this.isLoggedIn = data.authenticated === true;  // ✅ update state
            return data;
        } catch (err) {
            console.error("Error checking current user:", err);
            this.showAlert("Unable to verify session. Please log in.");
            return { authenticated: false };
        }
    }
    
    
/*    showLoginMessage(message) {
    const container = document.getElementById("login-status");
    if (container) {
        container.innerText = message;
        container.style.display = "block";
    }
}*/



    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            const stats = await response.json();

            if (response.ok) {
                this.updateStatsDisplay(stats);
            } else {
                console.error('Failed to load stats:', stats.error);
            }
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }

    async stopStreaming() {
        if (!this.isStreamingActive) {
            this.showAlert('Streaming not active', 'warning');
            return;
        }
        try {
            const res = await fetch('/api/kobo/stop', { method: 'POST' });
            const data = await res.json();
            if (res.ok) {
                this.isStreamingActive = false;
                this.showAlert('Streaming stopped: ' + data.message, 'info');
            } else {
                this.showAlert('Failed: ' + data.message, 'error');
            }
        } catch (err) {
            console.error(err);
            this.showAlert('Error stopping stream', 'error');
        }
    }

    updateStatsDisplay(stats) {
        // Update main metrics
        document.getElementById('total-webhooks').textContent = stats.total_webhooks || 0;
        document.getElementById('success-rate').textContent = `${stats.success_rate || 0}%`;
        document.getElementById('avg-processing-time').textContent = `${stats.average_processing_time_ms || 0} ms`;
        document.getElementById('today-webhooks').textContent = stats.today_webhooks || 0;

        // Update EventStream metrics
        const esMetrics = stats.eventstream_metrics || {};
        document.getElementById('eventstream-success-rate').textContent = `${esMetrics.success_rate_percent || 0}%`;
        document.getElementById('eventstream-avg-time').textContent = `${esMetrics.average_transmission_time_ms || 0} ms`;

        // Update metric card colors based on performance
        this.updateCardColors(stats);
    }

    updateCardColors(stats) {
        const successRateElement = document.getElementById('success-rate').closest('.card');
        const processingTimeElement = document.getElementById('avg-processing-time').closest('.card');

        // Success rate colors
        successRateElement.classList.remove('metric-card', 'success', 'warning', 'danger');
        if (stats.success_rate >= 95) {
            successRateElement.classList.add('metric-card', 'success');
        } else if (stats.success_rate >= 80) {
            successRateElement.classList.add('metric-card', 'warning');
        } else {
            successRateElement.classList.add('metric-card', 'danger');
        }

        // Processing time colors (assuming < 1000ms is good, < 5000ms is acceptable)
        processingTimeElement.classList.remove('metric-card', 'success', 'warning', 'danger');
        if (stats.average_processing_time_ms < 1000) {
            processingTimeElement.classList.add('metric-card', 'success');
        } else if (stats.average_processing_time_ms < 5000) {
            processingTimeElement.classList.add('metric-card', 'warning');
        } else {
            processingTimeElement.classList.add('metric-card', 'danger');
        }
    }

    async loadRecentLogs() {
        console.log("loadRecentLogs() called");
        try {
            const response = await fetch('/api/recent-logs?limit=10');
            const logs = await response.json();

            if (response.ok) {
                this.displayRecentLogs(logs);
            } else {
                console.error('Failed to load logs:', logs.error);
                document.getElementById('recent-logs').innerHTML = 
                    '<div class="text-center text-danger">Failed to load recent logs</div>';
            }
        } catch (error) {
            console.error('Error loading logs:', error);
            document.getElementById('recent-logs').innerHTML = 
                '<div class="text-center text-danger">Error loading recent logs</div>';
        }
    }

    displayRecentLogs(logs) {
        const container = document.getElementById('recent-logs');
        
        if (logs.length === 0) {
            container.innerHTML = '<div class="text-center text-muted">No recent webhook activity</div>';
            return;
        }

        const logsHtml = logs.map(log => {
            const statusBadge = this.getStatusBadge(log.status);
            const timestamp = new Date(log.timestamp).toLocaleString();
            
            return `
                <div class="log-entry mb-3 p-3 border rounded">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div class="d-flex align-items-center">
                            ${statusBadge}
                            <span class="ms-2 fw-bold">#${log.id}</span>
                            ${log.kobo_form_id ? `<span class="ms-2 text-muted">(${log.kobo_form_id})</span>` : ''}
                        </div>
                        <small class="timestamp">${timestamp}</small>
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <small class="text-muted">Processing Time:</small>
                            <span class="ms-1">${log.processing_time_ms ? `${log.processing_time_ms.toFixed(2)}ms` : 'N/A'}</span>
                        </div>
                        <div class="col-md-6">
                            <small class="text-muted">Payload Size:</small>
                            <span class="ms-1">${log.payload_size ? `${(log.payload_size / 1024).toFixed(1)}KB` : 'N/A'}</span>
                        </div>
                    </div>
                    ${log.error_message ? `
                        <div class="mt-2">
                            <small class="text-danger">
                                <i data-feather="alert-triangle" style="width: 14px; height: 14px;"></i>
                                ${log.error_message}
                            </small>
                        </div>
                    ` : ''}
                    ${log.retry_count > 0 ? `
                        <div class="mt-1">
                            <small class="text-warning">Retries: ${log.retry_count}</small>
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');

        container.innerHTML = logsHtml;
        
        // Re-initialize Feather icons for new content
        feather.replace();
    }

    getStatusBadge(status) {
        switch (status) {
            case 'success':
                return '<span class="badge bg-success status-badge">Success</span>';
            case 'failed':
                return '<span class="badge bg-danger status-badge">Failed</span>';
            case 'processing':
                return '<span class="badge bg-warning status-badge">Processing</span>';
            case 'retry':
                return '<span class="badge bg-info status-badge">Retry</span>';
            default:
                return '<span class="badge bg-secondary status-badge">Unknown</span>';
        }
    }

    async checkHealth() {
        try {
            const response = await fetch('/health');
            const health = await response.json();

            if (response.ok) {
                this.updateHealthStatus(health);
            } else {
                console.error('Health check failed:', health.error);
            }
        } catch (error) {
            console.error('Error checking health:', error);
        }
    }

    updateHealthStatus(health) {
        // Update database status
        const dbStatus = health.database ? 'Reachable' : 'Error';
        const dbBadge = health.database ? 'bg-success' : 'bg-danger';
        document.getElementById('database-status').innerHTML = 
            `<span class="badge ${dbBadge}">${dbStatus}</span>`;

        // Update EventStream status
        const esStatus = health.eventstream?.status || 'Unknown';
        const esBadge = esStatus === 'healthy' ? 'bg-success' : 
                       esStatus === 'degraded' ? 'bg-warning' : 'bg-danger';
        document.getElementById('eventstream-status').innerHTML = 
            `<span class="badge ${esBadge}">${esStatus.charAt(0).toUpperCase() + esStatus.slice(1)}</span>`;
    }



    
    async testEventStream() {
        console.log("Calling testEventStream")
        const user = await this.checkCurrentUser();
        if (!user) {
            this.showAlert("You must log in first", "danger");
            return;
        }

        const button = document.getElementById("test-eventstream");

        if (this.isTestingRunning) {
            // Stop testing
            this.stopTesting();
            return;
        }

        // Start testing
        this.isTestingRunning = true;
        button.innerHTML = '<i data-feather="stop-circle"></i> Stop Testing';
        button.className = "btn btn-danger";
        feather.replace();

        let shouldRefresh = false;

        try {
            
            const response = await fetch("/api/test-eventstream", {
                method: "POST",
                credentials: "include",   // 🔑 send session cookie
                headers: { "Content-Type": "application/json" }
            });

            if (response.status === 401) {
                this.showAlert("Not logged in — please login first", "danger");
                return;
            }
            if (response.status === 400) {
                this.showAlert("No EventStream configuration available", "warning");
                return;
            }

            const result = await response.json();

            if (response.ok) {
                this.showAlert("EventStream test successful!", "success");
                this.loadRecentLogs();
                shouldRefresh = true;   // ✅ only refresh logs if test worked
                this.loadLatestDataTable();
                this.checkHealth();
            } else {
                this.showAlert(`EventStream test failed: ${result.message}`, "danger");
            }
            console.log("POST /api/test-eventstream response:", response.status);
        } catch (error) {
            this.showAlert(`EventStream test error: ${error.message}`, "danger");
        } finally {
            
            this.isTestingRunning = false;
            button.innerHTML = '<i data-feather="send"></i> Test EventStream';
            button.className = "btn btn-outline-success";
            feather.replace();

            // Refresh logs to show the test entry
            if (shouldRefresh) {
                setTimeout(() => this.loadRecentLogs(), 1000);
            }
            }
        }
    
            /*if (!response.ok) {
                this.showAlert(`EventStream test failed: ${result.message}`, 'warning');
                this.stopTesting();
            }
        } catch (error) {
            this.showAlert(`EventStream test error: ${error.message}`, 'danger');
            this.stopTesting();
        }
    }, 3000);

    // Initial test
    this.showAlert('EventStream testing started - sending sample data every 3 seconds', 'info');
    }
*/
    stopTesting() {
        if (this.testingInterval) {
            clearInterval(this.testingInterval);
            this.testingInterval = null;
        }
        
        this.isTestingRunning = false;
        const button = document.getElementById('test-eventstream');
        button.innerHTML = '<i data-feather="send"></i> Test EventStream';
        button.className = 'btn btn-outline-success';
        feather.replace();
        
        this.showAlert('EventStream testing stopped', 'info');
        // Refresh logs to show the test entries
        setTimeout(() => this.loadRecentLogs(), 1000);
    }

    setupWebhookUrl() {
        const webhookUrl = `${window.location.origin}/kobo-webhook`;
        document.getElementById('webhook-url').value = webhookUrl;
    }

    copyWebhookUrl() {
        const input = document.getElementById('webhook-url');
        input.select();
        document.execCommand('copy');
        
        const button = document.getElementById('copy-webhook-url');
        const originalHtml = button.innerHTML;
        button.innerHTML = '<i data-feather="check"></i>';
        feather.replace();
        
        setTimeout(() => {
            button.innerHTML = originalHtml;
            feather.replace();
        }, 2000);
    }

    showAlert(message, type = 'info') {
        // Create alert element
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        document.body.appendChild(alertDiv);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.parentNode.removeChild(alertDiv);
            }
        }, 5000);
    }
refreshDashboard() {
    if (!this.isLoggedIn) {
        this.showAlert("You are not Logged in.", "warning");
        return;
    }

    // Only run these if logged in
    this.loadStats();
    this.loadRecentLogs();
    this.loadLatestDataTable();
    this.checkHealth();
}
    startAutoRefresh() {
        //this.intervalId = setInterval(() => {
        this.intervalId = setInterval(async () => {
            const user = await this.checkCurrentUser();
            if (!user || !user.username) {
                this.stopAutoRefresh(); // stop refreshing if logged out
                return;
            }
            this.loadStats();
            this.loadRecentLogs();
            this.loadLatestDataTable();
            this.checkHealth();
        }, this.refreshInterval);
    }

    stopAutoRefresh() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }

    async loadLatestDataTable() {
        try {
            const response = await fetch('/api/latest-data');
            const data = await response.json();
            //console.log("Latest data from backend:", data);
            
            const container = document.getElementById('latest-data-table');
            
            if (response.ok && data.length > 0) {
                // Create table with the latest 5 entries
                let tableHtml = `
                    <div class="table-responsive">
                        <table class="table table-sm table-hover">
                            <thead>
                                <tr>
                                    <th>Timestamp</th>
                                    <th>Status</th>
                                    <th>Size</th>
                                </tr>
                            </thead>
                            <tbody>
                `;

                data.slice(0, 5).forEach(entry => {
                    const timestamp = new Date(entry.timestamp).toLocaleTimeString();
                    const statusBadge = entry.status === 'success' ? 
                        '<span class="badge bg-success">Success</span>' : 
                        '<span class="badge bg-danger">Failed</span>';
                    const size = entry.payload_size ? `${(entry.payload_size / 1024).toFixed(1)} KB` : '-';
                    
                    tableHtml += `
                        <tr>
                            <td><small>${timestamp}</small></td>
                            <td>${statusBadge}</td>
                            <td><small>${size}</small></td>
                        </tr>
                    `;
                });

                tableHtml += `
                            </tbody>
                        </table>
                    </div>
                `;
                
                container.innerHTML = tableHtml;
            } else {
                container.innerHTML = `
                    <div class="text-center text-muted py-3">
                        <i data-feather="inbox"></i>
                        <p class="mb-0 mt-2">No data sent yet</p>
                    </div>
                `;
                
            }
            // Replace feather icons after updating the DOM
            feather.replace();
        } catch (error) {
            console.error('Error loading latest data table:', error);
            document.getElementById('latest-data-table').innerHTML = `
                <div class="text-center text-danger py-3">
                    <i data-feather="alert-circle"></i>
                    <p class="mb-0 mt-2">Error loading data</p>
                </div>
            `;
            feather.replace();
        }
    }

    async loadCurrentSettings() {
        try {
            const response = await fetch('/api/configuration');
            const config = await response.json();

            if (response.ok) {
                // Update webhook URL
                document.getElementById('webhook-url').value = config.webhook_url;

                // Load current settings if they exist
                const settings = config.settings || {};
                
                // Webhook settings
                if (settings.webhook_verify_signature) {
                    document.getElementById('verify-signature').checked = settings.webhook_verify_signature.value !== 'false';
                }
                if (settings.webhook_max_payload_size) {
                    document.getElementById('max-payload-size').value = Math.floor(settings.webhook_max_payload_size.value / (1024 * 1024));
                }

                // EventStream settings (show if configured)
                /*if (settings.eventstream_connection_string) {
                    document.getElementById('connection-string').placeholder = settings.eventstream_connection_string.configured ? 
                        'Connection string is configured (hidden for security)' : 'Enter your EventStream connection string';
                }*/
                /*if (settings.eventstream_connection) {
                    if (settings.eventstream_connection.configured) {
                        document.getElementById('namespace').placeholder = 'Configured (hidden)';
                        document.getElementById('entity-path').placeholder = 'Configured (hidden)';
                        document.getElementById('key-name').placeholder = 'Configured (hidden)';
                        document.getElementById('key-value').placeholder = 'Configured (hidden)';
                    }
                }*/
                if (settings.eventstream_connection_string) {
                    if (settings.eventstream_connection_string.configured) {
                        // Mask all fields to indicate configuration exists
                        document.getElementById('namespace').placeholder = 'Configured (hidden)';
                        document.getElementById('entity-path').placeholder = 'Configured (hidden)';
                        document.getElementById('key-name').placeholder = 'Configured (hidden)';
                        document.getElementById('key-value').placeholder = 'Configured (hidden)';
                    } else if (settings.eventstream_connection_string.value) {
                        // Try to parse connection string if available
                        const connStr = settings.eventstream_connection_string.value;

                        // Extract values with regex
                        const nsMatch = connStr.match(/Endpoint=sb:\/\/([^.]*)/);
                        const entityMatch = connStr.match(/EntityPath=([^;]*)/);
                        const keyNameMatch = connStr.match(/SharedAccessKeyName=([^;]*)/);
                        const keyValueMatch = connStr.match(/SharedAccessKey=([^;]*)/);

                        if (nsMatch) document.getElementById('namespace').value = nsMatch[1];
                        if (entityMatch) document.getElementById('entity-path').value = entityMatch[1];
                        if (keyNameMatch) document.getElementById('key-name').value = keyNameMatch[1];
                        if (keyValueMatch) document.getElementById('key-value').value = keyValueMatch[1];
                    }
                }
                if (settings.eventstream_max_retries) {
                    document.getElementById('max-retries').value = settings.eventstream_max_retries.value || '3';
                }
                if (settings.eventstream_retry_delay) {
                    document.getElementById('retry-delay').value = settings.eventstream_retry_delay.value || '1.0';
                }
                if (settings.eventstream_timeout) {
                    document.getElementById('timeout').value = settings.eventstream_timeout.value || '30';
                }
            }
        } catch (error) {
            console.error('Error loading settings:', error);
        }
    }
    
    async logoutUser() {
        try {
            const response = await fetch('/logout', { method: 'POST' });
            const result = await response.json();

            if (response.ok) {
                // Stop any active intervals
                this.stopAutoRefresh();
                this.stopTesting();
                this.isStreamingActive = false;

                this.showAlert('Logged out successfully!', 'success');
                window.location.href = '/';

                // Clear dashboard content
                document.getElementById("stats").innerHTML = "";
                document.getElementById("health-status").innerHTML = "";
                document.getElementById("logs-list").innerHTML = "";
                document.getElementById("latest-data-table").innerHTML = "";
            } else {
                this.showAlert(result.error || 'Logout failed', 'danger');
            }
        } catch (error) {
            this.showAlert(`Error: ${error.message}`, 'danger');
        }
    }


    async saveWebhookConfig() {
        const data = {
            verify_signature: document.getElementById('verify-signature').checked,
            kobo_secret: document.getElementById('kobo-secret').value,
            max_payload_size: parseInt(document.getElementById('max-payload-size').value) * 1024 * 1024
        };

        try {
            const response = await fetch('/api/configuration/webhook', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (response.ok) {
                this.showAlert('Webhook settings saved successfully!', 'success');
                // Clear the secret field for security
                document.getElementById('kobo-secret').value = '';
            } else {
                this.showAlert(`Failed to save webhook settings: ${result.error}`, 'danger');
            }
        } catch (error) {
            this.showAlert(`Error saving webhook settings: ${error.message}`, 'danger');
        }
    }

/*    async saveEventStreamConfig() {
        const connectionString = document.getElementById('connection-string').value;
        if (!connectionString) {
            this.showAlert('Please enter an EventStream connection string', 'warning');
            return;
        }

        const data = {
            connection_string: connectionString,
            max_retries: parseInt(document.getElementById('max-retries').value),
            retry_delay: parseFloat(document.getElementById('retry-delay').value),
            timeout: parseInt(document.getElementById('timeout').value)
        };

        try {
            const response = await fetch('/api/configuration/eventstream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (response.ok) {
                this.showAlert('EventStream settings saved successfully!', 'success');
                // Clear the connection string field for security
                document.getElementById('connection-string').value = '';
                document.getElementById('connection-string').placeholder = 'Connection string is configured (hidden for security)';
                // Refresh health status
                setTimeout(() => this.checkHealth(), 1000);
            } else {
                this.showAlert(`Failed to save EventStream settings: ${result.error}`, 'danger');
            }
        } catch (error) {
            this.showAlert(`Error saving EventStream settings: ${error.message}`, 'danger');
        }
    }*/
    async saveEventStreamConfig() {
        const namespace = document.getElementById('namespace').value.trim();
        const entityPath = document.getElementById('entity-path').value.trim();
        const keyName = document.getElementById('key-name').value.trim();
        const keyValue = document.getElementById('key-value').value.trim();

        if (!namespace || !entityPath || !keyName || !keyValue) {
            this.showAlert('Please fill in all EventStream connection fields', 'warning');
            return;
        }
        /*
        const connectionString = 
            `Endpoint=sb://${namespace}.servicebus.windows.net/;` +
            `SharedAccessKeyName=${keyName};` +
            `SharedAccessKey=${keyValue};` +
            `EntityPath=${entityPath}`;*/

        const data = {
            //connection_string: connectionString,
            Endpoint: `sb://${namespace}.servicebus.windows.net/`,
            EntityPath: entityPath,
            SharedAccessKeyName: keyName,
            SharedAccessKey: keyValue,
            max_retries: parseInt(document.getElementById('max-retries').value),
            retry_delay: parseFloat(document.getElementById('retry-delay').value),
            timeout: parseInt(document.getElementById('timeout').value),
            save_to_db: true
        };

        try {
            const response = await fetch('/api/configuration/eventstream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (response.ok) {
                this.showAlert('EventStream settings saved successfully!', 'success');

                // Clear sensitive fields for security
                document.getElementById('key-value').value = '';
                document.getElementById('key-value').placeholder = 'Configured (hidden)';

                // Optionally mask the others too
                document.getElementById('namespace').placeholder = 'Configured (hidden)';
                document.getElementById('entity-path').placeholder = 'Configured (hidden)';
                document.getElementById('key-name').placeholder = 'Configured (hidden)';

                // Refresh health status
                setTimeout(() => this.checkHealth(), 1000);
            } else {
                this.showAlert(`Failed to save EventStream settings: ${result.error}`, 'danger');
            }
        } catch (error) {
            this.showAlert(`Error saving EventStream settings: ${error.message}`, 'danger');
        }
    }
    async testEventStreamConnection() {
        const button = document.getElementById('test-connection');
        const originalHtml = button.innerHTML;
        
        button.disabled = true;
        button.innerHTML = '<i data-feather="loader" class="spinning"></i> Testing...';
        feather.replace();

        try {
            const response = await fetch('/api/configuration/test-eventstream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const result = await response.json();

            if (response.ok) {
                this.showAlert('EventStream connection test successful!', 'success');
                // Refresh logs to show the test entry
                setTimeout(() => this.loadRecentLogs(), 1000);
            } else {
                this.showAlert(`EventStream connection test failed: ${result.message}`, 'danger');
            }
        } catch (error) {
            this.showAlert(`EventStream test error: ${error.message}`, 'danger');
        } finally {
            button.disabled = false;
            button.innerHTML = originalHtml;
            feather.replace();
        }
    }
    
    async registerUser() {
    const username = document.getElementById('register-username').value;
    const password = document.getElementById('register-password').value;

    if (!username || !password) {
        this.showAlert('Username and password required', 'warning');
        return;
    }

    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const result = await response.json();

        if (response.ok) {
            this.showAlert('Registration successful. You can now log in.', 'success');
            // Close modal
            bootstrap.Modal.getInstance(document.getElementById('registerModal')).hide();
        } else {
            this.showAlert(result.error || 'Registration failed', 'danger');
        }
    } catch (error) {
        this.showAlert(`Error: ${error.message}`, 'danger');
    }
    }

    async loginUser() {
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;

        if (!username || !password) {
            this.showAlert('Username and password required', 'warning');
            return;
        }

        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
                credentials: 'same-origin'
            });

            const result = await response.json();

            if (response.ok) {
                this.showAlert('Login successful!', 'success');
                bootstrap.Modal.getInstance(document.getElementById('loginModal')).hide();
                document.getElementById("login-status").style.display = "none";
                // Optional: refresh dashboard data after login
                //this.loadStats();
                //this.loadRecentLogs();
                // Start dashboard updates after successful login
                this.loadInitialData();
                this.startAutoRefresh();

                // Update navbar
                this.updateNavbarAfterLogin();
            } else if (response.status === 401) {
            // Wrong credentials
            this.showAlert('Invalid username or password', 'danger');
        
            
            // Highlight inputs
            document.getElementById('login-username').classList.add('is-invalid');
            document.getElementById('login-password').classList.add('is-invalid');
        } else {
            // Other errors
            this.showAlert(result.error || 'Login failed', 'danger');
        }

            
        } catch (error) {
            this.showAlert(`Error: ${error.message}`, 'danger');
        }
    }

updateNavbarAfterLogin() {
    fetch('/api/current-user')
        .then(res => res.json())
        .then(data => {
            if (data.username) {
                const navHtml = `
                    <li class="nav-item">
                        <a class="nav-link" href="/profile">
                            <i data-feather="user" class="me-1"></i>
                            ${data.username}
                        </a>
                    </li>
                    <li class="nav-item">
                        <button class="btn btn-link nav-link" type="button" id="logout-btn">
                            <i data-feather="log-out" class="me-1"></i>
                            Logout
                        </button>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/">
                            <i data-feather="home" class="me-1"></i>
                            Dashboard
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#" data-bs-toggle="modal" data-bs-target="#settingsModal">
                            <i data-feather="settings" class="me-1"></i>
                            Settings
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/health" target="_blank">
                            <i data-feather="heart" class="me-1"></i>
                            Health Check
                        </a>
                    </li>
                `;
                document.querySelector('.navbar-nav.ms-auto').innerHTML = navHtml;

                // Rebind logout
                document.getElementById('logout-btn').addEventListener('click', (e) => {
                    e.preventDefault();
                    this.logoutUser();
                });

                feather.replace();
            }
        });
}    
}

// Initialize dashboard when DOM is loaded
// Only initialize once
document.addEventListener('DOMContentLoaded', () => {
    if (!window.dashboard) {
        window.dashboard = new Dashboard();
    }
});

// Handle page visibility change to pause/resume auto-refresh
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && window.dashboard) {
        // Page became visible, ensure auto-refresh is running
        window.dashboard.startAutoRefresh();
    }else if (window.dashboard) {
        window.dashboard.stopAutoRefresh();
    }
});
