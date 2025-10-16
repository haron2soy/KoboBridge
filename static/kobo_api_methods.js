// Additional methods for KoboToolbox API integration - append to dashboard.js

function toggleCustomServer() {
    const serverSelect = document.getElementById('kobo-server-url');
    const customDiv = document.getElementById('custom-server-div');
    
    if (serverSelect && customDiv) {
        if (serverSelect.value === 'custom') {
            customDiv.style.display = 'block';
        } else {
            customDiv.style.display = 'none';
        }
    }
}

/*// Helper to get API token and validate
function getApiToken() {
    const apiToken = document.getElementById('kobo-api-token').value.trim();
    if (!apiToken) {
        alert("API token cannot be empty!");
        //throw new Error("API token is empty"); // stop execution
    }
    return apiToken;
}
*/
function getApiToken() {
    const api_token = document.getElementById('kobo-api-token').value.trim();
    console.log("DEBUG Sending to backend:", api_token);
    if (api_token) return api_token;
    console.log("Start streaming payload:", { api_token: api_token });
    return localStorage.getItem("kobo_api_token") || "";

}

/*
async function saveKoboApiConfig(showAlert) {
    const serverUrl = document.getElementById('kobo-server-url').value;
    const customServer = document.getElementById('kobo-custom-server').value;
    const apiToken = getApiToken();
    
    const pollingInterval = parseInt(document.getElementById('kobo-polling-interval').value);
    const batchSize = parseInt(document.getElementById('kobo-batch-size').value);

    if (!apiToken) {
        dashboard.showAlert('Please enter your KoboToolbox API token', 'warning');
        return;
    }



    const data = {
        server_url: serverUrl === 'custom' ? customServer : serverUrl,
        api_token: apiToken,
        //project_id: projectId,
        polling_interval: pollingInterval,
        batch_size: batchSize
    };

    try {
        const response = await fetch('/api/configuration/kobo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
           // body: JSON.stringify(data)
           body: JSON.stringify({ server_url: serverUrl, api_token: apiToken })
        });

        const result = await response.json();
        console.log("Save Config Response:", result);

        if (response.ok) {
            dashboard.showAlert('KoboToolbox settings saved successfully!', 'success');
            localStorage.setItem("kobo_api_token", apiToken);
            // Clear the API token field for security
            document.getElementById('kobo-api-token').value = '';
        } else {
            dashboard.showAlert(`Failed to save KoboToolbox settings: ${result.error}`, 'danger');
        }
    } catch (error) {
        dashboard.showAlert(`Error saving KoboToolbox settings: ${error.message}`, 'danger');
    }
}

async function loadKoboProjects(showAlert) {
    const button = document.getElementById('load-kobo-projects');
    const originalHtml = button.innerHTML;
    
    button.disabled = true;
    button.innerHTML = '<i data-feather="loader" class="spinning"></i>';
    feather.replace();

    try {
        const response = await fetch('/api/kobo/projects');
        const result = await response.json();

        if (response.ok && result.projects) {
            const select = document.getElementById('kobo-projects-select');
            select.innerHTML = '<option value="">Select a project...</option>';
            
            result.projects.forEach(project => {
                const option = document.createElement('option');
                option.value = project.uid;
                option.textContent = `${project.name} (${project.uid})`;
                select.appendChild(option);
            });
            
            document.getElementById('kobo-projects-list').style.display = 'block';
            dashboard.showAlert(`Loaded ${result.projects.length} projects`, 'success');
        } else {
            dashboard.showAlert(`Failed to load projects: ${result.message || 'Unknown error'}`, 'danger');
        }
    } catch (error) {
        dashboard.showAlert(`Error loading projects: ${error.message}`, 'danger');
    } finally {
        button.disabled = false;
        button.innerHTML = originalHtml;
        feather.replace();
    }
}

*/
// Called whenever URL or token input changes
async function autoLoadProjects() {
    const serverUrl = document.getElementById('kobo-server-url').value.trim();
    const apiToken = getApiToken();

    if (!serverUrl || !apiToken) {
        return; // Do nothing until both are provided
    }

    try {
        const response = await fetch('/api/kobo/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ server_url: serverUrl, api_token: apiToken })
        });

        const result = await response.json();

        if (response.ok && result.projects) {
            const select = document.getElementById('kobo-projects-select');
            select.innerHTML = '<option value="">Select a project...</option>';

            result.projects.forEach(project => {
                const option = document.createElement('option');
                option.value = project.uid;
                option.textContent = `${project.name} (${project.uid})`;
                select.appendChild(option);
            });

            document.getElementById('kobo-projects-list').style.display = 'block';
            dashboard.showAlert(`Loaded ${result.projects.length} projects`, 'success');
        } else {
            dashboard.showAlert(`Failed to load projects: ${result.message || 'Unknown error'}`, 'danger');
        }
    } catch (error) {
        dashboard.showAlert(`Error loading projects: ${error.message}`, 'danger');
    }
}

// Save final config including selected project
async function saveKoboConfig() {
    const projectId = document.getElementById('kobo-projects-select').value;
    if (!projectId) {
        dashboard.showAlert('Please select a project', 'warning');
        return;
    }

    try {
        const response = await fetch('/api/kobo/save-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_id: projectId })
        });

        const result = await response.json();
        if (response.ok) {
            dashboard.showAlert('KoboToolbox configuration saved successfully!', 'success');
        } else {
            dashboard.showAlert(`Failed to save configuration: ${result.message}`, 'danger');
        }
    } catch (err) {
        dashboard.showAlert(`Error saving configuration: ${err.message}`, 'danger');
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('kobo-server-url');
    const tokenInput = document.getElementById('kobo-api-token');

    if (urlInput) urlInput.addEventListener('input', autoLoadProjects);
    if (tokenInput) tokenInput.addEventListener('input', autoLoadProjects);

    // Save button
    const saveBtn = document.getElementById('save-kobo-config');
    if (saveBtn) saveBtn.addEventListener('click', saveKoboConfig);
});


/*
async function testKoboConnection(showAlert) {
    const button = document.getElementById('test-kobo-connection');
    const originalHtml = button.innerHTML;
    
    button.disabled = true;
    button.innerHTML = '<i data-feather="loader" class="spinning"></i> Testing...';
    feather.replace();

    try {
        const response = await fetch('/api/kobo/test-connection', {
            method: 'POST'
        });

        const result = await response.json();

        if (response.ok) {
            dashboard.showAlert('KoboToolbox connection test successful!', 'success');
        } else {
            dashboard.showAlert(`KoboToolbox connection test failed: ${result.message}`, 'danger');
        }
    } catch (error) {
        dashboard.showAlert(`KoboToolbox test error: ${error.message}`, 'danger');
    } finally {
        button.disabled = false;
        button.innerHTML = originalHtml;
        feather.replace();
    }
}*/

async function testKoboConnection() {
    try {
        const serverUrl = document.getElementById("kobo-server-url").value.trim();
        const apiToken = getApiToken();

        if (!serverUrl || !apiToken) {
            dashboard.showAlert("Please enter both Server URL and API Token", "error");
            return;
        }

        const response = await fetch("/api/kobo/test-connection", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                server_url: serverUrl,
                api_token: apiToken
            })
        });

        const data = await response.json();
        if (response.ok) {
            dashboard.showAlert(data.message, "success");
        } else {
            dashboard.showAlert(data.message || "Connection test failed", "error");
        }
    } catch (err) {
        console.error("Test connection error:", err);
        dashboard.showAlert("An error occurred while testing the connection", "error");
    }
}


async function startStreaming(showAlert) {
    try {
        const apiToken = getApiToken();
        const projectId = document.getElementById('kobo-project-id').value;
        if (!projectId) {
        
            dashboard.showAlert('Please enter a project/form ID', 'warning');
            return;
    }
        /*const data = {
            
        project_id: projectId,
            
        };*/
        const response = await fetch('/api/kobo/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({project_id: projectId})//api_token: apiToken })
            
        });
        console.log("js Startstreaming payload:", { api_token: apiToken });
        const result = await response.json();
        
        if (response.ok) {
            updateStreamingUI(true);
            dashboard.showAlert('Real-time streaming started!', 'success');
        } else {
            dashboard.showAlert(`Failed to start streaming: ${result.message}`, 'danger');
        }
    } catch (error) {
        dashboard.showAlert(`Error starting streaming: ${error.message}`, 'danger');
    }
}

async function stopStreaming(showAlert) {
    try {
        const response = await fetch('/api/streaming/stop', {
            method: 'POST'
        });

        const result = await response.json();

        if (response.ok) {
            updateStreamingUI(false);
            dashboard.showAlert('Real-time streaming stopped!', 'info');
        } else {
            dashboard.showAlert(`Failed to stop streaming: ${result.message}`, 'danger');
        }
    } catch (error) {
        dashboard.showAlert(`Error stopping streaming: ${error.message}`, 'danger');
    }
}

function updateStreamingUI(isActive) {
    const startBtn = document.getElementById('start-streaming');
    const stopBtn = document.getElementById('stop-streaming');
    const status = document.getElementById('streaming-status');

    if (startBtn && stopBtn && status) {
        if (isActive) {
            startBtn.disabled = true;
            stopBtn.disabled = false;
            status.innerHTML = '<span class="badge bg-success">Active</span>';
        } else {
            startBtn.disabled = false;
            stopBtn.disabled = true;
            status.innerHTML = '<span class="badge bg-secondary">Stopped</span>';
        }
    }
}

async function checkStreamingStatus() {
    try {
        const response = await fetch('/api/streaming/status');
        const result = await response.json();

        if (response.ok) {
            updateStreamingUI(result.active);
        }
    } catch (error) {
        console.error('Error checking streaming status:', error);
    }
}
/*
document.getElementById("test-kobo-connection").addEventListener("click", async () => {
    const serverSelect = document.getElementById("kobo-server-url");
    let server_url = serverSelect.value;
    if (server_url === "custom") {
        server_url = document.getElementById("kobo-custom-server").value;
    }
    const api_token = document.getElementById("kobo-api-token").value;

    if (!server_url || !api_token) {
        alert("Server URL and API token are required");
        return;
    }

    try {
        const response = await fetch("/api/kobo/test-connection", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ server_url, api_token })
        });

        const data = await response.json();
        if (response.ok) {
            alert(`Success: ${data.message}`);
        } else {
            alert(`Error: ${data.message}`);
        }
    } catch (err) {
        console.error("Test connection failed:", err);
        alert("Test connection failed. See console for details.");
    }
});

*/

// Initialize event handlers when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Server URL change handler
    const serverSelect = document.getElementById('kobo-server-url');
    if (serverSelect) {
        serverSelect.addEventListener('change', toggleCustomServer);
    }

    // Projects selection handler  
    const projectsSelect = document.getElementById('kobo-projects-select');
    if (projectsSelect) {
        projectsSelect.addEventListener('change', (e) => {
            const projectIdInput = document.getElementById('kobo-project-id');
            if (projectIdInput) {
                projectIdInput.value = e.target.value;
            }
        });
    }

    // Load current streaming status
    checkStreamingStatus();
});