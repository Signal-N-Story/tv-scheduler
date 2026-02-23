/**
 * ARIZE TV Scheduler — Dashboard JavaScript
 */

const API = '/api/schedule';
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

// ── TV Status ──────────────────────────────────────────────────
async function checkTVStatus() {
    try {
        const res = await fetch('/tv/status');
        const data = await res.json();
        $('#statusDot').className = 'dot online';
        $('#statusText').textContent = `Online — ${data.active_boards || 0} board(s) active`;
    } catch {
        $('#statusDot').className = 'dot offline';
        $('#statusText').textContent = 'Offline';
    }
}

// ── Schedule Form ──────────────────────────────────────────────
$('#scheduleForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = $('#formMessage');
    const body = {
        schedule_date: $('#scheduleDate').value,
        board_type: $('#boardType').value,
        workout_title: $('#workoutTitle').value,
        workout_date_label: $('#workoutDateLabel').value,
        version: $('#version').value,
        html_content: $('#htmlContent').value,
        pushed_by: 'dashboard',
    };

    try {
        const res = await fetch(API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (res.ok) {
            showMsg(msg, `Scheduled ${body.board_type} for ${body.schedule_date}`, 'success');
            $('#scheduleForm').reset();
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
        const res = await fetch(`${API}?start_date=${startDate}&end_date=${endDate}`);
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
            headers: { 'Content-Type': 'application/json' },
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
        if (data.next_swap_time) {
            $('#nextSwap').textContent = new Date(data.next_swap_time).toLocaleString();
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
    loadCalendar();
    loadAuditLog();
    updateNextSwap();

    // Refresh status every 30s
    setInterval(checkTVStatus, 30000);
});
