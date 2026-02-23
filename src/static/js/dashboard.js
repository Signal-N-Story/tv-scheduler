/**
 * ATC TV Scheduler — Dashboard JavaScript
 */

const API = '/api/schedule';
const TEMPLATE_API = '/api/templates';
let currentWeekOffset = 0;

// ── Helpers ────────────────────────────────────────────────────
function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

function today() {
    return new Date().toISOString().slice(0, 10);
}

function formatDate(dateStr) {
    const d = new Date(dateStr + 'T12:00:00');
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

function getWeekDates(offset = 0) {
    const now = new Date();
    const monday = new Date(now);
    monday.setDate(now.getDate() - now.getDay() + 1 + offset * 7);
    const dates = [];
    for (let i = 0; i < 7; i++) {
        const d = new Date(monday);
        d.setDate(monday.getDate() + i);
        dates.push(d.toISOString().slice(0, 10));
    }
    return dates;
}

function showMsg(el, text, type) {
    el.textContent = text;
    el.className = `message ${type}`;
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 5000);
}

function getApiHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    const key = $('#apiKeyInput').value.trim();
    if (key) headers['X-API-Key'] = key;
    return headers;
}

// ── TV Status ──────────────────────────────────────────────────
async function checkTVStatus() {
    try {
        const res = await fetch('/tv/status');
        const data = await res.json();
        $('#statusDot').className = 'dot online';
        const boards = [data.mainboard_scheduled, data.modboard_scheduled].filter(Boolean).length;
        $('#statusText').textContent = `Online — ${boards} board(s) active`;
    } catch {
        $('#statusDot').className = 'dot offline';
        $('#statusText').textContent = 'Offline';
    }
}

// ── Templates ──────────────────────────────────────────────────
let templateCache = [];

async function loadTemplates() {
    try {
        const res = await fetch(TEMPLATE_API);
        const data = await res.json();
        templateCache = data.templates || [];
        populateTemplatePickers();
    } catch {
        templateCache = [];
    }
}

function populateTemplatePickers() {
    const pickers = ['#templatePicker', '#overrideTemplate'];
    pickers.forEach(sel => {
        const el = $(sel);
        if (!el) return;
        const firstOption = el.options[0];
        el.innerHTML = '';
        el.appendChild(firstOption);
        templateCache.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = `${t.name} (${t.board_type})`;
            el.appendChild(opt);
        });
    });
}

// Template picker — load into form
$('#templatePicker').addEventListener('change', (e) => {
    const id = parseInt(e.target.value);
    const tmpl = templateCache.find(t => t.id === id);
    if (!tmpl) return;
    $('#boardType').value = tmpl.board_type;
    $('#version').value = tmpl.version || (tmpl.board_type === 'mainboard' ? 'rx' : 'mod');
    $('#workoutTitle').value = tmpl.name;
    $('#htmlContent').value = tmpl.html_content;
});

// Override template picker
$('#overrideTemplate').addEventListener('change', (e) => {
    const id = parseInt(e.target.value);
    const tmpl = templateCache.find(t => t.id === id);
    if (!tmpl) return;
    $('#overrideBoard').value = tmpl.board_type;
    $('#overrideHtml').value = tmpl.html_content;
});

// Save as template
$('#saveTemplateBtn').addEventListener('click', async () => {
    const name = $('#workoutTitle').value.trim();
    const html = $('#htmlContent').value.trim();
    const board = $('#boardType').value;
    const version = $('#version').value;
    const msg = $('#formMessage');

    if (!name || !html) {
        showMsg(msg, 'Title and HTML are required to save a template', 'error');
        return;
    }

    try {
        const res = await fetch(TEMPLATE_API, {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify({ name, board_type: board, version, html_content: html }),
        });
        const data = await res.json();
        if (res.ok) {
            showMsg(msg, `Template "${name}" saved`, 'success');
            loadTemplates();
        } else {
            showMsg(msg, data.detail || 'Error saving template', 'error');
        }
    } catch (err) {
        showMsg(msg, `Network error: ${err.message}`, 'error');
    }
});

// ── Preview ────────────────────────────────────────────────────
$('#previewBtn').addEventListener('click', () => {
    const html = $('#htmlContent').value;
    if (!html.trim()) return;
    const frame = $('#previewFrame');
    frame.srcdoc = html;
    $('#previewModal').classList.remove('hidden');
});

$('#closePreview').addEventListener('click', () => {
    $('#previewModal').classList.add('hidden');
});

$('#previewModal').addEventListener('click', (e) => {
    if (e.target === $('#previewModal')) {
        $('#previewModal').classList.add('hidden');
    }
});

// ── File Upload ─────────────────────────────────────────────────
const UPLOAD_MAX_SIZE = 5 * 1024 * 1024; // 5 MB
const UPLOAD_ALLOWED_TYPES = ['.html', '.htm', '.png', '.jpg', '.jpeg'];

function getFileExtension(filename) {
    const dot = filename.lastIndexOf('.');
    return dot !== -1 ? filename.substring(dot).toLowerCase() : '';
}

function showUploadError(text) {
    const el = $('#uploadError');
    el.textContent = text;
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 6000);
}


function hideUploadError() {
    $('#uploadError').classList.add('hidden');
}

function setUploadSuccess(filename) {
    $('#uploadPrompt').classList.add('hidden');
    $('#uploadSuccess').classList.remove('hidden');
    $('#uploadFileName').textContent = filename;
    $('#uploadZone').classList.add('upload-done');
}

function clearUpload() {
    $('#uploadPrompt').classList.remove('hidden');
    $('#uploadSuccess').classList.add('hidden');
    $('#uploadFileName').textContent = '';
    $('#uploadZone').classList.remove('upload-done');
    $('#fileInput').value = '';
    hideUploadError();
}

function processFile(file) {
    hideUploadError();

    const ext = getFileExtension(file.name);
    if (!UPLOAD_ALLOWED_TYPES.includes(ext)) {
        showUploadError(`Invalid file type "${ext}". Accepted: ${UPLOAD_ALLOWED_TYPES.join(', ')}`);
        return;
    }
    if (file.size > UPLOAD_MAX_SIZE) {
        showUploadError(`File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum is 5 MB.`);
        return;
    }

    const isImage = ['.png', '.jpg', '.jpeg'].includes(ext);

    if (isImage) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const dataUrl = e.target.result;
            const mimeExt = ext === '.jpg' ? 'jpeg' : ext.substring(1);
            const base64Data = dataUrl.split(',')[1];
            const cardHtml = `<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<style>
  * { margin:0; padding:0; }
  body { width:1920px; height:1080px; overflow:hidden; background:#000; }
  img { width:100%; height:100%; object-fit:contain; }
</style>
</head><body>
<img src="data:image/${mimeExt};base64,${base64Data}" alt="Workout Card">
</body></html>`;
            $('#htmlContent').value = cardHtml;
            if (!$('#workoutTitle').value.trim()) {
                const title = file.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' ');
                $('#workoutTitle').value = title;
            }
            setUploadSuccess(file.name);
            $('#previewFrame').srcdoc = cardHtml;
            $('#previewModal').classList.remove('hidden');
        };
        reader.onerror = function() { showUploadError('Failed to read image file.'); };
        reader.readAsDataURL(file);
    } else {
        const reader = new FileReader();
        reader.onload = function(e) {
            const htmlText = e.target.result;
            $('#htmlContent').value = htmlText;
            const titleMatch = htmlText.match(/<title[^>]*>([^<]+)<\/title>/i);
            if (titleMatch && !$('#workoutTitle').value.trim()) {
                $('#workoutTitle').value = titleMatch[1].trim();
            }
            setUploadSuccess(file.name);
            $('#previewFrame').srcdoc = htmlText;
            $('#previewModal').classList.remove('hidden');
        };
        reader.onerror = function() { showUploadError('Failed to read HTML file.'); };
        reader.readAsText(file);
    }
}

// Browse button
$('#browseBtn').addEventListener('click', () => { $('#fileInput').click(); });

// File input change
$('#fileInput').addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) processFile(e.target.files[0]);
});

// Clear upload
$('#clearUploadBtn').addEventListener('click', clearUpload);

// Drag and drop
$('#uploadZone').addEventListener('dragover', (e) => {
    e.preventDefault(); e.stopPropagation();
    $('#uploadZone').classList.add('drag-active');
});
$('#uploadZone').addEventListener('dragleave', (e) => {
    e.preventDefault(); e.stopPropagation();
    $('#uploadZone').classList.remove('drag-active');
});
$('#uploadZone').addEventListener('drop', (e) => {
    e.preventDefault(); e.stopPropagation();
    $('#uploadZone').classList.remove('drag-active');
    if (e.dataTransfer.files && e.dataTransfer.files[0]) processFile(e.dataTransfer.files[0]);
});

// Reset upload state when form is reset
$('#scheduleForm').addEventListener('reset', () => { setTimeout(clearUpload, 0); });

// ── Canva Import ────────────────────────────────────────────────
function parseCanvaUrl(url) {
    if (!url) return null;
    const match = url.match(/https?:\/\/(?:www\.)?canva\.com\/design\/([A-Za-z0-9_-]+)/);
    return match ? match[1] : null;
}

function showCanvaError(text) {
    const el = $('#canvaError');
    el.textContent = text;
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 6000);
}

function hideCanvaError() {
    $('#canvaError').classList.add('hidden');
}

$('#canvaPreviewBtn').addEventListener('click', () => {
    const url = $('#canvaUrl').value.trim();
    hideCanvaError();

    if (!url) {
        showCanvaError('Please paste a Canva design URL.');
        return;
    }

    const designId = parseCanvaUrl(url);
    if (!designId) {
        showCanvaError('Invalid Canva URL. Expected format: https://www.canva.com/design/DAG.../view');
        return;
    }

    const embedUrl = `https://www.canva.com/design/${designId}/view?embed`;
    const frame = $('#canvaPreviewFrame');
    frame.src = embedUrl;
    $('#canvaPreviewArea').classList.remove('hidden');
});

$('#canvaImportBtn').addEventListener('click', () => {
    const url = $('#canvaUrl').value.trim();
    const designId = parseCanvaUrl(url);

    if (!designId) {
        showCanvaError('No valid Canva design loaded. Preview a design first.');
        return;
    }

    const embedUrl = `https://www.canva.com/design/${designId}/view?embed`;

    const cardHtml = `<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>*{margin:0;padding:0}body{width:1920px;height:1080px;overflow:hidden;background:#000}iframe{width:1920px;height:1080px;border:none}</style>
</head><body>
<iframe src="${embedUrl}" width="1920" height="1080" frameborder="0" allowfullscreen></iframe>
</body></html>`;

    $('#htmlContent').value = cardHtml;
    if (!$('#workoutTitle').value.trim()) {
        $('#workoutTitle').value = 'Canva Import';
    }

    const frame = $('#previewFrame');
    frame.srcdoc = cardHtml;
    $('#previewModal').classList.remove('hidden');

    $('#htmlContent').scrollIntoView({ behavior: 'smooth', block: 'center' });

    showMsg($('#formMessage'), 'Canva design imported. Review the card and push to schedule.', 'success');
});

// ── Schedule Form ──────────────────────────────────────────────
$('#scheduleForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = $('#formMessage');
    const entry = {
        schedule_date: $('#scheduleDate').value,
        board_type: $('#boardType').value,
        workout_title: $('#workoutTitle').value,
        workout_date_label: $('#workoutDateLabel').value || null,
        version: $('#version').value,
        html_content: $('#htmlContent').value,
        pushed_by: 'dashboard',
    };
    const body = { entries: [entry] };

    try {
        const res = await fetch(API, {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (res.ok) {
            showMsg(msg, `Scheduled ${entry.board_type} for ${entry.schedule_date}`, 'success');
            $('#scheduleForm').reset();
            $('#scheduleDate').value = today();
            loadCalendar();
            loadAuditLog();
        } else {
            showMsg(msg, data.detail || 'Error pushing schedule', 'error');
        }
    } catch (err) {
        showMsg(msg, `Network error: ${err.message}`, 'error');
    }
});

// Auto-set version based on board selection
$('#boardType').addEventListener('change', (e) => {
    $('#version').value = e.target.value === 'mainboard' ? 'rx' : 'mod';
});

// ── Calendar ───────────────────────────────────────────────────
async function loadCalendar() {
    const dates = getWeekDates(currentWeekOffset);
    const startDate = dates[0];
    const endDate = dates[6];
    const todayStr = today();

    // Update label
    const s = new Date(startDate + 'T12:00:00');
    const e = new Date(endDate + 'T12:00:00');
    $('#weekLabel').textContent = `${s.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} — ${e.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`;

    // Fetch schedule range
    let scheduleMap = {};
    try {
        const res = await fetch(`${API}?start=${startDate}&end=${endDate}`);
        const data = await res.json();
        if (data.entries) {
            data.entries.forEach(entry => {
                if (!scheduleMap[entry.schedule_date]) scheduleMap[entry.schedule_date] = [];
                scheduleMap[entry.schedule_date].push(entry);
            });
        }
    } catch { /* silent */ }

    // Render grid
    const grid = $('#calendarGrid');
    grid.innerHTML = '';
    const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

    dates.forEach((dateStr, i) => {
        const cell = document.createElement('div');
        cell.className = 'cal-day' + (dateStr === todayStr ? ' today' : '');
        const entries = scheduleMap[dateStr] || [];
        const entryHtml = entries.map(e =>
            `<div><span class="board-tag ${e.board_type}">${e.board_type}</span><br><small>${e.workout_title || '—'}</small></div>`
        ).join('');

        cell.innerHTML = `
            <div class="day-label">${dayNames[i]}</div>
            <div class="day-date">${formatDate(dateStr)}</div>
            ${entryHtml || '<small style="color:var(--text-muted)">No cards</small>'}
        `;
        grid.appendChild(cell);
    });
}

$('#prevWeek').addEventListener('click', () => { currentWeekOffset--; loadCalendar(); });
$('#nextWeek').addEventListener('click', () => { currentWeekOffset++; loadCalendar(); });

// ── Clone ──────────────────────────────────────────────────────
$('#cloneDayForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = $('#cloneDayMessage');
    const body = {
        source_date: $('#cloneSourceDate').value,
        target_date: $('#cloneTargetDate').value,
        board_type: $('#cloneBoard').value || null,
    };

    try {
        const res = await fetch(`${API}/clone`, {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (res.ok) {
            showMsg(msg, `Cloned ${data.cloned} card(s) to ${body.target_date}`, 'success');
            loadCalendar();
            loadAuditLog();
        } else {
            showMsg(msg, data.detail || 'Clone failed', 'error');
        }
    } catch (err) {
        showMsg(msg, `Network error: ${err.message}`, 'error');
    }
});

$('#cloneWeekForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = $('#cloneWeekMessage');
    const body = {
        source_week_start: $('#cloneSourceWeek').value,
        target_week_start: $('#cloneTargetWeek').value,
    };

    try {
        const res = await fetch(`${API}/clone-week`, {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (res.ok) {
            showMsg(msg, `Cloned ${data.cloned} card(s) across the week`, 'success');
            loadCalendar();
            loadAuditLog();
        } else {
            showMsg(msg, data.detail || 'Week clone failed', 'error');
        }
    } catch (err) {
        showMsg(msg, `Network error: ${err.message}`, 'error');
    }
});

// ── Override ───────────────────────────────────────────────────
$('#overrideForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = $('#overrideMessage');
    const body = {
        board_type: $('#overrideBoard').value,
        html_content: $('#overrideHtml').value,
        reason: $('#overrideReason').value,
    };

    try {
        const res = await fetch(`${API}/override`, {
            method: 'POST',
            headers: getApiHeaders(),
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (res.ok) {
            showMsg(msg, `Override applied to ${body.board_type}`, 'success');
            $('#overrideForm').reset();
            loadAuditLog();
        } else {
            showMsg(msg, data.detail || 'Override failed', 'error');
        }
    } catch (err) {
        showMsg(msg, `Network error: ${err.message}`, 'error');
    }
});

// ── Audit Log ──────────────────────────────────────────────────
async function loadAuditLog() {
    const filter = $('#auditFilter').value;
    const url = `${API}/audit` + (filter ? `?action=${filter}` : '');
    try {
        const res = await fetch(url);
        const data = await res.json();
        const list = $('#auditList');
        if (!data.entries || data.entries.length === 0) {
            list.innerHTML = '<p class="muted">No audit entries yet.</p>';
            return;
        }
        list.innerHTML = data.entries.map(e => `
            <div class="audit-entry">
                <div>
                    <span class="audit-action">${e.action}</span>
                    <div class="audit-detail">${e.board_type || ''} ${e.schedule_date || ''} ${e.details || ''}</div>
                </div>
                <span class="audit-time">${new Date(e.timestamp).toLocaleString()}</span>
            </div>
        `).join('');
    } catch {
        $('#auditList').innerHTML = '<p class="muted">Failed to load audit log.</p>';
    }
}

$('#auditFilter').addEventListener('change', loadAuditLog);
$('#refreshAudit').addEventListener('click', loadAuditLog);

// ── Live TV Monitor ─────────────────────────────────────────────
const MONITOR_REFRESH_MS = 60000;

async function refreshTVMonitor() {
    // Reload all TV iframes
    ['tv1Frame', 'tv2Frame', 'tv3Frame'].forEach(id => {
        const frame = document.getElementById(id);
        if (frame) frame.src = frame.src;
    });

    // Fetch status data
    try {
        const res = await fetch(`${API}/status`);
        const data = await res.json();

        updateTVInfo('tv1', data.mainboard, 'mainboard');
        updateTVInfo('tv2', data.modboard, 'modboard');
        updateTVInfo('tv3', data.mainboard, 'mainboard');

        // Update swap countdown
        if (data.next_swap_at) {
            updateSwapCountdown(data.next_swap_at);
            $('#nextSwap').textContent = new Date(data.next_swap_at).toLocaleString();
        }
    } catch {
        ['tv1', 'tv2', 'tv3'].forEach(tv => {
            document.getElementById(`${tv}Dot`).className = 'tv-status-dot offline';
            document.getElementById(`${tv}Title`).textContent = 'Connection Error';
            document.getElementById(`${tv}Meta`).textContent = '';
        });
        $('#nextSwap').textContent = '—';
    }
}

function updateTVInfo(tvId, cardData, boardType) {
    const dot = document.getElementById(`${tvId}Dot`);
    const title = document.getElementById(`${tvId}Title`);
    const meta = document.getElementById(`${tvId}Meta`);

    if (!dot || !title || !meta) return;

    if (cardData && cardData.status !== 'fallback') {
        const layer = cardData.fallback_layer || 1;
        if (layer === 1) {
            dot.className = 'tv-status-dot live';
        } else {
            dot.className = 'tv-status-dot fallback';
        }
        title.textContent = cardData.workout_title || 'Untitled Card';
        const status = cardData.status === 'overridden' ? 'overridden' : 'live';
        meta.textContent = `${cardData.version || '—'} · ${status}`;
    } else {
        dot.className = 'tv-status-dot fallback';
        title.textContent = 'No Card — Fallback Active';
        meta.textContent = 'splash screen';
    }
}

function updateSwapCountdown(nextSwapAt) {
    const next = new Date(nextSwapAt);
    const now = new Date();
    const diff = next - now;
    const timer = document.getElementById('swapTimer');
    if (!timer) return;
    if (diff > 0) {
        const hours = Math.floor(diff / 3600000);
        const mins = Math.floor((diff % 3600000) / 60000);
        timer.textContent = `${hours}h ${mins}m`;
    } else {
        timer.textContent = 'Now';
    }
}

// Dynamic iframe scaling via ResizeObserver
const tvScreens = document.querySelectorAll('.tv-screen');
const resizeObserver = new ResizeObserver(entries => {
    entries.forEach(entry => {
        const width = entry.contentRect.width;
        const scale = width / 1920;
        const iframe = entry.target.querySelector('iframe');
        if (iframe) {
            iframe.style.transform = `scale(${scale})`;
        }
    });
});
tvScreens.forEach(screen => resizeObserver.observe(screen));

// Click TV screen → full-size preview
document.querySelectorAll('.tv-screen').forEach(screen => {
    screen.addEventListener('click', () => {
        const iframe = screen.querySelector('iframe');
        if (iframe) {
            $('#previewFrame').src = iframe.src;
            $('#previewModal').classList.remove('hidden');
        }
    });
});

// Manual refresh button
if (document.getElementById('refreshMonitor')) {
    document.getElementById('refreshMonitor').addEventListener('click', refreshTVMonitor);
}

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Set default date to today
    $('#scheduleDate').value = today();

    checkTVStatus();
    loadTemplates();
    loadCalendar();
    loadAuditLog();
    refreshTVMonitor();

    // Refresh status every 30s
    setInterval(checkTVStatus, 30000);
    // Refresh TV monitors every 60s
    setInterval(refreshTVMonitor, MONITOR_REFRESH_MS);
});
