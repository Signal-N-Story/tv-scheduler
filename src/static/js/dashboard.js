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

// ── Next Swap Time ─────────────────────────────────────────────
async function updateNextSwap() {
    try {
        const res = await fetch(`${API}/status`);
        const data = await res.json();
        if (data.next_swap_at) {
            $('#nextSwap').textContent = new Date(data.next_swap_at).toLocaleString();
        }
    } catch {
        $('#nextSwap').textContent = '—';
    }
}

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Set default date to today
    $('#scheduleDate').value = today();

    checkTVStatus();
    loadTemplates();
    loadCalendar();
    loadAuditLog();
    updateNextSwap();

    // Refresh status every 30s
    setInterval(checkTVStatus, 30000);
});
