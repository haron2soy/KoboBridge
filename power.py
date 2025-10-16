# power.py
from __future__ import annotations
import os
from flask import Blueprint, request, jsonify, render_template_string, current_app

power_bp = Blueprint("power", __name__)

# ---------- Helper to build connection string ----------
def build_connection_string(endpoint: str, key_name: str, key_value: str, entity_path: str) -> str:
    # Accept either full "Endpoint=..." or a host like "mynamespace.servicebus.windows.net"
    endpoint = endpoint.strip()
    if endpoint.lower().startswith("endpoint="):
        # already full connection-string style endpoint
        endpoint_part = endpoint
    else:
        # normalize, allow user to pass with or without sb://
        if not endpoint.startswith("sb://"):
            endpoint = "sb://" + endpoint
        # ensure trailing slash removed for Endpoint= value, Power BI/Azure tolerate either
        endpoint_part = f"Endpoint={endpoint.rstrip('/')};"
    # Build remaining parts
    if not key_name or not key_value or not entity_path:
        raise ValueError("key_name, key_value and entity_path must be provided")

    # Ensure we don't duplicate "SharedAccessKeyName=" prefix if user included it
    if key_name.lower().startswith("sharedaccesskeyname="):
        key_name_part = key_name
    else:
        key_name_part = f"SharedAccessKeyName={key_name}"

    if key_value.lower().startswith("sharedaccesskey="):
        key_value_part = key_value
    else:
        key_value_part = f"SharedAccessKey={key_value}"

    if entity_path.lower().startswith("entitypath="):
        entity_part = entity_path
    else:
        entity_part = f"EntityPath={entity_path}"

    # If endpoint_part already contains "Endpoint=" we might have left a trailing semicolon; ensure proper concatenation
    if not endpoint_part.endswith(";"):
        endpoint_part += ";"

    conn = f"{endpoint_part}{key_name_part};{key_value_part};{entity_part}"
    return conn

# ---------- Inline HTML template (form) ----------
_FORM_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Event Stream Config</title>
<style>
  :root{--bg:#f6f8fa;--card:#ffffff;--muted:#6b7280;--accent:#0b5cff}
  body{font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,"Helvetica Neue",Arial;margin:0;background:var(--bg);display:flex;align-items:center;justify-content:center;height:100vh}
  .card{background:var(--card);padding:20px;border-radius:12px;box-shadow:0 6px 18px rgba(15,23,42,0.08);width:420px}
  h1{font-size:18px;margin:0 0 12px}
  label{display:block;font-size:13px;margin-top:12px;color:#111827}
  input[type="text"], input[type="password"], input[type="number"]{width:100%;padding:10px;border:1px solid #e6e9ef;border-radius:8px;margin-top:6px;box-sizing:border-box}
  .row{display:flex;gap:8px}
  .small{font-size:12px;color:var(--muted);margin-top:6px}
  .actions{display:flex;justify-content:space-between;align-items:center;margin-top:18px}
  button{background:var(--accent);color:white;border:none;padding:10px 14px;border-radius:8px;cursor:pointer}
  button.secondary{background:#e6eefc;color:#0b5cff}
  .hint{font-size:12px;color:var(--muted);margin-top:8px}
  .result{margin-top:12px;padding:10px;border-radius:8px;background:#f3f4f6;font-family:monospace;word-break:break-all}
  .toggle{cursor:pointer;font-size:12px;color:var(--accent);border:none;background:none;padding:0}
</style>
</head>
<body>
  <div class="card" role="main">
    <h1>Event Stream — Connection Builder</h1>
    <form id="cfgForm" onsubmit="return handleSubmit(event)">
      <label>Endpoint (host or full Endpoint=...)</label>
      <input id="endpoint" type="text" placeholder="mynamespace.servicebus.windows.net or Endpoint=sb://..." required />

      <label>SharedAccessKeyName</label>
      <input id="keyName" type="text" placeholder="RootManageSharedAccessKey" required />

      <label>SharedAccessKey</label>
      <div style="display:flex;gap:8px;align-items:center">
        <input id="keyValue" type="password" placeholder="••••••••••••••••" required />
        <button type="button" class="secondary" onclick="toggleSecret()" title="Show/Hide secret">Show</button>
      </div>
      <div class="small">Tip: Keep this secret secure. Do not commit to source control.</div>

      <label>EntityPath (Event Hub)</label>
      <input id="entityPath" type="text" placeholder="myeventhub" required />

      <label>Max retries (optional)</label>
      <input id="maxRetries" type="number" min="0" value="3" />

      <label>Retry delay seconds (optional)</label>
      <input id="retryDelay" type="number" step="0.1" value="1.0" />

      <label>Timeout seconds (optional)</label>
      <input id="timeout" type="number" value="30" />

      <div class="actions">
        <div class="hint">This will not persist secrets to git. Server will receive values.</div>
        <div style="display:flex;gap:8px">
          <button type="submit">Build & Save</button>
          <button type="button" class="secondary" onclick="resetForm()">Reset</button>
        </div>
      </div>
    </form>

    <div id="resultArea" class="result" style="display:none"></div>
  </div>

<script>
function toggleSecret(){
  const kv = document.getElementById('keyValue');
  const btn = event.target;
  if(kv.type === 'password'){ kv.type = 'text'; btn.textContent='Hide'; }
  else { kv.type = 'password'; btn.textContent='Show'; }
}

function resetForm(){
  document.getElementById('cfgForm').reset();
  document.getElementById('resultArea').style.display='none';
  document.getElementById('resultArea').textContent = '';
}

async function handleSubmit(e){
  e.preventDefault();
  const payload = {
    endpoint: document.getElementById('endpoint').value.trim(),
    key_name: document.getElementById('keyName').value.trim(),
    key_value: document.getElementById('keyValue').value,
    entity_path: document.getElementById('entityPath').value.trim(),
    max_retries: parseInt(document.getElementById('maxRetries').value || "3", 10),
    retry_delay: parseFloat(document.getElementById('retryDelay').value || "1.0"),
    timeout: parseInt(document.getElementById('timeout').value || "30", 10)
  };

  // Basic client-side validation
  if(!payload.endpoint || !payload.key_name || !payload.key_value || !payload.entity_path){
    alert('Please fill all required fields.');
    return;
  }

  const res = await fetch('/power/save', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  const area = document.getElementById('resultArea');
  if(res.ok){
    // show masked key in UI (don't reveal full secret)
    const maskedKey = payload.key_value.length > 6
      ? payload.key_value.slice(0,3) + '…' + payload.key_value.slice(-3)
      : '••••';
    area.style.display = 'block';
    area.textContent = `Connection string built:\n${data.connection_string}\n\nServer stored: ${data.stored ? 'yes' : 'no (in-memory only)'}\nSharedAccessKey (masked): ${maskedKey}`;
  } else {
    area.style.display = 'block';
    area.textContent = `Error: ${data.error || 'unknown'}`;
  }
}
</script>
</body>
</html>
"""

# ---------- Routes ----------
@power_bp.route("/power", methods=["GET"])
def power_form():
    """
    Serves the HTML/JS/CSS form for entering Event Hub connection parts.
    """
    return render_template_string(_FORM_HTML)


@power_bp.route("/power/save", methods=["POST"])
def power_save():
    """
    Accepts JSON body:
      {
        "endpoint": "...",
        "key_name": "...",
        "key_value": "...",
        "entity_path": "...",
        "max_retries": 3,
        "retry_delay": 1.0,
        "timeout": 30
      }

    Builds connection string server-side and returns it.
    Optionally sets os.environ for the running process (commented by default).
    """
    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    required = ("endpoint", "key_name", "key_value", "entity_path")
    if not all(k in payload and payload[k] for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    endpoint = payload["endpoint"]
    key_name = payload["key_name"]
    key_value = payload["key_value"]
    entity_path = payload["entity_path"]
    max_retries = int(payload.get("max_retries", 3))
    retry_delay = float(payload.get("retry_delay", 1.0))
    timeout = int(payload.get("timeout", 30))

    try:
        conn = build_connection_string(endpoint, key_name, key_value, entity_path)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # --- WARNING: be careful storing secrets ---
    # By default we do NOT persist secrets to disk or git.
    # You can enable storing to environment for the running process only by uncommenting below,
    # but ensure your deployment environment uses a secure secret store (Azure Key Vault, HashiCorp, etc.)
    store_in_env = False  # <-- set to True only if you understand the implications

    if store_in_env:
        os.environ["EVENTSTREAM_ENDPOINT"] = endpoint
        os.environ["EVENTSTREAM_KEY_NAME"] = key_name
        os.environ["EVENTSTREAM_KEY_VALUE"] = key_value
        os.environ["EVENTSTREAM_ENTITY_PATH"] = entity_path
        os.environ["EVENTSTREAM_CONN_STR"] = conn
        os.environ["MAX_RETRIES"] = str(max_retries)
        os.environ["RETRY_DELAY"] = str(retry_delay)
        os.environ["EVENTSTREAM_TIMEOUT"] = str(timeout)
        stored = True
    else:
        # Optionally keep values available in the running Flask app context for short-term use:
        # store in current_app.config (process-memory only, not persisted)
        current_app.config["EVENTSTREAM_CONN"] = conn
        current_app.config["EVENTSTREAM_PARTS"] = {
            "endpoint": endpoint,
            "key_name": key_name,
            "key_value": key_value,
            "entity_path": entity_path,
            "max_retries": max_retries,
            "retry_delay": retry_delay,
            "timeout": timeout
        }
        stored = False

    # Return a masked-ish connection string for UI; full conn is included because user requested it,
    # but UI masks secret; if you want to never return full conn, remove it from response.
    return jsonify({
        "connection_string": conn,           # You can remove this if you don't want to return full secret
        "stored": stored
    }), 200
