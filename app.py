#!/usr/bin/env python3
"""
Flask web GUI for the Vocabulary Flashcard Generator.

Run:
    python app.py
Then open http://localhost:5000 in your browser.
"""

import json
import os
import queue
import threading
import time
import uuid

from flask import (Flask, render_template_string, request, jsonify,
                   send_file, redirect, url_for, Response)

import src.config as config

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max upload

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(config.OUTPUT_DIR, exist_ok=True)

# In-memory job store: {job_id: {status, progress, result, error, words}}
_jobs: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# HTML Template (single-page app using vanilla JS)
# ---------------------------------------------------------------------------

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vocabulary Flashcard Generator</title>
<style>
  :root {
    --primary: #4F46E5;
    --primary-light: #818CF8;
    --bg: #F9FAFB;
    --card-bg: #FFFFFF;
    --text: #111827;
    --text-muted: #6B7280;
    --border: #E5E7EB;
    --success: #059669;
    --danger: #DC2626;
    --tier2: #4285F4;
    --tier3: #FB8C00;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }
  .container { max-width: 900px; margin: 0 auto; padding: 24px 16px; }

  /* Header */
  header {
    text-align: center;
    padding: 32px 0 16px;
  }
  header h1 { font-size: 28px; font-weight: 700; }
  header p { color: var(--text-muted); margin-top: 8px; font-size: 15px; }

  /* Tabs */
  .tabs {
    display: flex;
    border-bottom: 2px solid var(--border);
    margin-bottom: 24px;
  }
  .tab {
    padding: 10px 24px;
    cursor: pointer;
    font-weight: 600;
    color: var(--text-muted);
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition: all 0.2s;
  }
  .tab:hover { color: var(--primary); }
  .tab.active { color: var(--primary); border-bottom-color: var(--primary); }

  /* Panels */
  .panel { display: none; }
  .panel.active { display: block; }

  /* Card container */
  .card {
    background: var(--card-bg);
    border-radius: 12px;
    border: 1px solid var(--border);
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }
  .card h3 { font-size: 17px; margin-bottom: 16px; }

  /* Form elements */
  label { display: block; font-weight: 600; font-size: 14px; margin-bottom: 6px; }
  .hint { font-size: 12px; color: var(--text-muted); margin-bottom: 12px; }
  input[type="text"], input[type="password"], input[type="number"], select {
    width: 100%; padding: 10px 14px; border: 1px solid var(--border);
    border-radius: 8px; font-size: 14px; outline: none; transition: border 0.2s;
  }
  input:focus, select:focus { border-color: var(--primary); }
  .form-group { margin-bottom: 16px; }
  .form-row { display: flex; gap: 16px; }
  .form-row .form-group { flex: 1; }

  /* File upload */
  .upload-area {
    border: 2px dashed var(--border);
    border-radius: 12px;
    padding: 48px 24px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    background: #FAFAFA;
  }
  .upload-area:hover, .upload-area.dragover {
    border-color: var(--primary);
    background: #EEF2FF;
  }
  .upload-area .icon { font-size: 48px; margin-bottom: 12px; }
  .upload-area p { color: var(--text-muted); }
  .upload-area .filename {
    margin-top: 12px;
    font-weight: 600;
    color: var(--primary);
  }
  input[type="file"] { display: none; }

  /* Buttons */
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 12px 28px;
    border: none;
    border-radius: 8px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-primary { background: var(--primary); color: white; }
  .btn-primary:hover { background: #4338CA; }
  .btn-primary:disabled { background: #A5B4FC; cursor: not-allowed; }
  .btn-success { background: var(--success); color: white; }
  .btn-success:hover { background: #047857; }
  .btn-outline {
    background: white; color: var(--primary);
    border: 1px solid var(--primary);
  }
  .btn-outline:hover { background: #EEF2FF; }
  .btn-sm { padding: 8px 16px; font-size: 13px; }
  .actions { display: flex; gap: 12px; margin-top: 20px; justify-content: center; }

  /* Progress */
  .progress-container { margin: 24px 0; }
  .progress-bar-bg {
    height: 8px;
    background: var(--border);
    border-radius: 4px;
    overflow: hidden;
  }
  .progress-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--primary), var(--primary-light));
    border-radius: 4px;
    transition: width 0.5s ease;
    width: 0%;
  }
  .progress-log {
    margin-top: 16px;
    max-height: 200px;
    overflow-y: auto;
    font-family: 'SF Mono', Monaco, Consolas, monospace;
    font-size: 13px;
    background: #1F2937;
    color: #D1D5DB;
    border-radius: 8px;
    padding: 16px;
  }
  .progress-log .log-item {
    padding: 3px 0;
    border-bottom: 1px solid #374151;
  }
  .progress-log .log-item:last-child { border-bottom: none; }
  .progress-log .time { color: #6B7280; margin-right: 8px; }
  .progress-log .success { color: #34D399; }
  .progress-log .error { color: #F87171; }

  /* Status badge */
  .status {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
  }
  .status-running { background: #DBEAFE; color: #1D4ED8; }
  .status-done { background: #D1FAE5; color: #065F46; }
  .status-error { background: #FEE2E2; color: #991B1B; }

  /* Results table */
  .words-preview {
    max-height: 400px;
    overflow-y: auto;
    margin-top: 16px;
  }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
  th { background: #F3F4F6; font-weight: 600; position: sticky; top: 0; }
  .tier-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    color: white;
  }
  .tier-2 { background: var(--tier2); }
  .tier-3 { background: var(--tier3); }

  /* Config saved toast */
  .toast {
    position: fixed;
    bottom: 24px;
    right: 24px;
    padding: 12px 24px;
    background: #065F46;
    color: white;
    border-radius: 8px;
    font-weight: 600;
    opacity: 0;
    transform: translateY(10px);
    transition: all 0.3s;
    z-index: 100;
  }
  .toast.show { opacity: 1; transform: translateY(0); }

  /* Spinner */
  .spinner {
    display: inline-block;
    width: 20px; height: 20px;
    border: 3px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .check-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
  }
  .check-row input[type="checkbox"] {
    width: 18px; height: 18px; accent-color: var(--primary);
  }

  /* Responsive */
  @media (max-width: 600px) {
    .form-row { flex-direction: column; gap: 0; }
    .container { padding: 12px; }
  }
</style>
</head>
<body>

<div class="container">
  <header>
    <h1>Vocabulary Flashcard Generator</h1>
    <p>Upload a PDF article, extract vocabulary with Gemini AI, generate flashcards</p>
  </header>

  <!-- Tabs -->
  <div class="tabs">
    <div class="tab active" onclick="showPanel('generate')">Generate</div>
    <div class="tab" onclick="showPanel('settings')">Settings</div>
    <div class="tab" onclick="showPanel('history')">History</div>
  </div>

  <!-- ==================== GENERATE PANEL ==================== -->
  <div id="panel-generate" class="panel active">

    <!-- Step 1: Upload -->
    <div id="step-upload" class="card">
      <h3>1. Upload PDF Article</h3>
      <div class="upload-area" id="drop-zone" onclick="document.getElementById('pdf-input').click()">
        <div class="icon">&#128196;</div>
        <p>Click to choose a PDF file, or drag and drop here</p>
        <div class="filename" id="file-label"></div>
      </div>
      <input type="file" id="pdf-input" accept=".pdf">

      <div class="form-row" style="margin-top:16px">
        <div class="form-group">
          <label>Number of Words</label>
          <input type="number" id="word-count" value="30" min="5" max="60">
        </div>
        <div class="form-group">
          <label>Gemini Model</label>
          <select id="model-select">
            <option value="gemini-2.5-flash" selected>Gemini 2.5 Flash (fast)</option>
            <option value="gemini-2.5-pro">Gemini 2.5 Pro (quality)</option>
            <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
          </select>
        </div>
      </div>

      <div class="check-row">
        <input type="checkbox" id="skip-images">
        <label for="skip-images" style="margin:0;font-weight:normal">Skip image search (faster, use placeholders)</label>
      </div>

      <div class="actions">
        <button class="btn btn-primary" id="btn-generate" onclick="startGenerate()" disabled>
          Generate Flashcards
        </button>
      </div>
    </div>

    <!-- Step 2: Progress -->
    <div id="step-progress" class="card" style="display:none">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h3>Processing...</h3>
        <span class="status status-running" id="job-status">Running</span>
      </div>
      <div class="progress-container">
        <div class="progress-bar-bg">
          <div class="progress-bar" id="progress-bar"></div>
        </div>
      </div>
      <div class="progress-log" id="progress-log"></div>
    </div>

    <!-- Step 3: Results -->
    <div id="step-results" class="card" style="display:none">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h3>Flashcards Ready!</h3>
        <span class="status status-done">Complete</span>
      </div>
      <p style="margin-top:8px;color:var(--text-muted)" id="result-summary"></p>

      <div class="actions">
        <button class="btn btn-success" onclick="downloadResult()">Download PDF</button>
        <button class="btn btn-outline" onclick="downloadJson()">Download Words JSON</button>
        <button class="btn btn-outline" onclick="resetForm()">Generate Another</button>
      </div>

      <h3 style="margin-top:24px">Word Preview</h3>
      <div class="words-preview" id="words-preview"></div>
    </div>
  </div>

  <!-- ==================== SETTINGS PANEL ==================== -->
  <div id="panel-settings" class="panel">
    <div class="card">
      <h3>API Configuration</h3>
      <p class="hint" style="margin-bottom:16px;">
        Keys are stored in your browser only and sent to this local server per request.
        They are never transmitted elsewhere.
      </p>

      <div class="form-group">
        <label>Gemini API Key <span style="color:var(--danger)">*required</span></label>
        <input type="password" id="cfg-gemini-key" placeholder="AIzaSy...">
        <p class="hint">
          Get a free key at
          <a href="https://aistudio.google.com/apikey" target="_blank">aistudio.google.com/apikey</a>
        </p>
      </div>

      <hr style="border:none;border-top:1px solid var(--border);margin:20px 0">
      <h3>Image Search</h3>
      <p class="hint" style="margin-bottom:16px;">
        Images are automatically fetched from <strong>Wikimedia Commons</strong> (free, no key needed).<br>
        Optionally, you can also configure Google Custom Search for more image variety.
      </p>

      <div class="form-group">
        <label>Google Custom Search API Key <span style="color:var(--text-muted)">(optional)</span></label>
        <input type="password" id="cfg-cse-key" placeholder="AIzaSy...">
      </div>
      <div class="form-group">
        <label>Search Engine ID (cx) <span style="color:var(--text-muted)">(optional)</span></label>
        <input type="text" id="cfg-cse-cx" placeholder="e.g. a1b2c3d4e5f6g7h8i">
        <p class="hint">
          If left blank, Wikimedia Commons will be used automatically.
        </p>
      </div>

      <div class="actions" style="justify-content:flex-start">
        <button class="btn btn-primary" onclick="saveSettings()">Save Settings</button>
      </div>
    </div>

    <!-- ==================== SETUP GUIDE ==================== -->
    <div class="card">
      <h3>Setup Guide</h3>
      <div style="font-size:14px;line-height:1.8;">
        <p><strong>Step 1: Install Python Dependencies</strong></p>
        <pre style="background:#1F2937;color:#D1D5DB;padding:14px;border-radius:8px;overflow-x:auto;margin:8px 0 16px">pip install flask google-generativeai reportlab Pillow requests</pre>

        <p><strong>Step 2: Get a Gemini API Key (Free)</strong></p>
        <ol style="padding-left:20px;margin:8px 0 16px">
          <li>Go to <a href="https://aistudio.google.com/apikey" target="_blank">aistudio.google.com/apikey</a></li>
          <li>Sign in with your Google account</li>
          <li>Click <strong>"Create API Key"</strong></li>
          <li>Copy the key and paste it in the Settings tab above</li>
        </ol>

        <p><strong>Step 3: (Optional) Setup Image Search</strong></p>
        <ol style="padding-left:20px;margin:8px 0 16px">
          <li>Go to <a href="https://programmablesearchengine.google.com/" target="_blank">Programmable Search Engine</a></li>
          <li>Create a new search engine, set "Search the entire web"</li>
          <li>Copy the <strong>Search Engine ID</strong> (cx)</li>
          <li>Enable the Custom Search API in <a href="https://console.cloud.google.com/apis/library/customsearch.googleapis.com" target="_blank">Google Cloud Console</a></li>
          <li>Create an API key in <a href="https://console.cloud.google.com/apis/credentials" target="_blank">Credentials</a> (or reuse the Gemini key if same project)</li>
          <li>Paste both values in Settings above</li>
        </ol>

        <p><strong>Step 4: (Optional) Install CJK Fonts</strong></p>
        <pre style="background:#1F2937;color:#D1D5DB;padding:14px;border-radius:8px;overflow-x:auto;margin:8px 0 16px"># Ubuntu / Debian
sudo apt-get install fonts-noto-cjk

# macOS - CJK fonts are pre-installed</pre>

        <p><strong>Step 5: Run the Web App</strong></p>
        <pre style="background:#1F2937;color:#D1D5DB;padding:14px;border-radius:8px;overflow-x:auto;margin:8px 0">python app.py</pre>
        <p style="margin-top:6px">Then open <a href="http://localhost:5000" target="_blank">http://localhost:5000</a></p>
      </div>
    </div>
  </div>

  <!-- ==================== HISTORY PANEL ==================== -->
  <div id="panel-history" class="panel">
    <div class="card">
      <h3>Recent Jobs</h3>
      <div id="history-list">
        <p style="color:var(--text-muted)">No jobs yet. Generate some flashcards first!</p>
      </div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
// --- State ---
let currentJobId = null;
let pollingTimer = null;

// --- Tab switching ---
function showPanel(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  event.target.classList.add('active');
  if (name === 'history') loadHistory();
}

// --- File upload ---
const dropZone = document.getElementById('drop-zone');
const pdfInput = document.getElementById('pdf-input');
const fileLabel = document.getElementById('file-label');
const btnGenerate = document.getElementById('btn-generate');

pdfInput.addEventListener('change', () => {
  if (pdfInput.files.length > 0) {
    fileLabel.textContent = pdfInput.files[0].name;
    btnGenerate.disabled = false;
  }
});

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('dragover');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  if (e.dataTransfer.files.length > 0 && e.dataTransfer.files[0].type === 'application/pdf') {
    pdfInput.files = e.dataTransfer.files;
    fileLabel.textContent = e.dataTransfer.files[0].name;
    btnGenerate.disabled = false;
  }
});

// --- Settings ---
function loadSettings() {
  document.getElementById('cfg-gemini-key').value = localStorage.getItem('gemini_key') || '';
  document.getElementById('cfg-cse-key').value = localStorage.getItem('cse_key') || '';
  document.getElementById('cfg-cse-cx').value = localStorage.getItem('cse_cx') || '';
}
function saveSettings() {
  localStorage.setItem('gemini_key', document.getElementById('cfg-gemini-key').value.trim());
  localStorage.setItem('cse_key', document.getElementById('cfg-cse-key').value.trim());
  localStorage.setItem('cse_cx', document.getElementById('cfg-cse-cx').value.trim());
  showToast('Settings saved!');
}
loadSettings();

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

// --- Generate ---
async function startGenerate() {
  const geminiKey = localStorage.getItem('gemini_key');
  if (!geminiKey) {
    showToast('Please set your Gemini API Key in Settings first!');
    showPanel('settings');
    document.querySelector('[onclick="showPanel(\'settings\')"]').classList.add('active');
    return;
  }
  if (!pdfInput.files.length) return;

  // Show progress
  document.getElementById('step-upload').style.display = 'none';
  document.getElementById('step-progress').style.display = 'block';
  document.getElementById('step-results').style.display = 'none';
  document.getElementById('progress-log').innerHTML = '';
  document.getElementById('progress-bar').style.width = '0%';
  document.getElementById('job-status').textContent = 'Running';
  document.getElementById('job-status').className = 'status status-running';

  const formData = new FormData();
  formData.append('pdf', pdfInput.files[0]);
  formData.append('gemini_key', geminiKey);
  formData.append('cse_key', localStorage.getItem('cse_key') || '');
  formData.append('cse_cx', localStorage.getItem('cse_cx') || '');
  formData.append('word_count', document.getElementById('word-count').value);
  formData.append('model', document.getElementById('model-select').value);
  formData.append('skip_images', document.getElementById('skip-images').checked ? '1' : '0');

  try {
    const resp = await fetch('/api/generate', { method: 'POST', body: formData });
    const data = await resp.json();
    if (data.error) {
      addLog(data.error, 'error');
      return;
    }
    currentJobId = data.job_id;
    addLog('Job started: ' + currentJobId);
    startPolling();
  } catch (err) {
    addLog('Network error: ' + err.message, 'error');
  }
}

function startPolling() {
  if (pollingTimer) clearInterval(pollingTimer);
  pollingTimer = setInterval(async () => {
    try {
      const resp = await fetch('/api/status/' + currentJobId);
      const data = await resp.json();

      // Update logs
      const logEl = document.getElementById('progress-log');
      if (data.progress && data.progress.length > 0) {
        logEl.innerHTML = data.progress.map(p =>
          `<div class="log-item"><span class="time">${p.time}</span>${p.msg}</div>`
        ).join('');
        logEl.scrollTop = logEl.scrollHeight;
      }

      // Update progress bar
      const pct = data.percent || 0;
      document.getElementById('progress-bar').style.width = pct + '%';

      if (data.status === 'done') {
        clearInterval(pollingTimer);
        document.getElementById('job-status').textContent = 'Complete';
        document.getElementById('job-status').className = 'status status-done';
        document.getElementById('progress-bar').style.width = '100%';
        showResults(data);
      } else if (data.status === 'error') {
        clearInterval(pollingTimer);
        document.getElementById('job-status').textContent = 'Error';
        document.getElementById('job-status').className = 'status status-error';
        addLog(data.error || 'Unknown error', 'error');
      }
    } catch (err) {
      // Ignore transient fetch errors
    }
  }, 1500);
}

function addLog(msg, cls) {
  const logEl = document.getElementById('progress-log');
  const now = new Date().toLocaleTimeString();
  const cssClass = cls ? ` class="${cls}"` : '';
  logEl.innerHTML += `<div class="log-item"><span class="time">${now}</span><span${cssClass}>${msg}</span></div>`;
  logEl.scrollTop = logEl.scrollHeight;
}

// --- Results ---
function showResults(data) {
  document.getElementById('step-results').style.display = 'block';
  const words = data.words || [];
  const tier2 = words.filter(w => w.tier === 2).length;
  const tier3 = words.filter(w => w.tier === 3).length;
  document.getElementById('result-summary').textContent =
    `${words.length} words extracted (${tier2} Tier 2, ${tier3} Tier 3) — ${Math.ceil(words.length / 2)} pages`;

  // Build preview table
  let html = `<table><thead><tr>
    <th>#</th><th>Word</th><th>Tier</th><th>Chinese</th><th>Spanish</th><th>Definition</th>
  </tr></thead><tbody>`;
  words.forEach((w, i) => {
    const tierBadge = `<span class="tier-badge tier-${w.tier}">Tier ${w.tier}</span>`;
    html += `<tr>
      <td>${i + 1}</td>
      <td><strong>${w.word}</strong></td>
      <td>${tierBadge}</td>
      <td>${w.chinese || ''}</td>
      <td>${w.spanish || ''}</td>
      <td>${w.english_definition || ''}</td>
    </tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('words-preview').innerHTML = html;
}

function downloadResult() {
  if (currentJobId) window.open('/api/download/' + currentJobId, '_blank');
}
function downloadJson() {
  if (currentJobId) window.open('/api/download-json/' + currentJobId, '_blank');
}

function resetForm() {
  document.getElementById('step-upload').style.display = 'block';
  document.getElementById('step-progress').style.display = 'none';
  document.getElementById('step-results').style.display = 'none';
  pdfInput.value = '';
  fileLabel.textContent = '';
  btnGenerate.disabled = true;
  currentJobId = null;
}

// --- History ---
async function loadHistory() {
  try {
    const resp = await fetch('/api/history');
    const data = await resp.json();
    const el = document.getElementById('history-list');
    if (!data.jobs || data.jobs.length === 0) {
      el.innerHTML = '<p style="color:var(--text-muted)">No jobs yet.</p>';
      return;
    }
    let html = '<table><thead><tr><th>Time</th><th>File</th><th>Words</th><th>Status</th><th>Action</th></tr></thead><tbody>';
    data.jobs.forEach(j => {
      const statusCls = j.status === 'done' ? 'status-done' : j.status === 'error' ? 'status-error' : 'status-running';
      const dl = j.status === 'done'
        ? `<a href="/api/download/${j.id}" class="btn btn-sm btn-outline">Download</a>`
        : '';
      html += `<tr>
        <td>${j.time || ''}</td>
        <td>${j.filename || ''}</td>
        <td>${j.word_count || '-'}</td>
        <td><span class="status ${statusCls}">${j.status}</span></td>
        <td>${dl}</td>
      </tr>`;
    });
    html += '</tbody></table>';
    el.innerHTML = html;
  } catch(e) {
    // ignore
  }
}
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """Accept PDF upload and start processing in a background thread."""
    pdf_file = request.files.get("pdf")
    if not pdf_file or not pdf_file.filename:
        return jsonify(error="No PDF file provided"), 400

    gemini_key = request.form.get("gemini_key", "").strip()
    if not gemini_key:
        return jsonify(error="Gemini API key is required"), 400

    # Save uploaded file
    job_id = uuid.uuid4().hex[:12]
    safe_name = "".join(c if c.isalnum() or c in ".-_" else "_"
                        for c in pdf_file.filename)
    pdf_path = os.path.join(UPLOAD_DIR, f"{job_id}_{safe_name}")
    pdf_file.save(pdf_path)

    # Job record
    _jobs[job_id] = {
        "status": "running",
        "progress": [],
        "percent": 0,
        "words": None,
        "result_path": None,
        "error": None,
        "filename": pdf_file.filename,
        "time": time.strftime("%Y-%m-%d %H:%M"),
    }

    # Collect settings from form
    settings = {
        "gemini_key": gemini_key,
        "cse_key": request.form.get("cse_key", "").strip(),
        "cse_cx": request.form.get("cse_cx", "").strip(),
        "word_count": int(request.form.get("word_count", 30)),
        "model": request.form.get("model", "gemini-2.5-flash"),
        "skip_images": request.form.get("skip_images") == "1",
    }

    # Run in background
    t = threading.Thread(target=_run_job, args=(job_id, pdf_path, settings),
                         daemon=True)
    t.start()

    return jsonify(job_id=job_id)


@app.route("/api/status/<job_id>")
def api_status(job_id):
    job = _jobs.get(job_id)
    if not job:
        return jsonify(error="Job not found"), 404
    return jsonify(
        status=job["status"],
        progress=job["progress"],
        percent=job["percent"],
        words=job["words"],
        error=job["error"],
    )


@app.route("/api/download/<job_id>")
def api_download(job_id):
    job = _jobs.get(job_id)
    if not job or not job.get("result_path"):
        return jsonify(error="File not ready"), 404
    path = job["result_path"]
    if path.endswith(".html"):
        return send_file(path, mimetype="text/html", as_attachment=True,
                         download_name="flashcards.html")
    return send_file(path, mimetype="application/pdf", as_attachment=True,
                     download_name="flashcards.pdf")


@app.route("/api/download-json/<job_id>")
def api_download_json(job_id):
    job = _jobs.get(job_id)
    if not job or not job.get("words"):
        return jsonify(error="Data not ready"), 404
    return Response(
        json.dumps(job["words"], ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=vocabulary.json"},
    )


@app.route("/api/history")
def api_history():
    jobs = []
    for jid, j in sorted(_jobs.items(), key=lambda x: x[1].get("time", ""),
                          reverse=True):
        jobs.append({
            "id": jid,
            "filename": j.get("filename"),
            "status": j.get("status"),
            "word_count": len(j["words"]) if j.get("words") else 0,
            "time": j.get("time"),
        })
    return jsonify(jobs=jobs)


# ---------------------------------------------------------------------------
# Background job runner
# ---------------------------------------------------------------------------

def _run_job(job_id: str, pdf_path: str, settings: dict):
    """Execute the full pipeline in a background thread."""
    job = _jobs[job_id]

    def _log(msg):
        job["progress"].append({
            "time": time.strftime("%H:%M:%S"),
            "msg": msg,
        })

    try:
        # Apply settings to config
        config.update(
            GEMINI_API_KEY=settings["gemini_key"],
            GEMINI_MODEL=settings["model"],
            TARGET_WORD_COUNT=settings["word_count"],
            GOOGLE_CSE_API_KEY=settings.get("cse_key", ""),
            GOOGLE_CSE_CX=settings.get("cse_cx", ""),
        )

        # Step 1: Extract vocabulary
        _log("Step 1/3: Extracting vocabulary from PDF...")
        job["percent"] = 10

        from src.gemini_client import extract_vocabulary
        words = extract_vocabulary(pdf_path, on_progress=_log)
        job["words"] = words
        job["percent"] = 50

        tier2 = [w for w in words if w.get("tier") == 2]
        tier3 = [w for w in words if w.get("tier") == 3]
        _log(f"Found {len(words)} words ({len(tier2)} Tier 2, {len(tier3)} Tier 3)")

        # Step 2: Fetch images
        _log("Step 2/3: Fetching images...")
        job["percent"] = 55

        if settings.get("skip_images"):
            _log("Skipping images (placeholder mode)")
            images = {}
        else:
            from src.image_fetcher import fetch_all_images
            images = fetch_all_images(words, on_progress=_log)

        job["percent"] = 80
        _log(f"Images ready ({len(images)} fetched)")

        # Step 3: Generate PDF
        _log("Step 3/3: Generating flashcard PDF...")
        output_path = os.path.join(config.OUTPUT_DIR, f"{job_id}_flashcards.pdf")
        from src.flashcard_generator import generate_pdf
        result_path = generate_pdf(words, images, output_path)
        job["result_path"] = result_path
        job["percent"] = 100

        _log(f"Done! Output: {os.path.basename(result_path)}")
        job["status"] = "done"

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        _log(f"ERROR: {e}")

    finally:
        # Cleanup uploaded PDF
        try:
            os.remove(pdf_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n  Vocabulary Flashcard Generator")
    print("  ==============================")
    print("  Open http://localhost:5000 in your browser\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
