"""
Веб-панель управления ботом CardGen.
Запуск: python panel.py
Открыть: http://localhost:5000
"""
import os
import sys
import sqlite3
import subprocess
import threading
from datetime import datetime
from flask import Flask, jsonify, request, render_template_string
from dotenv import load_dotenv

load_dotenv(override=True)

# Пути — всегда абсолютные относительно этого файла
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DB_PATH    = os.path.join(BASE_DIR, "data", "database.db")
BOT_SCRIPT = os.path.join(BASE_DIR, "main.py")

# Python из venv если есть, иначе текущий интерпретатор
_venv_python = os.path.join(BASE_DIR, "venv", "Scripts", "python.exe")
PYTHON = _venv_python if os.path.exists(_venv_python) else sys.executable

app = Flask(__name__)

bot_process: subprocess.Popen | None = None
bot_lock = threading.Lock()
bot_log_lines: list[str] = []
MAX_LOG_LINES = 300


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _log(line: str):
    ts = datetime.now().strftime("%H:%M:%S")
    bot_log_lines.append(f"[{ts}] {line}")
    if len(bot_log_lines) > MAX_LOG_LINES:
        del bot_log_lines[0]


def _stream_pipe(pipe, prefix=""):
    for line in pipe:
        bot_log_lines.append(prefix + line.rstrip())
        if len(bot_log_lines) > MAX_LOG_LINES:
            del bot_log_lines[0]


# ── HTML ──────────────────────────────────────────────────────────────────────

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CardGen Panel</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3e;
    --accent: #4f8ef7; --danger: #e05c5c; --success: #4caf7d;
    --warn: #e0a84a; --text: #d4d8f0; --muted: #7b7f9e;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; font-size: 14px; }
  header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 14px 24px;
           display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 18px; font-weight: 600; }
  .badge { padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
  .badge-on  { background: #1e3a2a; color: var(--success); }
  .badge-off { background: #3a1e1e; color: var(--danger); }
  .layout { display: grid; grid-template-columns: 320px 1fr; gap: 20px; padding: 20px 24px; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 18px; }
  .card h2 { font-size: 11px; text-transform: uppercase; letter-spacing: .6px;
             color: var(--muted); margin-bottom: 14px; }
  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px;
         padding: 9px 16px; border: none; border-radius: 7px; cursor: pointer;
         font-size: 13px; font-weight: 600; transition: opacity .15s; width: 100%; margin-bottom: 8px; }
  .btn:last-child { margin-bottom: 0; }
  .btn:hover { opacity: .82; } .btn:active { opacity: .65; }
  .btn-green { background: var(--success); color: #fff; }
  .btn-red   { background: var(--danger);  color: #fff; }
  .btn-blue  { background: var(--accent);  color: #fff; }
  .btn-gray  { background: #252838; color: var(--text); }
  .btn-sm    { width: auto; padding: 3px 10px; font-size: 11px; margin: 0; }
  .stat-row { display: flex; justify-content: space-between; align-items: center;
              padding: 9px 0; border-bottom: 1px solid var(--border); }
  .stat-row:last-child { border-bottom: none; }
  .stat-val { font-weight: 700; color: var(--accent); font-size: 15px; }
  input[type=number], input[type=text] {
    background: #12141e; border: 1px solid var(--border); border-radius: 6px;
    color: var(--text); padding: 8px 10px; width: 100%; font-size: 13px; margin-bottom: 8px;
  }
  input:focus { outline: none; border-color: var(--accent); }
  #log { background: #0a0c14; border: 1px solid var(--border); border-radius: 8px;
         padding: 12px; height: 280px; overflow-y: auto; font-family: monospace;
         font-size: 12px; line-height: 1.65; color: #9ba3c8; white-space: pre-wrap; word-break: break-all; }
  .log-err { color: var(--danger); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 8px 10px; color: var(--muted); font-weight: 600;
       border-bottom: 1px solid var(--border); font-size: 11px; text-transform: uppercase; }
  td { padding: 8px 10px; border-bottom: 1px solid #1e2130; vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #1e2235; }
  .tag { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
  .tag-admin   { background: #1e2a4a; color: var(--accent); }
  .tag-teacher { background: #2a1e3a; color: #b07aff; }
  .tag-student { background: #1e2e1e; color: var(--success); }
  .del-btn { background: none; border: none; color: var(--muted); cursor: pointer;
             font-size: 14px; padding: 3px 7px; border-radius: 4px; line-height: 1; }
  .del-btn:hover { background: #3a1e1e; color: var(--danger); }
  #toast { position: fixed; bottom: 24px; right: 24px; background: #1a1d27;
           border: 1px solid var(--border); border-radius: 8px; padding: 10px 18px;
           font-size: 13px; opacity: 0; transition: opacity .25s; pointer-events: none;
           box-shadow: 0 4px 20px rgba(0,0,0,.5); }
  #toast.show { opacity: 1; }
  .right-col { display: flex; flex-direction: column; gap: 20px; }
  #search-result div { padding: 6px 0; border-bottom: 1px solid var(--border); color: var(--text); }
  #search-result div:last-child { border: none; }
  code { background: #1e2130; padding: 1px 5px; border-radius: 3px; font-size: 11px; }
</style>
</head>
<body>

<header>
  <h1>CardGen Panel</h1>
  <span class="badge badge-off" id="status-badge">Проверка...</span>
</header>

<div class="layout">

  <div style="display:flex;flex-direction:column;gap:20px">

    <div class="card">
      <h2>Управление ботом</h2>
      <button class="btn btn-green" onclick="botAction('start')">&#9654; Запустить</button>
      <button class="btn btn-red"   onclick="botAction('stop')">&#9632; Остановить</button>
      <button class="btn btn-gray"  onclick="botAction('restart')">&#8635; Перезапустить</button>
    </div>

    <div class="card">
      <h2>Статистика</h2>
      <div id="stats"><div class="stat-row"><span>Загрузка...</span></div></div>
    </div>

    <div class="card">
      <h2>Удалить пользователя</h2>
      <input type="number" id="del-id" placeholder="Telegram ID">
      <button class="btn btn-red" onclick="deleteUser()">Удалить из БД</button>
    </div>

    <div class="card">
      <h2>Поиск</h2>
      <input type="text" id="search-q" placeholder="Имя или ID"
             onkeydown="if(event.key==='Enter')searchUser()">
      <button class="btn btn-blue" onclick="searchUser()">Найти</button>
      <div id="search-result"></div>
    </div>

  </div>

  <div class="right-col">

    <div class="card">
      <h2>Лог бота &nbsp;
        <button class="btn btn-gray btn-sm" onclick="clearLog()">очистить</button>
      </h2>
      <div id="log"></div>
    </div>

    <div class="card">
      <h2>Пользователи</h2>
      <div style="overflow-x:auto">
        <table>
          <thead>
            <tr><th>ID</th><th>Имя</th><th>Класс</th><th>Роль</th><th></th></tr>
          </thead>
          <tbody id="users-table">
            <tr><td colspan="5" style="color:var(--muted)">Загрузка...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>
</div>

<div id="toast"></div>

<script>
let toastTimer = null;
function toast(msg, ok=true) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.borderColor = ok ? 'var(--success)' : 'var(--danger)';
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3000);
}

async function api(url, opts={}) {
  try {
    const r = await fetch(url, { headers: {'Content-Type':'application/json'}, ...opts });
    return await r.json();
  } catch(e) {
    return { ok: false, message: 'Ошибка соединения' };
  }
}

async function botAction(action) {
  const data = await api('/api/bot/' + action, { method: 'POST' });
  toast(data.message, data.ok !== false);
  setTimeout(updateStatus, 1000);
}

async function updateStatus() {
  const data = await api('/api/bot/status');
  const badge = document.getElementById('status-badge');
  if (data.running) {
    badge.textContent = 'Работает';
    badge.className = 'badge badge-on';
  } else {
    badge.textContent = 'Остановлен';
    badge.className = 'badge badge-off';
  }
}

async function updateStats() {
  const data = await api('/api/stats');
  if (!data.rows) return;
  document.getElementById('stats').innerHTML = data.rows.map(r =>
    `<div class="stat-row"><span>${r.label}</span><span class="stat-val">${r.value}</span></div>`
  ).join('');
}

async function updateUsers() {
  const data = await api('/api/users');
  if (!data.users) return;
  const tbody = document.getElementById('users-table');
  if (!data.users.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="color:var(--muted)">Нет пользователей</td></tr>';
    return;
  }
  tbody.innerHTML = data.users.map(u => {
    const role = u.isAdmin   ? '<span class="tag tag-admin">Админ</span>'
               : u.isTeacher ? '<span class="tag tag-teacher">Учитель</span>'
               : '<span class="tag tag-student">Ученик</span>';
    return `<tr>
      <td style="color:var(--muted);font-size:11px">${u.id}</td>
      <td>${u.name}</td>
      <td>${u.cls || '—'}</td>
      <td>${role}</td>
      <td><button class="del-btn" onclick="deleteUserById(${u.id})" title="Удалить">&#x2715;</button></td>
    </tr>`;
  }).join('');
}

async function deleteUser() {
  const id = document.getElementById('del-id').value.trim();
  if (!id) { toast('Введи ID', false); return; }
  if (!confirm('Удалить пользователя ' + id + '?')) return;
  const data = await api('/api/users/' + id, { method: 'DELETE' });
  toast(data.message, data.ok);
  if (data.ok) { document.getElementById('del-id').value = ''; refresh(); }
}

async function deleteUserById(id) {
  if (!confirm('Удалить пользователя ' + id + '?')) return;
  const data = await api('/api/users/' + id, { method: 'DELETE' });
  toast(data.message, data.ok);
  if (data.ok) refresh();
}

function refresh() { updateUsers(); updateStats(); }

async function searchUser() {
  const q = document.getElementById('search-q').value.trim();
  if (!q) return;
  const data = await api('/api/users/search?q=' + encodeURIComponent(q));
  const el = document.getElementById('search-result');
  if (!data.users || !data.users.length) { el.innerHTML = '<div style="color:var(--muted)">Не найдено</div>'; return; }
  el.innerHTML = data.users.map(u =>
    `<div><b>${u.name}</b> (${u.cls || '—'}) <code>${u.id}</code>
     ${u.isAdmin ? '&#128081;' : u.isTeacher ? '&#128104;&#8205;&#127979;' : '&#128104;&#8205;&#127979;'}
     <button class="del-btn" onclick="deleteUserById(${u.id})" title="Удалить">&#x2715;</button></div>`
  ).join('');
}

let logOffset = 0;
async function updateLog() {
  const data = await api('/api/log?offset=' + logOffset);
  if (!data.lines || !data.lines.length) return;
  const el = document.getElementById('log');
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
  data.lines.forEach(line => {
    const div = document.createElement('div');
    if (line.includes('[ERR]') || line.includes('ERROR')) div.className = 'log-err';
    div.textContent = line;
    el.appendChild(div);
  });
  logOffset += data.lines.length;
  if (atBottom) el.scrollTop = el.scrollHeight;
}

function clearLog() {
  fetch('/api/log/clear', { method: 'POST' });
  document.getElementById('log').innerHTML = '';
  logOffset = 0;
}

updateStatus(); updateStats(); updateUsers(); updateLog();
setInterval(updateStatus, 3000);
setInterval(updateLog,    1500);
setInterval(updateStats, 10000);
setInterval(updateUsers, 15000);
</script>
</body>
</html>
"""


# ── API ───────────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return render_template_string(TEMPLATE)


@app.get("/api/bot/status")
def bot_status():
    with bot_lock:
        running = bot_process is not None and bot_process.poll() is None
    return jsonify(running=running)


def _do_start():
    """Запустить бота. Вызывать БЕЗ bot_lock."""
    global bot_process
    bot_log_lines.clear()
    proc = subprocess.Popen(
        [PYTHON, BOT_SCRIPT],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1, encoding="utf-8", errors="replace",
        cwd=BASE_DIR,
    )
    bot_process = proc
    threading.Thread(target=_stream_pipe, args=(proc.stdout, ""), daemon=True).start()
    threading.Thread(target=_stream_pipe, args=(proc.stderr, "[ERR] "), daemon=True).start()
    _log(f"Бот запущен (PID {proc.pid}, python: {PYTHON})")
    return proc.pid


def _do_stop():
    """Остановить бота. Вызывать БЕЗ bot_lock."""
    global bot_process
    if not bot_process or bot_process.poll() is not None:
        return False
    bot_process.terminate()
    try:
        bot_process.wait(timeout=6)
    except subprocess.TimeoutExpired:
        bot_process.kill()
    _log("Бот остановлен")
    bot_process = None
    return True


@app.post("/api/bot/start")
def bot_start():
    with bot_lock:
        if bot_process and bot_process.poll() is None:
            return jsonify(ok=False, message="Бот уже запущен")
        pid = _do_start()
    return jsonify(ok=True, message=f"Бот запущен (PID {pid})")


@app.post("/api/bot/stop")
def bot_stop():
    with bot_lock:
        stopped = _do_stop()
    if stopped:
        return jsonify(ok=True, message="Бот остановлен")
    return jsonify(ok=False, message="Бот не был запущен")


@app.post("/api/bot/restart")
def bot_restart():
    with bot_lock:
        _do_stop()
        pid = _do_start()
    return jsonify(ok=True, message=f"Бот перезапущен (PID {pid})")


@app.get("/api/stats")
def stats():
    load_dotenv(override=True)
    admin_ids = [x.strip() for x in os.getenv("ADMIN_ID", "").split(",") if x.strip()]
    conn = _db()
    cur = conn.cursor()
    rows = []
    try:
        cur.execute("SELECT COUNT(*) FROM Users WHERE isTeacher=0 AND isAdmin=0")
        rows.append({"label": "Учеников", "value": cur.fetchone()[0]})
        cur.execute("SELECT COUNT(*) FROM Users WHERE isTeacher=1")
        rows.append({"label": "Учителей", "value": cur.fetchone()[0]})
        rows.append({"label": "Администраторов (.env)", "value": len(admin_ids)})
        cur.execute("SELECT COUNT(*) FROM Grades")
        rows.append({"label": "Оценок в БД", "value": cur.fetchone()[0]})
        cur.execute("SELECT COUNT(*) FROM Events WHERE is_active=1")
        rows.append({"label": "Активных мероприятий", "value": cur.fetchone()[0]})
        cur.execute("SELECT COUNT(*) FROM Tickets WHERE status='open'")
        rows.append({"label": "Открытых обращений", "value": cur.fetchone()[0]})
        cur.execute("SELECT COUNT(*) FROM Announcements")
        rows.append({"label": "Объявлений всего", "value": cur.fetchone()[0]})
    finally:
        conn.close()
    return jsonify(rows=rows)


@app.get("/api/users")
def users_list():
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT ID, ФИ, class, isAdmin, isTeacher FROM Users ORDER BY isTeacher DESC, isAdmin DESC, ФИ")
        users = [
            {"id": r["ID"], "name": r["ФИ"], "cls": r["class"],
             "isAdmin": bool(r["isAdmin"]), "isTeacher": bool(r["isTeacher"])}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()
    return jsonify(users=users)


@app.get("/api/users/search")
def users_search():
    q = request.args.get("q", "").strip().lower()
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT ID, ФИ, class, isAdmin, isTeacher FROM Users")
        users = [
            {"id": r["ID"], "name": r["ФИ"], "cls": r["class"],
             "isAdmin": bool(r["isAdmin"]), "isTeacher": bool(r["isTeacher"])}
            for r in cur.fetchall()
            if q in r["ФИ"].lower() or q == str(r["ID"])
        ]
    finally:
        conn.close()
    return jsonify(users=users)


@app.delete("/api/users/<int:user_id>")
def delete_user(user_id: int):
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM Users WHERE ID = ?", (user_id,))
        conn.commit()
        deleted = cur.rowcount
    finally:
        conn.close()
    if deleted:
        _log(f"Удалён пользователь ID={user_id}")
        return jsonify(ok=True, message=f"Пользователь {user_id} удалён")
    return jsonify(ok=False, message="Пользователь не найден")


@app.get("/api/log")
def get_log():
    offset = int(request.args.get("offset", 0))
    return jsonify(lines=bot_log_lines[offset:])


@app.post("/api/log/clear")
def clear_log_api():
    bot_log_lines.clear()
    global logOffset
    return jsonify(ok=True)


if __name__ == "__main__":
    print("CardGen Panel: http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
