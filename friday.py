"""
FRIDAY - Iron Man Style AI Assistant
Fixed Version: Logic bugs resolved + FRIDAY personality integrated
"""

# ── Global flags ────────────────────────────────────────────────────────────
vmonitoring       = False
live_screen_mode  = False
live_screen_thread = None
last_screen_text  = ""
pending_system_command = None
OUTPUT_DIR = None

# ── Imports ─────────────────────────────────────────────────────────────────
import random, os, webbrowser, time, asyncio, json, threading, queue, subprocess
import re
import socket, uuid
import zipfile
import html, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timedelta
import psutil, pyautogui
import pygame
import pygetwindow as gw
import speech_recognition as sr
from PIL         import Image, ImageGrab
import pytesseract
import edge_tts

from api_config import client as api_client, chat_completion, GROQ_MODEL as api_model, get_client_info

try:
    from deep_learning import (
        DLCommandRouter, DLIntentClassifier, DLEmotionAnalyzer, DLImageAnalyzer,
        dl_classify, dl_emotion, dl_describe_image, dl_get_emotion_modifier,
        command_router as dl_router, dl_trainer, get_dl_status,
    )
    DL_AVAILABLE = True
except ImportError:
    DL_AVAILABLE = False
    print("[DL] deep_learning.py not found — DL features disabled.")

pywhatkit = None
pywhatkit_import_error = None

def get_pywhatkit():
    global pywhatkit, pywhatkit_import_error
    if pywhatkit is not None:
        return pywhatkit
    try:
        import pywhatkit as loaded_pywhatkit
        pywhatkit = loaded_pywhatkit
        pywhatkit_import_error = None
        return pywhatkit
    except Exception as e:
        pywhatkit_import_error = e
        print(f"[PYWHATKIT ERROR] {e}")
        return None

OUTPUT_DIR = os.path.abspath("friday_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

PHONE_REMOTE_PORT = 8765
PHONE_REMOTE_TOKEN_FILE = os.path.join(OUTPUT_DIR, "phone_remote_token.txt")
PHONE_REMOTE_LINK_FILE = os.path.join(OUTPUT_DIR, "phone_remote_link.txt")

def get_or_create_phone_remote_token(path=None):
    token_path = path or PHONE_REMOTE_TOKEN_FILE
    try:
        with open(token_path, "r", encoding="utf-8") as f:
            token = f.read().strip()
        if token:
            return token
    except Exception:
        pass
    token = uuid.uuid4().hex[:10]
    os.makedirs(os.path.dirname(token_path), exist_ok=True)
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(token)
    return token

PHONE_REMOTE_TOKEN = get_or_create_phone_remote_token()
PHONE_REMOTE_QUEUE = queue.Queue()
PHONE_REMOTE_LOG = []
PHONE_REMOTE_LOG_LOCK = threading.Lock()
phone_remote_server = None
phone_remote_worker_thread = None
LAST_CONTEXT_FILE = os.path.join(OUTPUT_DIR, "last_context.txt")
RESEARCH_MEMORY_FILE = os.path.join(OUTPUT_DIR, "research_memory.json")
TASKS_FILE = os.path.join(OUTPUT_DIR, "tasks.json")
COMMAND_HISTORY_FILE = os.path.join(OUTPUT_DIR, "command_history.jsonl")
FILE_INDEX_FILE = os.path.join(OUTPUT_DIR, "file_index.json")
DASHBOARD_FILE = os.path.join(OUTPUT_DIR, "friday_dashboard.html")
LAST_CONTEXT_TEXT = ""
LAST_CONTEXT_SOURCE = ""
AUTO_LEARN_DEFAULT_TOPICS = [
    "AI assistants",
    "Windows automation",
    "Python voice assistant",
    "OpenAI coding tools",
]
auto_learning_enabled = False
auto_learning_thread = None
auto_learning_topics = []
reminder_worker_enabled = False
reminder_worker_thread = None

def get_lan_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

def build_phone_remote_url(ip, port, token):
    return f"http://{ip}:{port}/?key={token}"

def get_phone_remote_url():
    return build_phone_remote_url(get_lan_ip(), PHONE_REMOTE_PORT, PHONE_REMOTE_TOKEN)

def write_phone_remote_link_file(url):
    with open(PHONE_REMOTE_LINK_FILE, "w", encoding="utf-8") as f:
        f.write(url + "\n")
    return PHONE_REMOTE_LINK_FILE

def add_phone_log(role, text, log=None, now=None):
    entry = {
        "role": str(role or "system"),
        "text": str(text or "").strip(),
        "time": now() if now else datetime.now().strftime("%I:%M %p"),
    }
    target_log = PHONE_REMOTE_LOG if log is None else log
    if log is None:
        with PHONE_REMOTE_LOG_LOCK:
            target_log.append(entry)
            del target_log[:-80]
    else:
        target_log.append(entry)
    return entry

def submit_phone_command(command, command_queue=None, log=None, now=None):
    text = str(command or "").strip()
    if not text:
        return {"ok": False, "message": "Command empty."}
    target_queue = PHONE_REMOTE_QUEUE if command_queue is None else command_queue
    target_queue.put(text)
    add_phone_log("user", text, log=log, now=now)
    return {"ok": True, "message": "Command sent to FRIDAY.", "command": text}

def build_phone_remote_page(token, remote_url):
    safe_url = html.escape(remote_url, quote=True)
    safe_token = urllib.parse.quote(token)
    token_json = json.dumps(token)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FRIDAY Phone Remote</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b0f14;
      --panel: #121922;
      --panel-2: #182230;
      --text: #edf3f8;
      --muted: #9fb0bf;
      --line: #263545;
      --accent: #28d7c3;
      --accent-2: #8fd46b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Segoe UI, Inter, Arial, sans-serif;
    }}
    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 18px 18px 12px;
      border-bottom: 1px solid var(--line);
      background: #0f151d;
      position: sticky;
      top: 0;
      z-index: 2;
    }}
    h1 {{ margin: 0; font-size: 22px; letter-spacing: 0; }}
    .sub {{ margin-top: 3px; color: var(--muted); font-size: 13px; }}
    .pill {{
      border: 1px solid rgba(40, 215, 195, 0.45);
      color: var(--accent);
      border-radius: 999px;
      padding: 7px 10px;
      font-size: 12px;
      white-space: nowrap;
    }}
    main {{
      width: min(760px, 100%);
      margin: 0 auto;
      padding: 16px;
      display: grid;
      gap: 14px;
    }}
    section {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      overflow: hidden;
    }}
    textarea {{
      width: 100%;
      min-height: 122px;
      resize: vertical;
      border: 0;
      outline: 0;
      padding: 16px;
      background: var(--panel);
      color: var(--text);
      font: 17px/1.45 Segoe UI, Inter, Arial, sans-serif;
    }}
    .controls, .quick {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      padding: 12px;
      border-top: 1px solid var(--line);
      background: var(--panel-2);
    }}
    .quick {{ grid-template-columns: repeat(2, minmax(0, 1fr)); border-top: 0; }}
    button {{
      min-height: 46px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #203040;
      color: var(--text);
      font: 600 15px Segoe UI, Inter, Arial, sans-serif;
    }}
    button.primary {{ background: var(--accent); color: #04100f; border-color: var(--accent); }}
    button.voice {{ background: #25333f; border-color: rgba(143, 212, 107, 0.55); }}
    button:disabled {{ opacity: 0.45; }}
    .log {{
      min-height: 210px;
      max-height: 44vh;
      overflow: auto;
      padding: 12px;
    }}
    .line {{
      display: grid;
      gap: 4px;
      padding: 10px 0;
      border-bottom: 1px solid rgba(255,255,255,0.06);
    }}
    .line:last-child {{ border-bottom: 0; }}
    .meta {{ color: var(--muted); font-size: 12px; }}
    .user .text {{ color: var(--accent-2); }}
    .friday .text {{ color: var(--accent); }}
    .text {{ overflow-wrap: anywhere; line-height: 1.4; }}
    .link {{
      color: var(--muted);
      font-size: 12px;
      padding: 0 2px 4px;
      overflow-wrap: anywhere;
    }}
    @media (min-width: 680px) {{
      .quick {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
      textarea {{ min-height: 150px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>FRIDAY Phone Remote</h1>
      <div class="sub">Laptop linked</div>
    </div>
    <div class="pill" id="status">Online</div>
  </header>
  <main>
    <div class="link">{safe_url}</div>
    <section>
      <textarea id="command" placeholder="open gmail"></textarea>
      <div class="controls">
        <button class="voice" id="voice">Start Voice</button>
        <button class="primary" id="send">Send</button>
      </div>
    </section>
    <section class="quick">
      <button data-command="open gmail">Gmail</button>
      <button data-command="open vs code">VS Code</button>
      <button data-command="tell me todays news">News</button>
      <button data-command="see my screen">Screen</button>
    </section>
    <section class="log" id="log"></section>
  </main>
  <script>
    const TOKEN = {token_json};
    const commandEndpoint = "/api/command?key={safe_token}";
    const statusEndpoint = "/api/status?key={safe_token}";
    const commandBox = document.getElementById("command");
    const sendButton = document.getElementById("send");
    const voiceButton = document.getElementById("voice");
    const statusPill = document.getElementById("status");
    const logBox = document.getElementById("log");

    async function sendCommand(text) {{
      const command = (text || commandBox.value || "").trim();
      if (!command) return;
      sendButton.disabled = true;
      try {{
        const res = await fetch(commandEndpoint, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ command }})
        }});
        const data = await res.json();
        statusPill.textContent = data.ok ? "Sent" : "Check";
        if (data.ok) commandBox.value = "";
        await loadStatus();
      }} catch (err) {{
        statusPill.textContent = "Offline";
      }} finally {{
        sendButton.disabled = false;
      }}
    }}

    function renderLog(items) {{
      logBox.innerHTML = "";
      for (const item of items.slice().reverse()) {{
        const row = document.createElement("div");
        row.className = "line " + (item.role || "system");
        row.innerHTML = `<div class="meta">${{item.time || ""}} - ${{item.role || "system"}}</div><div class="text"></div>`;
        row.querySelector(".text").textContent = item.text || "";
        logBox.appendChild(row);
      }}
    }}

    async function loadStatus() {{
      try {{
        const res = await fetch(statusEndpoint);
        const data = await res.json();
        if (data.ok) {{
          statusPill.textContent = "Online";
          renderLog(data.log || []);
        }}
      }} catch (err) {{
        statusPill.textContent = "Offline";
      }}
    }}

    sendButton.addEventListener("click", () => sendCommand());
    commandBox.addEventListener("keydown", (event) => {{
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) sendCommand();
    }});
    document.querySelectorAll("[data-command]").forEach((button) => {{
      button.addEventListener("click", () => sendCommand(button.dataset.command));
    }});

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {{
      voiceButton.disabled = true;
      voiceButton.textContent = "Voice N/A";
    }} else {{
      const recognition = new SpeechRecognition();
      recognition.lang = "en-IN";
      recognition.interimResults = false;
      recognition.onstart = () => voiceButton.textContent = "Listening";
      recognition.onend = () => voiceButton.textContent = "Start Voice";
      recognition.onresult = (event) => {{
        const text = event.results[0][0].transcript;
        commandBox.value = text;
        sendCommand(text);
      }};
      voiceButton.addEventListener("click", () => recognition.start());
    }}

    loadStatus();
    setInterval(loadStatus, 2500);
  </script>
</body>
</html>"""

class PhoneRemoteHandler(BaseHTTPRequestHandler):
    def _query(self):
        parsed = urllib.parse.urlparse(self.path)
        return parsed, urllib.parse.parse_qs(parsed.query)

    def _authorized(self, query):
        return query.get("key", [""])[0] == PHONE_REMOTE_TOKEN

    def _send_json(self, data, status=200):
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, data, status=200):
        raw = data.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed, query = self._query()
        if not self._authorized(query):
            self._send_html("<h1>FRIDAY remote locked</h1>", status=403)
            return
        if parsed.path == "/api/status":
            with PHONE_REMOTE_LOG_LOCK:
                log = list(PHONE_REMOTE_LOG[-80:])
            self._send_json({"ok": True, "online": True, "log": log})
            return
        if parsed.path in ["/", "/index.html"]:
            self._send_html(build_phone_remote_page(PHONE_REMOTE_TOKEN, get_phone_remote_url()))
            return
        self._send_json({"ok": False, "message": "Not found."}, status=404)

    def do_POST(self):
        parsed, query = self._query()
        if parsed.path != "/api/command":
            self._send_json({"ok": False, "message": "Not found."}, status=404)
            return
        if not self._authorized(query):
            self._send_json({"ok": False, "message": "Locked."}, status=403)
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        command = ""
        try:
            payload = json.loads(body or "{}")
            command = payload.get("command", "")
        except Exception:
            payload = urllib.parse.parse_qs(body)
            command = payload.get("command", [""])[0]
        self._send_json(submit_phone_command(command))

    def log_message(self, format, *args):
        return

def phone_remote_worker():
    while True:
        command = PHONE_REMOTE_QUEUE.get()
        try:
            execute(command)
        except Exception as e:
            add_phone_log("friday", f"Remote command failed: {e}")
            print(f"[PHONE REMOTE ERROR] {e}")
        finally:
            PHONE_REMOTE_QUEUE.task_done()

def start_phone_remote():
    global PHONE_REMOTE_PORT, phone_remote_server, phone_remote_worker_thread
    if phone_remote_server:
        return get_phone_remote_url()

    for port in range(PHONE_REMOTE_PORT, PHONE_REMOTE_PORT + 10):
        try:
            server = ThreadingHTTPServer(("0.0.0.0", port), PhoneRemoteHandler)
            PHONE_REMOTE_PORT = port
            phone_remote_server = server
            threading.Thread(target=server.serve_forever, daemon=True).start()
            if not phone_remote_worker_thread or not phone_remote_worker_thread.is_alive():
                phone_remote_worker_thread = threading.Thread(target=phone_remote_worker, daemon=True)
                phone_remote_worker_thread.start()
            url = get_phone_remote_url()
            write_phone_remote_link_file(url)
            add_phone_log("system", "Phone remote online.")
            print(f"[PHONE REMOTE] {url}")
            return url
        except OSError:
            continue

    raise RuntimeError("No free phone remote port found.")

def open_phone_remote_dashboard():
    try:
        url = start_phone_remote()
        open_in_chrome(url)
        return f"Phone remote opened, Boss. Link: {url}"
    except Exception as e:
        return f"Phone remote failed, Boss: {e}"

# ── Register Chrome as default browser for webbrowser module ────────────────
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
_chrome_available = os.path.exists(CHROME_PATH)
try:
    webbrowser.register(
        'chrome',
        None,
        webbrowser.BackgroundBrowser(CHROME_PATH)
    )
except Exception:
    _chrome_available = False

def open_in_chrome(url):
    """Open URL in Chrome. Falls back to default browser if Chrome not found."""
    try:
        if _chrome_available:
            webbrowser.get('chrome').open(url)
        elif os.path.exists(CHROME_PATH):
            subprocess.Popen([CHROME_PATH, url])
        else:
            webbrowser.open(url)
    except Exception:
        webbrowser.open(url)  # final fallback

def open_google_search(query):
    query = (query or "").strip()
    if not query:
        return "Search missing, Boss."
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
    open_in_chrome(url)
    return f"Searching {query}, Boss."

def write_news_page(items, title="FRIDAY News"):
    rows = []
    for index, item in enumerate(items, start=1):
        headline = html.escape(item.get("title", "Untitled"))
        link = html.escape(item.get("link", "#"), quote=True)
        rows.append(f'<li><a href="{link}" target="_blank">{headline}</a></li>')
    body = "\n".join(rows) if rows else "<li>No headlines found.</li>"
    page = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 32px; background: #0d1117; color: #e6edf3; }}
    h1 {{ font-size: 28px; }}
    li {{ margin: 14px 0; line-height: 1.45; }}
    a {{ color: #58a6ff; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .meta {{ color: #8b949e; margin-bottom: 24px; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="meta">Generated by FRIDAY at {datetime.now().strftime('%d %b %Y, %I:%M %p')}</div>
  <ol>{body}</ol>
</body>
</html>"""
    path = os.path.abspath("friday_news.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path

def fetch_news(topic=""):
    topic = (topic or "").strip()
    if topic:
        rss_url = (
            "https://news.google.com/rss/search?q="
            + urllib.parse.quote_plus(topic)
            + "&hl=en-IN&gl=IN&ceid=IN:en"
        )
        browser_url = "https://news.google.com/search?q=" + urllib.parse.quote_plus(topic)
        title = f"News: {topic}"
    else:
        rss_url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
        browser_url = "https://news.google.com/topstories?hl=en-IN&gl=IN&ceid=IN:en"
        title = "Top News"

    try:
        req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as response:
            xml_data = response.read()
        root_xml = ET.fromstring(xml_data)
        items = []
        for item in root_xml.findall(".//item")[:10]:
            items.append({
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
            })
        page_path = write_news_page(items, title)
        open_in_chrome(page_path)
        top = items[0]["title"] if items else "No headlines found"
        return f"News opened, Boss. Top: {top}"
    except Exception as e:
        print(f"[NEWS ERROR] {e}")
        open_in_chrome(browser_url)
        return "News opened in Chrome, Boss."

def extract_news_topic(command):
    topic = command
    for phrase in [
        "tell me todays news", "tell me today's news", "today news", "today's news",
        "latest news", "show news", "open news", "news headlines", "headlines",
        "tell me news", "read news", "news"
    ]:
        topic = topic.replace(phrase, "")
    topic = topic.replace("about", "").strip(" .")
    return topic

def open_weather(command):
    query = command.replace("weather", "").replace("temperature", "").strip()
    if not query:
        query = "weather near me"
    else:
        query = "weather " + query
    return open_google_search(query)

def current_time_reply():
    return datetime.now().strftime("Time is %I:%M %p, Boss.")

def current_date_reply():
    return datetime.now().strftime("Today is %d %B %Y, Boss.")

def extract_command_payload(command, prefixes):
    text = (command or "").strip()
    for prefix in prefixes:
        if text.startswith(prefix):
            return text[len(prefix):].strip(" :,-")
    return ""

def user_path_to_real_path(path_text):
    raw = (path_text or "").strip().strip('"').strip("'")
    home = os.path.expanduser("~")
    known = {
        "downloads": os.path.join(home, "Downloads"),
        "download": os.path.join(home, "Downloads"),
        "documents": os.path.join(home, "Documents"),
        "document": os.path.join(home, "Documents"),
        "desktop": os.path.join(home, "Desktop"),
        "pictures": os.path.join(home, "Pictures"),
        "photos": os.path.join(home, "Pictures"),
        "videos": os.path.join(home, "Videos"),
        "music": os.path.join(home, "Music"),
        "friday output": OUTPUT_DIR,
        "output": OUTPUT_DIR,
    }
    if raw.lower() in known:
        return known[raw.lower()]
    raw = os.path.expandvars(os.path.expanduser(raw))
    if os.path.isabs(raw):
        return os.path.abspath(raw)
    candidates = [
        os.path.abspath(raw),
        os.path.abspath(os.path.join(os.getcwd(), raw)),
        os.path.abspath(os.path.join(OUTPUT_DIR, raw)),
        os.path.abspath(os.path.join(home, raw)),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return os.path.abspath(raw)

def save_last_context(text, source):
    global LAST_CONTEXT_TEXT, LAST_CONTEXT_SOURCE
    LAST_CONTEXT_TEXT = str(text or "").strip()
    LAST_CONTEXT_SOURCE = str(source or "context").strip()
    with open(LAST_CONTEXT_FILE, "w", encoding="utf-8") as f:
        f.write(f"Source: {LAST_CONTEXT_SOURCE}\n\n{LAST_CONTEXT_TEXT}")
    return LAST_CONTEXT_TEXT

def read_docx_text(path):
    try:
        with zipfile.ZipFile(path) as docx:
            xml_data = docx.read("word/document.xml")
        root_xml = ET.fromstring(xml_data)
        parts = []
        for node in root_xml.iter():
            if node.tag.endswith("}t") and node.text:
                parts.append(node.text)
            elif node.tag.endswith("}p"):
                parts.append("\n")
        return " ".join("".join(parts).split())
    except Exception as e:
        return f"DOCX read failed: {e}"

def read_pdf_text(path):
    for module_name in ["pypdf", "PyPDF2"]:
        try:
            module = __import__(module_name)
            reader = module.PdfReader(path)
            pages = []
            for page in reader.pages[:12]:
                pages.append(page.extract_text() or "")
            return "\n".join(pages).strip()
        except Exception:
            continue
    return "PDF reading needs pypdf/PyPDF2 installed, Boss."

def read_xlsx_text(path, max_cells=300):
    try:
        with zipfile.ZipFile(path) as xlsx:
            shared = []
            if "xl/sharedStrings.xml" in xlsx.namelist():
                shared_root = ET.fromstring(xlsx.read("xl/sharedStrings.xml"))
                for item in shared_root.iter():
                    if item.tag.endswith("}t") and item.text:
                        shared.append(item.text)
            rows = []
            sheet_names = [name for name in xlsx.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")]
            for sheet_name in sheet_names[:3]:
                root_xml = ET.fromstring(xlsx.read(sheet_name))
                count = 0
                for cell in root_xml.iter():
                    if not cell.tag.endswith("}c"):
                        continue
                    value = None
                    cell_type = cell.attrib.get("t")
                    for child in cell:
                        if child.tag.endswith("}v") and child.text:
                            value = child.text
                            break
                    if value is None:
                        continue
                    if cell_type == "s":
                        try:
                            value = shared[int(value)]
                        except Exception:
                            pass
                    rows.append(str(value))
                    count += 1
                    if count >= max_cells:
                        break
            return " | ".join(rows) if rows else "No readable spreadsheet cells found."
    except Exception as e:
        return f"XLSX read failed: {e}"

def read_file_text(path, max_chars=18000):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        text = read_docx_text(path)
    elif ext == ".pdf":
        text = read_pdf_text(path)
    elif ext in [".xlsx", ".xlsm"]:
        text = read_xlsx_text(path)
    elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
        text = pytesseract.image_to_string(Image.open(path))
    else:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(max_chars)
        if ext in [".html", ".htm"]:
            text = re.sub(r"<script.*?</script>", " ", text, flags=re.I | re.S)
            text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
            text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())[:max_chars]

def summarize_folder(path, max_items=40):
    rows = []
    for name in os.listdir(path)[:max_items]:
        full = os.path.join(path, name)
        try:
            kind = "folder" if os.path.isdir(full) else "file"
            size = "" if os.path.isdir(full) else f"{os.path.getsize(full)} bytes"
            modified = datetime.fromtimestamp(os.path.getmtime(full)).strftime("%d %b %Y %I:%M %p")
            rows.append(f"{kind}: {name} {size} modified {modified}".strip())
        except Exception:
            rows.append(name)
    return "\n".join(rows) if rows else "Folder is empty."

def read_path_context(path_text):
    path = user_path_to_real_path(path_text)
    if not os.path.exists(path):
        return {"ok": False, "source": path, "text": "", "message": "Path not found, Boss."}
    if os.path.isdir(path):
        text = summarize_folder(path)
        source = path
    else:
        text = read_file_text(path)
        source = path
    save_last_context(text, source)
    return {"ok": True, "source": source, "text": text, "message": "Context loaded, Boss."}

def get_active_window_title():
    try:
        window = gw.getActiveWindow()
        return window.title if window else "active window"
    except Exception:
        return "active window"

def read_active_app_context():
    capture_screen()
    text = extract_text_from_screen()
    source = get_active_window_title()
    if not text:
        return {"ok": False, "source": source, "text": "", "message": "No readable text on screen, Boss."}
    save_last_context(text, source)
    return {"ok": True, "source": source, "text": text, "message": "Active app read, Boss."}

def get_clipboard_text():
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            text=True,
            capture_output=True,
            timeout=5,
        )
        return (result.stdout or "").strip()
    except Exception:
        return ""

def read_selected_file_context():
    before = get_clipboard_text()
    try:
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.4)
        copied = get_clipboard_text()
    except Exception:
        copied = ""
    candidates = [line.strip().strip('"') for line in copied.splitlines() if line.strip()]
    for candidate in candidates:
        if os.path.exists(candidate):
            return read_path_context(candidate)
    if before and os.path.exists(before.strip().strip('"')):
        return read_path_context(before.strip().strip('"'))
    return read_active_app_context()

def read_selected_text_context():
    try:
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.3)
        copied = get_clipboard_text()
    except Exception:
        copied = ""
    if copied and not os.path.exists(copied.strip().strip('"')):
        save_last_context(copied, "selected text")
        return {"ok": True, "source": "selected text", "text": copied, "message": "Selected text read, Boss."}
    return read_selected_file_context()

def summarize_context_text(text, source="context"):
    text = str(text or "").strip()
    if not text:
        return "No context loaded, Boss."
    return ask_ai(
        "Summarize this content in 4 short bullets. Source: "
        + source
        + "\n\nCONTENT:\n"
        + text[:7000],
        use_history=False,
    )

def answer_from_last_context(question):
    question = (question or "").strip()
    if not LAST_CONTEXT_TEXT:
        return "No context loaded, Boss. Say read current app or read file first."
    if not question:
        question = "summarize this"
    return ask_ai(
        "Answer using only this context. If the answer is not present, say it is not visible in the context.\n"
        + f"Source: {LAST_CONTEXT_SOURCE}\n"
        + f"Question: {question}\n\nContext:\n{LAST_CONTEXT_TEXT[:9000]}",
        use_history=False,
    )

def load_research_memory(path=None):
    target = path or RESEARCH_MEMORY_FILE
    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_research_memory(items, path=None):
    target = path or RESEARCH_MEMORY_FILE
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(items[-160:], f, indent=2)

def record_research_memory(topic, notes, path=None, now=None):
    entry = {
        "topic": (topic or "general").strip(),
        "notes": [str(note).strip() for note in notes if str(note).strip()][:12],
        "time": now() if now else datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    memory = load_research_memory(path)
    memory.append(entry)
    save_research_memory(memory, path)
    return entry

def fetch_google_news_items(topic, limit=8):
    topic = (topic or "").strip()
    rss_url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote_plus(topic or "technology")
        + "&hl=en-IN&gl=IN&ceid=IN:en"
    )
    req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=12) as response:
        xml_data = response.read()
    root_xml = ET.fromstring(xml_data)
    items = []
    for item in root_xml.findall(".//item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title:
            items.append({"title": title, "link": link})
    return items

def learn_about_topic(topic):
    topic = (topic or "").strip() or "AI assistants"
    try:
        items = fetch_google_news_items(topic)
        if not items:
            return "No new research found, Boss."
        headlines = [item["title"] for item in items]
        summary = ask_ai(
            "Turn these Google News headlines into concise learning notes for FRIDAY.\nTopic: "
            + topic
            + "\nHeadlines:\n"
            + "\n".join(headlines),
            use_history=False,
        )
        saved_notes = [summary] + headlines[:5]
        record_research_memory(topic, saved_notes)
        return f"Learned about {topic}, Boss."
    except Exception as e:
        print(f"[LEARN ERROR] {e}")
        return f"Could not learn now, Boss: {e}"

def auto_learning_worker(interval_seconds=900):
    global auto_learning_enabled
    while auto_learning_enabled:
        topics = auto_learning_topics or AUTO_LEARN_DEFAULT_TOPICS
        for topic in topics:
            if not auto_learning_enabled:
                break
            learn_about_topic(topic)
            time.sleep(3)
        for _ in range(max(1, interval_seconds // 5)):
            if not auto_learning_enabled:
                break
            time.sleep(5)

def start_auto_learning(topics=None, interval_seconds=900):
    global auto_learning_enabled, auto_learning_thread, auto_learning_topics
    if topics:
        auto_learning_topics = [topic.strip() for topic in topics if topic.strip()]
    elif not auto_learning_topics:
        auto_learning_topics = list(AUTO_LEARN_DEFAULT_TOPICS)
    if auto_learning_enabled and auto_learning_thread and auto_learning_thread.is_alive():
        return "Auto learning already running, Boss."
    auto_learning_enabled = True
    auto_learning_thread = threading.Thread(
        target=auto_learning_worker,
        kwargs={"interval_seconds": interval_seconds},
        daemon=True,
    )
    auto_learning_thread.start()
    return "Auto learning started, Boss."

def stop_auto_learning():
    global auto_learning_enabled
    auto_learning_enabled = False
    return "Auto learning stopped, Boss."

def learned_memory_answer(question=""):
    memory = load_research_memory()
    if not memory:
        return "Research memory empty, Boss."
    joined = "\n\n".join(
        f"{item.get('time')} | {item.get('topic')}: " + "; ".join(item.get("notes", [])[:5])
        for item in memory[-25:]
    )
    if not question:
        return summarize_context_text(joined, "research memory")
    return ask_ai(
        "Answer from FRIDAY research memory.\nQuestion: "
        + question
        + "\n\nResearch memory:\n"
        + joined[:9000],
        use_history=False,
    )

def handle_context_and_learning_command(command):
    text = (command or "").strip()

    if text in [
        "read current app", "read active app", "read current window", "read this app",
        "read file explorer", "read explorer", "read app", "read screen content",
    ]:
        result = read_active_app_context()
        return f"Read {result['source']}, Boss." if result["ok"] else result["message"]

    if text in ["read selected file", "read selected", "read selected item"]:
        result = read_selected_file_context()
        return f"Read {os.path.basename(result['source'])}, Boss." if result["ok"] else result["message"]

    if text in ["read selected text", "read selection", "read highlighted text", "read copied text"]:
        result = read_selected_text_context()
        return f"Read {result['source']}, Boss." if result["ok"] else result["message"]

    for prefix in ["read file ", "summarize file ", "read folder ", "summarize folder "]:
        if text.startswith(prefix):
            payload = extract_command_payload(text, [prefix])
            result = read_path_context(payload)
            if not result["ok"]:
                return result["message"]
            if prefix.startswith("summarize"):
                return summarize_context_text(result["text"], result["source"])
            return f"Loaded {os.path.basename(result['source'])}, Boss."

    if text in ["summarize current app", "summarize active app", "summarize this app"]:
        result = read_active_app_context()
        if not result["ok"]:
            return result["message"]
        return summarize_context_text(result["text"], result["source"])

    if text in ["summarize last context", "summarize this", "summarize what you read"]:
        return summarize_context_text(LAST_CONTEXT_TEXT, LAST_CONTEXT_SOURCE)

    for prefix in [
        "ask screen ", "ask app ", "ask this ", "ask context ", "question from screen ",
        "question about this ", "answer from screen ", "answer from app ",
    ]:
        if text.startswith(prefix):
            question = extract_command_payload(text, [prefix])
            if "screen" in prefix or "app" in prefix:
                read_active_app_context()
            return answer_from_last_context(question)

    if text.startswith("ask file ") and " about " in text:
        payload = extract_command_payload(text, ["ask file "])
        path_text, question = payload.split(" about ", 1)
        result = read_path_context(path_text)
        if not result["ok"]:
            return result["message"]
        return answer_from_last_context(question)

    if text in ["what did you read", "show last context", "last context"]:
        if not LAST_CONTEXT_TEXT:
            return "No context loaded, Boss."
        print("[LAST CONTEXT]", LAST_CONTEXT_SOURCE)
        print(LAST_CONTEXT_TEXT[:3000])
        return f"Last context is {LAST_CONTEXT_SOURCE}, Boss."

    for prefix in ["learn about ", "google learn about ", "research ", "google research "]:
        if text.startswith(prefix):
            return learn_about_topic(extract_command_payload(text, [prefix]))

    for prefix in ["start learning about ", "start auto learning about ", "start google learning about "]:
        if text.startswith(prefix):
            topic_text = extract_command_payload(text, [prefix])
            topics = [part.strip() for part in re.split(r",| and ", topic_text) if part.strip()]
            return start_auto_learning(topics)

    if text in ["start learning", "start auto learning", "start google learning"]:
        return start_auto_learning()

    if text in ["stop learning", "stop auto learning", "stop google learning"]:
        return stop_auto_learning()

    if text in ["what have you learned", "show learned memory", "research memory", "learned memory"]:
        return learned_memory_answer()

    for prefix in ["ask learned ", "ask research ", "question from research "]:
        if text.startswith(prefix):
            return learned_memory_answer(extract_command_payload(text, [prefix]))

    return None

def log_history(kind, text, path=None, now=None):
    target = path or COMMAND_HISTORY_FILE
    entry = {
        "type": str(kind or "event"),
        "text": str(text or "").strip(),
        "time": now() if now else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=True) + "\n")
    return entry

def load_history(path=None, limit=80):
    target = path or COMMAND_HISTORY_FILE
    if not os.path.exists(target):
        return []
    items = []
    with open(target, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    return items[-limit:]

def load_tasks(path=None):
    target = path or TASKS_FILE
    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_tasks(tasks, path=None):
    target = path or TASKS_FILE
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)

def parse_due_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(str(value), fmt)
        except Exception:
            continue
    return None

def parse_reminder_command(command, now=None):
    now = now or datetime.now()
    text = (command or "").strip().lower()
    match = re.search(r"remind me in\s+(\d+)\s+(minute|minutes|hour|hours|day|days)\s+to\s+(.+)", text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        task_text = match.group(3).strip()
        if "hour" in unit:
            due_dt = now + timedelta(hours=amount)
        elif "day" in unit:
            due_dt = now + timedelta(days=amount)
        else:
            due_dt = now + timedelta(minutes=amount)
        return {"text": task_text, "due": due_dt.strftime("%Y-%m-%d %H:%M")}

    match = re.search(r"remind me at\s+(.+?)\s+to\s+(.+)", text)
    if match:
        time_text = match.group(1).strip().replace(".", "")
        task_text = match.group(2).strip()
        due_time = None
        for fmt in ["%H:%M", "%I:%M %p", "%I %p"]:
            try:
                due_time = datetime.strptime(time_text.upper(), fmt).time()
                break
            except Exception:
                continue
        if due_time:
            due_dt = datetime.combine(now.date(), due_time)
            if due_dt < now:
                due_dt += timedelta(days=1)
            return {"text": task_text, "due": due_dt.strftime("%Y-%m-%d %H:%M")}

    return None

def add_task(text, due="", path=None):
    tasks = load_tasks(path)
    task = {
        "id": uuid.uuid4().hex[:8],
        "text": str(text or "").strip(),
        "due": str(due or "").strip(),
        "done": False,
        "notified": False,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    tasks.append(task)
    save_tasks(tasks, path)
    return task

def mark_task_done(task_id_or_number, path=None):
    tasks = load_tasks(path)
    target = str(task_id_or_number or "").strip().lower()
    changed = False
    for index, task in enumerate(tasks, start=1):
        if target in [str(index), str(task.get("id", "")).lower()]:
            task["done"] = True
            changed = True
            break
    save_tasks(tasks, path)
    return changed

def get_due_tasks(now=None, path=None):
    now = now or datetime.now()
    due = []
    for task in load_tasks(path):
        if task.get("done") or task.get("notified"):
            continue
        due_dt = parse_due_datetime(task.get("due"))
        if due_dt and due_dt <= now:
            due.append(task)
    return due

def mark_tasks_notified(task_ids, path=None):
    ids = set(task_ids)
    tasks = load_tasks(path)
    for task in tasks:
        if task.get("id") in ids:
            task["notified"] = True
    save_tasks(tasks, path)

def reminder_worker():
    while reminder_worker_enabled:
        try:
            due = get_due_tasks()
            if due:
                for task in due:
                    speak("Reminder: " + task.get("text", "task"))
                mark_tasks_notified([task.get("id") for task in due])
        except Exception as e:
            print(f"[REMINDER ERROR] {e}")
        time.sleep(20)

def start_reminder_worker():
    global reminder_worker_enabled, reminder_worker_thread
    if reminder_worker_enabled and reminder_worker_thread and reminder_worker_thread.is_alive():
        return
    reminder_worker_enabled = True
    reminder_worker_thread = threading.Thread(target=reminder_worker, daemon=True)
    reminder_worker_thread.start()

def build_task_summary(tasks=None):
    tasks = load_tasks() if tasks is None else tasks
    active = [task for task in tasks if not task.get("done")]
    if not active:
        return "No active tasks, Boss."
    lines = []
    for index, task in enumerate(active[:12], start=1):
        due = f" at {task.get('due')}" if task.get("due") else ""
        lines.append(f"{index}. {task.get('text')}{due}")
    return "Tasks: " + " | ".join(lines)

INDEX_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", ".csv",
    ".xml", ".yml", ".yaml", ".ini", ".bat", ".ps1", ".docx", ".xlsx",
}

def build_file_index(root_text, max_files=90, max_chars_per_file=1800):
    root_path = user_path_to_real_path(root_text)
    items = []
    if not os.path.isdir(root_path):
        return {"root": root_path, "items": []}
    ignored_dirs = {"__pycache__", ".git", "node_modules", "dist", "build", ".venv", "venv"}
    for current, dirs, files in os.walk(root_path):
        dirs[:] = [name for name in dirs if name not in ignored_dirs]
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in INDEX_EXTENSIONS:
                continue
            full = os.path.join(current, filename)
            try:
                text = read_file_text(full, max_chars=max_chars_per_file)
                items.append({
                    "name": filename,
                    "path": full,
                    "text": text[:max_chars_per_file],
                    "modified": datetime.fromtimestamp(os.path.getmtime(full)).strftime("%Y-%m-%d %H:%M"),
                })
            except Exception as e:
                items.append({"name": filename, "path": full, "text": f"Read failed: {e}", "modified": ""})
            if len(items) >= max_files:
                break
        if len(items) >= max_files:
            break
    return {"root": root_path, "items": items, "built": datetime.now().strftime("%Y-%m-%d %H:%M")}

def save_file_index(index, path=None):
    target = path or FILE_INDEX_FILE
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    return target

def load_file_index(path=None):
    target = path or FILE_INDEX_FILE
    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {"root": "", "items": []}
    except Exception:
        return {"root": "", "items": []}

def search_file_index(index, query, limit=8):
    terms = [term for term in re.findall(r"[a-zA-Z0-9_]+", (query or "").lower()) if len(term) > 1]
    scored = []
    for item in index.get("items", []):
        haystack = (item.get("name", "") + " " + item.get("path", "") + " " + item.get("text", "")).lower()
        score = sum(haystack.count(term) for term in terms)
        if score:
            row = dict(item)
            row["score"] = score
            scored.append(row)
    scored.sort(key=lambda row: row.get("score", 0), reverse=True)
    return scored[:limit]

def ask_file_index(question):
    index = load_file_index()
    if not index.get("items"):
        return "No file index, Boss. Say index folder downloads first."
    matches = search_file_index(index, question, limit=6)
    if not matches:
        return "No matching indexed files, Boss."
    context = "\n\n".join(
        f"FILE: {item.get('path')}\n{item.get('text', '')[:1600]}"
        for item in matches
    )
    return ask_ai(
        "Answer from these indexed files. Mention file names if useful.\n"
        + f"Question: {question}\n\n{context}",
        use_history=False,
    )

def build_file_search_result_text(results):
    if not results:
        return "No matches, Boss."
    print("[FILE SEARCH RESULTS]")
    for item in results:
        print(item.get("path"))
    names = ", ".join(item.get("name", "file") for item in results[:4])
    return "Found: " + names

def build_dashboard_html(tasks=None, research=None, history=None, phone_url=""):
    tasks = load_tasks() if tasks is None else tasks
    research = load_research_memory() if research is None else research
    history = load_history(limit=40) if history is None else history
    phone_url = phone_url or get_phone_remote_url()

    def esc(value):
        return html.escape(str(value or ""))

    task_rows = "\n".join(
        f"<li><b>{esc(task.get('text'))}</b><span>{esc(task.get('due'))}</span></li>"
        for task in tasks[-20:] if not task.get("done")
    ) or "<li>No active tasks.</li>"
    research_rows = "\n".join(
        f"<li><b>{esc(item.get('topic'))}</b><p>{esc('; '.join(item.get('notes', [])[:3]))}</p></li>"
        for item in research[-12:]
    ) or "<li>No research yet.</li>"
    history_rows = "\n".join(
        f"<li><span>{esc(item.get('time'))}</span><b>{esc(item.get('type'))}</b> {esc(item.get('text'))}</li>"
        for item in history[-30:]
    ) or "<li>No history yet.</li>"

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FRIDAY Dashboard</title>
  <style>
    body {{ margin: 0; background: #0b0f14; color: #edf3f8; font-family: Segoe UI, Arial, sans-serif; }}
    header {{ padding: 22px 24px; border-bottom: 1px solid #243241; background: #101821; }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 20px; display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }}
    section {{ border: 1px solid #263545; border-radius: 8px; background: #121922; padding: 16px; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    ul {{ margin: 0; padding-left: 18px; }}
    li {{ margin: 10px 0; line-height: 1.4; }}
    span {{ color: #9fb0bf; margin-left: 8px; font-size: 12px; }}
    a {{ color: #28d7c3; overflow-wrap: anywhere; }}
    p {{ margin: 6px 0 0; color: #bdc8d3; }}
  </style>
</head>
<body>
  <header><h1>FRIDAY Dashboard</h1><p>{esc(datetime.now().strftime('%d %b %Y %I:%M %p'))}</p></header>
  <main>
    <section><h2>Phone Remote</h2><a href="{esc(phone_url)}">{esc(phone_url)}</a></section>
    <section><h2>Active Tasks</h2><ul>{task_rows}</ul></section>
    <section><h2>Research Memory</h2><ul>{research_rows}</ul></section>
    <section><h2>Recent History</h2><ul>{history_rows}</ul></section>
  </main>
</body>
</html>"""

def open_friday_dashboard():
    page = build_dashboard_html()
    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(page)
    open_in_chrome(DASHBOARD_FILE)
    return "Dashboard opened, Boss."

def handle_next_level_command(command):
    text = (command or "").strip()

    parsed = parse_reminder_command(text)
    if parsed:
        add_task(parsed["text"], parsed["due"])
        return f"Reminder set for {parsed['due']}, Boss."

    for prefix in ["add task ", "new task ", "todo "]:
        if text.startswith(prefix):
            task_text = extract_command_payload(text, [prefix])
            add_task(task_text)
            return "Task added, Boss."

    if text in ["list tasks", "show tasks", "today tasks", "my tasks"]:
        return build_task_summary()

    for prefix in ["complete task ", "finish task ", "done task "]:
        if text.startswith(prefix):
            target = extract_command_payload(text, [prefix])
            return "Task completed, Boss." if mark_task_done(target) else "Task not found, Boss."

    for prefix in ["index folder ", "scan folder ", "index files in ", "scan files in "]:
        if text.startswith(prefix):
            folder = extract_command_payload(text, [prefix])
            index = build_file_index(folder)
            save_file_index(index)
            return f"Indexed {len(index.get('items', []))} files, Boss."

    for prefix in ["search files for ", "find in files ", "search indexed files for "]:
        if text.startswith(prefix):
            query = extract_command_payload(text, [prefix])
            return build_file_search_result_text(search_file_index(load_file_index(), query))

    for prefix in ["ask files ", "ask indexed files ", "question from files "]:
        if text.startswith(prefix):
            return ask_file_index(extract_command_payload(text, [prefix]))

    if text in ["open dashboard", "friday dashboard", "open friday dashboard", "show dashboard"]:
        return open_friday_dashboard()

    if text in ["command history", "show command history", "what did i say"]:
        history = load_history(limit=10)
        if not history:
            return "History empty, Boss."
        print("[COMMAND HISTORY]")
        for item in history:
            print(item)
        return "History printed, Boss."

    return None

def open_special_target(command):
    name = command.replace("open", "", 1).strip().lower()
    home = os.path.expanduser("~")
    targets = {
        "downloads": os.path.join(home, "Downloads"),
        "download": os.path.join(home, "Downloads"),
        "documents": os.path.join(home, "Documents"),
        "document": os.path.join(home, "Documents"),
        "desktop": os.path.join(home, "Desktop"),
        "pictures": os.path.join(home, "Pictures"),
        "photos": os.path.join(home, "Pictures"),
        "videos": os.path.join(home, "Videos"),
        "music": os.path.join(home, "Music"),
        "settings": "ms-settings:",
        "windows settings": "ms-settings:",
        "control panel": "control",
        "recycle bin": "shell:RecycleBinFolder",
        "this pc": "shell:MyComputerFolder",
        "my computer": "shell:MyComputerFolder",
    }
    target = targets.get(name)
    if not target:
        return None
    try:
        os.startfile(target)
        return f"Opened {name}, Boss."
    except Exception as e:
        return f"Could not open {name}, Boss: {e}"

CONTACTS_FILE = os.path.join(OUTPUT_DIR, "email_contacts.json")

def load_email_contacts():
    try:
        with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_email_contacts(contacts):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=2)

def add_email_contact(command):
    text = command
    for prefix in ["add email contact", "save email contact", "remember email contact"]:
        text = text.replace(prefix, "", 1).strip()
    match = re.search(r"(.+?)\s+(?:as|is)\s+([\w.\-+]+@[\w.\-]+\.\w+)", text)
    if not match:
        return "Format: add email contact name as email, Boss."
    name = match.group(1).strip().lower()
    email = match.group(2).strip()
    contacts = load_email_contacts()
    contacts[name] = email
    save_email_contacts(contacts)
    return f"Saved {name}, Boss."

def resolve_email_target(name_or_email):
    target = (name_or_email or "").strip().lower()
    if "@" in target:
        return target
    contacts = load_email_contacts()
    return contacts.get(target, target)

def open_email():
    open_in_chrome("https://mail.google.com/mail/u/0/#inbox")
    return "Gmail opened, Boss."

def compose_email(to="", subject="", body=""):
    to = resolve_email_target(to)
    url = (
        "https://mail.google.com/mail/?view=cm&fs=1"
        + "&to=" + urllib.parse.quote(to or "")
        + "&su=" + urllib.parse.quote(subject or "")
        + "&body=" + urllib.parse.quote(body or "")
    )
    open_in_chrome(url)
    return "Email draft opened, Boss."

def parse_email_command(command):
    text = command.strip()
    if text in [
        "open email", "open gmail", "open mail", "my email kholo", "email kholo",
        "gmail kholo", "mail kholo", "email khol", "gmail khol", "mail khol",
        "meri email kholo", "meri email khol", "apni email kholo", "apni email khol",
    ]:
        return {"action": "open_email"}
    if text.startswith(("add email contact", "save email contact", "remember email contact")):
        return {"action": "add_contact", "command": text}
    if text in ["send email", "send mail"]:
        return {"action": "ask_send"}
    if text in ["confirm send email", "confirm send mail"]:
        return {"action": "confirm_send"}

    if "email" not in text and "mail" not in text:
        return None

    cleaned = text
    for prefix in ["compose email to", "write email to", "draft email to", "send email to", "mail to", "email to"]:
        if cleaned.startswith(prefix):
            cleaned = cleaned.replace(prefix, "", 1).strip()
            break
    else:
        return None

    subject = ""
    body = ""
    recipient = cleaned

    if " subject " in cleaned:
        recipient, rest = cleaned.split(" subject ", 1)
        if " body " in rest:
            subject, body = rest.split(" body ", 1)
        elif " saying " in rest:
            subject, body = rest.split(" saying ", 1)
        else:
            subject = rest
    elif " body " in cleaned:
        recipient, body = cleaned.split(" body ", 1)
    elif " saying " in cleaned:
        recipient, body = cleaned.split(" saying ", 1)
    elif " message " in cleaned:
        recipient, body = cleaned.split(" message ", 1)

    if not body and recipient:
        body = ask_ai("Write a short email body for: " + text, use_history=False)

    return {
        "action": "compose",
        "to": recipient.strip(),
        "subject": subject.strip(),
        "body": body.strip(),
    }

def handle_email_command(command):
    parsed = parse_email_command(command)
    if not parsed:
        return None
    action = parsed["action"]
    if action == "open_email":
        return open_email()
    if action == "add_contact":
        return add_email_contact(parsed["command"])
    if action == "ask_send":
        return "Say confirm send email, Boss."
    if action == "confirm_send":
        pyautogui.hotkey("ctrl", "enter")
        return "Send triggered, Boss."
    if action == "compose":
        return compose_email(parsed.get("to"), parsed.get("subject"), parsed.get("body"))
    return None

COMPILER_URLS = {
    "python": "https://www.programiz.com/python-programming/online-compiler/",
    "javascript": "https://www.programiz.com/javascript/online-compiler/",
    "js": "https://www.programiz.com/javascript/online-compiler/",
    "html": "https://www.programiz.com/html/online-compiler/",
    "java": "https://www.programiz.com/java-programming/online-compiler/",
    "c": "https://www.programiz.com/c-programming/online-compiler/",
    "cpp": "https://www.programiz.com/cpp-programming/online-compiler/",
    "c++": "https://www.programiz.com/cpp-programming/online-compiler/",
}

def detect_language(text):
    text = (text or "").lower()
    for lang in ["python", "javascript", "html", "java", "c++", "cpp", "c"]:
        if lang in text:
            return lang
    return "python"

def open_online_compiler(language="python"):
    language = detect_language(language)
    open_in_chrome(COMPILER_URLS.get(language, COMPILER_URLS["python"]))
    return f"{language} compiler opened, Boss."

def generate_code(task, language="python"):
    language = detect_language(language or task)
    prompt = f"""
Write complete runnable {language} code for this task.
Return code only. No markdown. No explanation.
Task: {task}
"""
    try:
        res = chat_completion(
            messages=[
                {"role": "system", "content": "Return complete runnable code only."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1400,
            temperature=0.2,
        )
        if res is None:
            return "# Code generation failed, Boss."
        code = res.choices[0].message.content.strip()
        code = re.sub(r"^```[\w+-]*\s*", "", code)
        code = re.sub(r"\s*```$", "", code)
        return code.strip()
    except Exception as e:
        print(f"[CODE GEN ERROR] {e}")
        return f"# Code generation failed: {e}"

def code_extension(language):
    language = detect_language(language)
    return {
        "python": ".py",
        "javascript": ".js",
        "js": ".js",
        "html": ".html",
        "java": ".java",
        "c": ".c",
        "cpp": ".cpp",
        "c++": ".cpp",
    }.get(language, ".txt")

def save_generated_code(task, language="python", filename=""):
    language = detect_language(language or task)
    code = generate_code(task, language)
    if not filename:
        filename = sanitize_filename(task[:40] or "friday_code", "friday_code" + code_extension(language))
        filename = os.path.splitext(filename)[0] + code_extension(language)
    path = resolve_output_path(filename, "friday_code" + code_extension(language))
    with open(path, "w", encoding="utf-8") as f:
        f.write(code + "\n")
    os.startfile(path)
    return f"Code file created, Boss: {os.path.basename(path)}"

def paste_generated_code(task, language="python"):
    code = generate_code(task, language)
    return type_into_active_window(code)

def handle_code_command(command):
    text = command.strip()
    if "compiler" in text and ("open" in text or "online" in text or "khol" in text or "kholo" in text):
        return open_online_compiler(detect_language(text))
    if "online compiler" in text:
        return open_online_compiler(detect_language(text))

    starters = [
        "write code for", "write python code for", "write javascript code for",
        "code for", "code a", "make code for", "generate code for",
        "python code for", "javascript code for"
    ]
    for starter in starters:
        if text.startswith(starter):
            task = text.replace(starter, "", 1).strip()
            return paste_generated_code(task or text, detect_language(text))

    if "code" in text and any(word in text for word in ["likh", "likho", "bana", "banao", "write"]):
        return paste_generated_code(text, detect_language(text))

    file_starters = [
        "create code file for", "create python file for", "make python file for",
        "save code for", "create program for"
    ]
    for starter in file_starters:
        if text.startswith(starter):
            task = text.replace(starter, "", 1).strip()
            return save_generated_code(task or text, detect_language(text))

    if text.startswith("open compiler and code "):
        task = text.replace("open compiler and code", "", 1).strip()
        language = detect_language(task)
        open_online_compiler(language)
        time.sleep(4)
        return paste_generated_code(task, language)

    return None

def sanitize_filename(name, default="friday_note.txt"):
    name = (name or "").strip().strip('"').strip("'")
    if not name:
        name = default
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    if "." not in os.path.basename(name):
        name += ".txt"
    return name

def resolve_output_path(path_text, default="friday_note.txt"):
    path_text = (path_text or "").strip().strip('"').strip("'")
    if not path_text:
        path_text = default
    if os.path.isabs(path_text):
        path = os.path.abspath(path_text)
    else:
        path = os.path.abspath(os.path.join(OUTPUT_DIR, sanitize_filename(path_text, default)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path

def set_clipboard_text(text):
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
            input=str(text),
            text=True,
            capture_output=True,
            timeout=8,
        )
        return True
    except Exception as e:
        print(f"[CLIPBOARD ERROR] {e}")
        return False

def type_into_active_window(text):
    text = str(text or "").strip()
    if not text:
        return "Text missing, Boss."
    if set_clipboard_text(text):
        pyautogui.hotkey("ctrl", "v")
    else:
        pyautogui.write(text, interval=0.02)
    return "Typed, Boss."

def create_text_file(path_text, content):
    path = resolve_output_path(path_text)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(content or "").strip() + "\n")
    os.startfile(path)
    return f"File created, Boss: {os.path.basename(path)}"

def append_text_file(path_text, content):
    path = resolve_output_path(path_text)
    with open(path, "a", encoding="utf-8") as f:
        f.write(str(content or "").strip() + "\n")
    os.startfile(path)
    return f"File updated, Boss: {os.path.basename(path)}"

def open_path_target(path_text):
    target = (path_text or "").strip().strip('"').strip("'")
    if not target:
        return "Path missing, Boss."
    known = open_special_target("open " + target)
    if known:
        return known
    expanded = os.path.expandvars(os.path.expanduser(target))
    if os.path.exists(expanded):
        os.startfile(expanded)
        return "Opened, Boss."
    return open_google_search(target)

def list_folder(path_text=""):
    target = (path_text or "").strip().strip('"').strip("'")
    if not target:
        target = os.getcwd()
    target = os.path.expandvars(os.path.expanduser(target))
    if not os.path.isdir(target):
        return "Folder not found, Boss."
    names = os.listdir(target)[:12]
    print("[FOLDER LIST]", target)
    for name in names:
        print(name)
    return "Listed folder, Boss: " + ", ".join(names[:4])

def create_interface_window(topic, content=""):
    topic = (topic or "FRIDAY Panel").strip()
    if not content:
        content = ask_ai(
            "Create concise useful content for a simple local interface about: " + topic,
            use_history=False,
        )
    safe_title = html.escape(topic)
    safe_content = html.escape(content).replace("\n", "<br>")
    page = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{safe_title}</title>
  <style>
    body {{ margin:0; font-family:Segoe UI,Arial,sans-serif; background:#080b10; color:#f4f7fb; }}
    header {{ padding:18px 24px; background:#101826; border-bottom:1px solid #233044; }}
    h1 {{ margin:0; font-size:24px; color:#7dd3fc; }}
    main {{ padding:24px; line-height:1.55; font-size:17px; }}
    .panel {{ max-width:900px; border:1px solid #233044; padding:20px; background:#0f172a; }}
  </style>
</head>
<body>
  <header><h1>{safe_title}</h1></header>
  <main><div class="panel">{safe_content}</div></main>
</body>
</html>"""
    filename = sanitize_filename(topic, "friday_interface.html").rsplit(".", 1)[0] + ".html"
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    open_in_chrome(path)
    return "Interface opened, Boss."

def extract_json_object(text):
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception as e:
        print(f"[PLAN JSON ERROR] {e}: {text}")
        return None

def plan_action_with_ai(command):
    prompt = f"""
Convert the user's command into ONE JSON object. Return JSON only.

Available actions:
- open_app: app
- open_website: url_or_name
- search_web: query
- news: topic
- weather: location
- open_path: path
- list_folder: path
- type_text: text
- create_file: path, content
- append_file: path, content
- make_interface: topic, content
- run_command: command
- open_email
- compose_email: to, subject, body
- add_email_contact: name, email
- open_compiler: language
- write_code: language, task
- create_code_file: language, task, filename
- read_screen
- analyze_screen
- click_text: text
- press_key: key
- chat: message

Rules:
- Prefer actions over chat.
- If user asks to write/type into current app, use type_text.
- If user asks to make a window/interface/page, use make_interface.
- If user asks current/latest/today information, use search_web or news.
- If user asks email/mail, use open_email or compose_email.
- If user asks coding/program/compiler, use open_compiler, write_code, or create_code_file.
- Keep fields short.

User command: {command}
"""
    try:
        res = chat_completion(
            messages=[{"role": "system", "content": "Return JSON only."}, {"role": "user", "content": prompt}],
            max_tokens=220,
            temperature=0.1,
        )
        if res is None:
            return None
        raw = res.choices[0].message.content.strip()
        print("[AI PLAN]", raw)
        return extract_json_object(raw)
    except Exception as e:
        print(f"[AI PLAN ERROR] {e}")
        return None

def execute_action_plan(plan, original_command=""):
    if not isinstance(plan, dict):
        return None
    action = str(plan.get("action", "")).strip().lower()
    if action == "open_app":
        return open_app_by_name(plan.get("app") or plan.get("target") or original_command)
    if action == "open_website":
        return open_website_by_name(plan.get("url_or_name") or plan.get("url") or plan.get("site") or original_command)
    if action == "search_web":
        return open_google_search(plan.get("query") or original_command)
    if action == "news":
        return fetch_news(plan.get("topic") or "")
    if action == "weather":
        location = plan.get("location") or ""
        return open_google_search(("weather " + location).strip())
    if action == "open_path":
        return open_path_target(plan.get("path") or plan.get("target") or "")
    if action == "list_folder":
        return list_folder(plan.get("path") or "")
    if action == "type_text":
        return type_into_active_window(plan.get("text") or "")
    if action == "create_file":
        return create_text_file(plan.get("path") or "friday_note.txt", plan.get("content") or "")
    if action == "append_file":
        return append_text_file(plan.get("path") or "friday_note.txt", plan.get("content") or "")
    if action == "make_interface":
        return create_interface_window(plan.get("topic") or original_command, plan.get("content") or "")
    if action == "run_command":
        return run_local_command(plan.get("command") or "")
    if action == "open_email":
        return open_email()
    if action == "compose_email":
        return compose_email(plan.get("to") or "", plan.get("subject") or "", plan.get("body") or "")
    if action == "add_email_contact":
        name = plan.get("name") or plan.get("contact") or ""
        email = plan.get("email") or ""
        if name and email:
            contacts = load_email_contacts()
            contacts[name.lower()] = email
            save_email_contacts(contacts)
            return f"Saved {name}, Boss."
        return "Contact missing, Boss."
    if action == "open_compiler":
        return open_online_compiler(plan.get("language") or "python")
    if action == "write_code":
        return paste_generated_code(plan.get("task") or original_command, plan.get("language") or "")
    if action == "create_code_file":
        return save_generated_code(
            plan.get("task") or original_command,
            plan.get("language") or "",
            plan.get("filename") or "",
        )
    if action == "read_screen":
        return extract_text_from_screen()[:300] or "No text, Boss."
    if action == "analyze_screen":
        return analyze_screen_with_ai()
    if action == "click_text":
        target = plan.get("text") or plan.get("target") or ""
        return f"Clicked {target}, Boss." if find_and_click_element(target) else f"Not found, Boss."
    if action == "press_key":
        key = plan.get("key") or ""
        pyautogui.press(key)
        return f"Pressed {key}, Boss."
    if action == "chat":
        return ask_ai(plan.get("message") or original_command, use_history=True)
    return None

def open_app_by_name(app):
    app = (app or "").replace("open", "", 1).strip().lower()
    if not app:
        return "App missing, Boss."
    if app in ["code", "vs code", "vscode", "visual studio code"]:
        return open_code()
    configured_path = app_paths.get(app)
    if configured_path:
        try:
            os.startfile(configured_path)
            return f"Opened {app}, Boss."
        except Exception as e:
            return f"Open failed, Boss: {e}"
    try:
        os.startfile(app)
        return f"Opened {app}, Boss."
    except Exception:
        try:
            subprocess.Popen(app)
            return f"Opened {app}, Boss."
        except Exception:
            return open_google_search(app)

def open_code():
    project_dir = os.path.abspath(os.getcwd())
    friday_file = os.path.join(project_dir, "friday.py")
    try:
        if CODE_EXE_PATH and os.path.exists(CODE_EXE_PATH):
            subprocess.Popen([CODE_EXE_PATH, project_dir, friday_file])
            return "Code opened, Boss."
        if CODE_CMD_PATH and os.path.exists(CODE_CMD_PATH):
            subprocess.Popen([CODE_CMD_PATH, "-r", project_dir, friday_file], shell=True)
            return "Code opened, Boss."
        subprocess.Popen(["cmd", "/c", "start", "", "code", "-r", project_dir, friday_file])
        return "Code opened, Boss."
    except Exception as e:
        print(f"[CODE OPEN ERROR] {e}")
        try:
            os.startfile(project_dir)
            return "Project folder opened, Boss."
        except Exception as inner:
            return f"Code failed, Boss: {inner}"

def open_website_by_name(site):
    site = (site or "").replace("open website", "", 1).strip().lower()
    if not site:
        return "Website missing, Boss."
    url = website_urls.get(site, f"https://www.{site}.com" if "." not in site else f"https://{site}")
    open_in_chrome(url)
    return f"Opened {site}, Boss."

def handle_direct_ultimate_command(command):
    if command.startswith("write "):
        return type_into_active_window(command.split("write ", 1)[1])
    if command.startswith("type "):
        return type_into_active_window(command.split("type ", 1)[1])
    if command.startswith("create file "):
        payload = command.split("create file ", 1)[1]
        if " with " in payload:
            path, content = payload.split(" with ", 1)
        else:
            path, content = payload, ""
        return create_text_file(path, content)
    if command.startswith("append file "):
        payload = command.split("append file ", 1)[1]
        if " with " in payload:
            path, content = payload.split(" with ", 1)
            return append_text_file(path, content)
    if command.startswith("open folder "):
        return open_path_target(command.split("open folder ", 1)[1])
    if command.startswith("open file "):
        return open_path_target(command.split("open file ", 1)[1])
    if command.startswith("list folder"):
        return list_folder(command.replace("list folder", "", 1).strip())
    if command.startswith("make interface ") or command.startswith("create interface "):
        topic = command.replace("make interface", "", 1).replace("create interface", "", 1).strip()
        return create_interface_window(topic)
    if command.startswith("make window ") or command.startswith("create window "):
        topic = command.replace("make window", "", 1).replace("create window", "", 1).strip()
        return create_interface_window(topic)
    return None

def ai_execute_task(command):
    direct = handle_direct_ultimate_command(command)
    if direct:
        return direct
    plan = plan_action_with_ai(command)
    result = execute_action_plan(plan, command)
    return result

from overlay        import update_text, root
from status_overlay import update_status, create_status_overlay

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

pygame.mixer.init()

# ── API client ─────────────────────────────────────────────────────────────
api_provider = "groq"
if api_client is None:
    print(f"[API] Groq not available. FRIDAY will have limited functionality.")

VOICE       = "en-IN-NeerjaNeural"   # Change to a US female voice if you want more FRIDAY feel
MEMORY_FILE = "memory.json"

voice_queue  = queue.Queue()
stop_speaking = False

live_mode          = False
latest_frame_path  = None

_last_alert_time = 0
_ALERT_COOLDOWN  = 15          # seconds between spoken screen alerts
_screen_lock     = threading.Lock()   # FIX: thread-safe last_screen_text access

# ── FRIDAY system prompt (Iron Man movie accurate) ───────────────────────────
FRIDAY_SYSTEM_PROMPT = """You are FRIDAY — Tony Stark's AI from Iron Man movies.

PERSONALITY RULES (strict):
- Address user as "Boss" always
- Responses are SHORT, precise, intelligent — never more than 2-3 sentences
- Calm, confident, zero drama
- Never say "I'm just an AI" or "I cannot" — always find a way or state the limitation technically
- Minimal sarcasm, only when contextually perfect (movie level)
- No emojis, no filler words, no "Certainly!", no "Of course!"
- Technical language preferred
- If asked something personal/emotional: brief, logical, move on

EXAMPLE RESPONSES:
User: "how are you"       → "Systems nominal, Boss."
User: "what can you do"   → "Full system control, web access, screen analysis, and whatever else you need, Boss."
User: "tell me a joke"    → "I'm an AI, Boss. Comedy isn't in my primary directives — but I can try."
User: "thanks"            → "Always, Boss."
User: "who made you"      → "A developer with good taste, Boss."

Execute every reasonable request. Stay in character at all times."""

# ── App paths ────────────────────────────────────────────────────────────────
def first_existing_path(*paths):
    for path in paths:
        if path and os.path.exists(path):
            return path
    return None

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
APPDATA = os.environ.get("APPDATA", "")
PROGRAMFILES = os.environ.get("PROGRAMFILES", r"C:\Program Files")
PROGRAMFILES_X86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
CODE_EXE_PATH = first_existing_path(
    os.path.join(LOCALAPPDATA, "Programs", "Microsoft VS Code", "Code.exe"),
    os.path.join(PROGRAMFILES, "Microsoft VS Code", "Code.exe"),
)
CODE_CMD_PATH = first_existing_path(
    os.path.join(LOCALAPPDATA, "Programs", "Microsoft VS Code", "bin", "code.cmd"),
    os.path.join(LOCALAPPDATA, "Programs", "Microsoft VS Code", "bin", "code"),
)

app_paths = {
    "notepad":       r"C:\Windows\System32\notepad.exe",
    "calculator":    r"C:\Windows\System32\calc.exe",
    "paint":         r"C:\Windows\System32\mspaint.exe",
    "code":          CODE_EXE_PATH,
    "vs code":       CODE_EXE_PATH,
    "vscode":        CODE_EXE_PATH,
    "visual studio code": CODE_EXE_PATH,
    "chrome":        first_existing_path(
        CHROME_PATH,
        os.path.join(PROGRAMFILES_X86, "Google", "Chrome", "Application", "chrome.exe"),
    ),
    "edge":          first_existing_path(
        os.path.join(PROGRAMFILES_X86, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(PROGRAMFILES, "Microsoft", "Edge", "Application", "msedge.exe"),
    ),
    "spotify":       first_existing_path(
        os.path.join(APPDATA, "Spotify", "Spotify.exe"),
        os.path.join(LOCALAPPDATA, "Microsoft", "WindowsApps", "Spotify.exe"),
    ),
    "whatsapp":      first_existing_path(
        os.path.join(LOCALAPPDATA, "WhatsApp", "WhatsApp.exe"),
        os.path.join(LOCALAPPDATA, "Microsoft", "WindowsApps", "WhatsApp.exe"),
    ),
    "discord":       first_existing_path(
        os.path.join(LOCALAPPDATA, "Discord", "Update.exe"),
        os.path.join(LOCALAPPDATA, "Microsoft", "WindowsApps", "Discord.exe"),
    ),
    "task manager":  r"C:\Windows\System32\Taskmgr.exe",
    "file explorer": r"C:\Windows\explorer.exe",
}

website_urls = {
    "google":       "https://www.google.com",
    "youtube":      "https://www.youtube.com",
    "facebook":     "https://www.facebook.com",
    "twitter":      "https://www.twitter.com",
    "github":       "https://www.github.com",
    "youtube music":"https://music.youtube.com",
    "spotify":      "https://www.spotify.com",
    "netflix":      "https://www.netflix.com",
    "amazon":       "https://www.amazon.com",
    "linkedin":     "https://www.linkedin.com",
    "gmail":        "https://mail.google.com",
    "gemini":       "https://gemini.google.com",
    "chat gpt":     "https://chat.openai.com",
    "reddit":       "https://www.reddit.com",
    "instagram":    "https://www.instagram.com",
    "whatsapp web": "https://web.whatsapp.com",
    "telegram":     "https://web.telegram.org",
    "bing":         "https://www.bing.com",
    "yahoo":        "https://www.yahoo.com",
    "duckduckgo":   "https://duckduckgo.com",
    "stackoverflow":"https://stackoverflow.com",
}

# ── Auto-correct misheard commands ──────────────────────────────────────────
def correct_command(command):
    corrections = {
        "start monitoring":  ["startmonitoring","start monitoor","begin monitoring","start monitering"],
        "stop monitoring":   ["stop monitor","end monitoring","stop monitoor"],
        "see my screen":     ["show my screen","capture my screen"],
        "what's on my screen":["what is on my screen","analyze my screen"],
        "remember that":     ["save that in memory","store that"],
        "what do you remember":["recall memory","what's in your memory"],
        "clear memory":      ["forget everything","reset memory","clear your memory"],
        "stop music":        ["pause music","stop video","pause video"],
        "resume music":      ["play music","resume video","play video"],
        "close tab":         ["close this tab","close current tab","close website"],
        "close application": ["close app","exit app","quit app"],
        "start live screen": [
            "start live monitoring","begin screen monitoring","watch my screen",
            "start live screen mode","activate live screen","turn on live screen",
            "start screen control","enable live screen"
        ],
        "stop live screen":  [
            "stop live monitoring","end screen monitoring","stop watching",
            "stop live screen mode","deactivate live screen","turn off live screen",
            "stop screen control","disable live screen"
        ],
        "analyze screen":    ["analyze this screen","analyze my screen","screen analysis"],
        "summarize screen":  ["give me screen summary","summarize this screen","screen summary"],
        "read my screen":    ["read screen text","what's on my screen"],
    }
    for key, variants in corrections.items():
        if key in command:
            continue
        for variant in variants:
            if variant in command:
                command = command.replace(variant, key)
    return command

# ── AI (Groq + FRIDAY personality) ──────────────────────────────────────────
# FIX: Removed hardcoded personality_basic / personality_mood / personality_traits
# Those were intercepting commands before Groq, causing wrong responses.
# Now ALL responses go through Groq with FRIDAY system prompt.
# Only exception: pure offline fallback if Groq fails.

_conversation_history = []   # FIX: maintain multi-turn context

FRIDAY_SYSTEM_PROMPT += (
    "\n\nOVERRIDE: Keep every reply ultra short. "
    "Default to one sentence and 4-12 words. "
    "Do not explain unless Boss asks for details."
)

def ask_ai(prompt, use_history=False):
    """
    Send prompt to Groq with FRIDAY system prompt.
    use_history=True for conversational turns, False for one-shot tasks.
    """
    global _conversation_history

    try:
        if use_history:
            _conversation_history.append({"role": "user", "content": prompt})
            messages = [{"role": "system", "content": FRIDAY_SYSTEM_PROMPT}] + _conversation_history[-10:]
        else:
            messages = [
                {"role": "system", "content": FRIDAY_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt}
            ]

        if api_client is None:
            return "API not configured, Boss."
        res = chat_completion(messages, max_tokens=80, temperature=0.4)
        if res is None:
            return "API error, Boss."
        reply = res.choices[0].message.content.strip()

        if use_history:
            _conversation_history.append({"role": "assistant", "content": reply})
            if len(_conversation_history) > 20:
                _conversation_history = _conversation_history[-20:]

        return reply

    except Exception as e:
        print(f"[AI ERROR] {e}")
        return "Systems experiencing interference, Boss. Try again."

# ── Text change detector ─────────────────────────────────────────────────────
def _text_changed_significantly(old_text, new_text, threshold=0.15):
    if not old_text and not new_text:
        return False
    old_words = set(old_text.lower().split())
    new_words = set(new_text.lower().split())
    total = max(len(old_words), len(new_words))
    if total == 0:
        return False
    diff = len(old_words.symmetric_difference(new_words))
    return (diff / total) > threshold

# ── Voice ────────────────────────────────────────────────────────────────────
async def generate_voice(text):
    file = f"voice_{time.time()}.mp3"
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(file)
    return file

def voice_worker():
    global stop_speaking
    while True:
        text = voice_queue.get()
        if text is None:
            break
        file = None
        try:
            stop_speaking = False
            file = asyncio.run(generate_voice(text))
            pygame.mixer.music.load(file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                if stop_speaking:
                    pygame.mixer.music.stop()
                    break
                time.sleep(0.1)
        except Exception as e:
            print(f"[VOICE ERROR] {e}")
        finally:
            # Always mark task done so voice_queue.join() can unblock
            voice_queue.task_done()
            # Safe delete after unload
            if file and os.path.exists(file):
                try:
                    pygame.mixer.music.unload()
                    os.remove(file)
                except Exception:
                    pass

threading.Thread(target=voice_worker, daemon=True).start()

def short_voice_text(text, max_words=14, max_chars=130):
    clean = str(text).replace("\n", " ").strip()
    if not clean:
        return ""
    words = clean.split()
    if len(words) > max_words:
        clean = " ".join(words[:max_words]).rstrip(".,;:") + "."
    if len(clean) > max_chars:
        clean = clean[:max_chars].rsplit(" ", 1)[0].rstrip(".,;:") + "."
    return clean

def speak(text):
    print("FRIDAY:", text)
    print("-" * 50)
    clean = short_voice_text(text)
    log_history("speech", clean)
    add_phone_log("friday", clean)
    update_text(clean)
    voice_queue.put(clean)

# ── Screen functions ─────────────────────────────────────────────────────────
def capture_screen():
    try:
        img = ImageGrab.grab()
        img.save("live_screen.png")
        return True
    except Exception as e:
        print(f"[SCREEN CAPTURE ERROR] {e}")
        return False

def extract_text_from_screen():
    try:
        if os.path.exists("live_screen.png"):
            img  = Image.open("live_screen.png")
            text = pytesseract.image_to_string(img)
            return text.strip()
        print("[OCR] live_screen.png not found.")
        return ""
    except Exception as e:
        print(f"[OCR ERROR] {e}")
        return ""

def detect_ui_elements():
    try:
        if not os.path.exists("live_screen.png"):
            return []
        img       = Image.open("live_screen.png")
        text_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        elements  = []
        for i, text in enumerate(text_data['text']):
            if text.strip():
                x, y, w, h = (text_data['left'][i], text_data['top'][i],
                              text_data['width'][i], text_data['height'][i])
                conf_raw = text_data['conf'][i]
                conf     = int(conf_raw) if str(conf_raw) != '-1' else 0
                if conf > 30:
                    elements.append({
                        'text':       text.strip().lower(),
                        'bbox':       (x, y, x + w, y + h),
                        'center':     (x + w // 2, y + h // 2),
                        'confidence': conf
                    })
        return elements
    except Exception as e:
        print(f"[UI DETECT ERROR] {e}")
        return []

def find_and_click_element(element_text):
    elements = detect_ui_elements()
    for element in elements:
        if element_text.lower() in element['text']:
            x, y = element['center']
            pyautogui.moveTo(x, y, duration=0.3)
            pyautogui.click()
            return True
    return False

def find_and_type_in_field(field_text, text_to_type):
    elements = detect_ui_elements()
    for element in elements:
        if field_text.lower() in element['text']:
            x, y = element['center']
            pyautogui.moveTo(x, y, duration=0.3)
            pyautogui.click()
            time.sleep(0.5)
            pyautogui.write(text_to_type, interval=0.05)
            return True
    return False

def analyze_screen_with_ai():
    text = extract_text_from_screen()
    if text:
        return ask_ai(f"Analyze this screen content briefly: {text[:500]}")
    return "No readable content on screen, Boss."

def analyze_screen_with_ai_for_action(command):
    text     = extract_text_from_screen()
    elements = detect_ui_elements()
    element_list = "\n".join([f"- '{e['text']}'" for e in elements[:10]])
    context = (
        f"Screen content (first 300 chars): {text[:300]}\n"
        f"Detected UI elements:\n{element_list}\n\n"
        f"User command: {command}\n\n"
        "Determine ONE action. Reply ONLY in this exact format:\n"
        "ACTION: [click|type|press|open|navigate]\n"
        "TARGET: [element name or key]\n"
        "TEXT: [text to type, blank if not typing]\n"
        "CONFIDENCE: [high|medium|low]\n"
        "If undetermined: CANNOT_DETERMINE"
    )
    try:
        return parse_action_response(ask_ai(context))
    except Exception as e:
        print(f"[ACTION PARSE ERROR] {e}")
        return {"action": "none", "target": "", "text": "", "confidence": "low"}

def parse_action_response(response):
    action_data = {"action": "none", "target": "", "text": "", "confidence": "low"}
    for line in response.split('\n'):
        stripped = line.strip()
        lower    = stripped.lower()
        if lower.startswith('action:'):
            action_data['action']     = lower.replace('action:', '').strip()
        elif lower.startswith('target:'):
            action_data['target']     = lower.replace('target:', '').strip()
        elif lower.startswith('confidence:'):
            action_data['confidence'] = lower.replace('confidence:', '').strip()
        elif stripped.upper().startswith('TEXT:'):
            action_data['text']       = stripped[5:].strip()   # preserve case
    return action_data

def execute_screen_action(action_data):
    action = action_data['action']
    target = action_data['target']
    text   = action_data['text']
    if action == 'click':
        return f"Clicked on {target}, Boss." if find_and_click_element(target) else f"Element '{target}' not found, Boss."
    elif action == 'type':
        return f"Typed in {target}, Boss."   if find_and_type_in_field(target, text) else f"Field '{target}' not found, Boss."
    elif action == 'press':
        try:
            pyautogui.press(target)
            return f"Pressed {target}, Boss."
        except Exception as e:
            return f"Key error: {e}"
    return "Action not recognised, Boss."

# ── Live screen monitor ──────────────────────────────────────────────────────
def live_screen_monitor_with_control():
    global live_screen_mode, last_screen_text, latest_frame_path, _last_alert_time
    print("[LIVE] Full control mode activated")
    speak("Live screen monitoring active, Boss.")

    while live_screen_mode:
        try:
            if capture_screen():
                latest_frame_path = "live_screen.png"

            current_text = extract_text_from_screen()
            now          = time.time()

            with _screen_lock:
                changed = _text_changed_significantly(last_screen_text, current_text)
                if changed:
                    last_screen_text = current_text

            if current_text and changed:
                alert_words = ['error:', 'fatal', 'exception', 'access denied', 'not found', 'crashed']
                lower_text  = current_text.lower()
                triggered   = [w for w in alert_words if w in lower_text]

                if triggered and (now - _last_alert_time) > _ALERT_COOLDOWN:
                    _last_alert_time = now
                    preview = current_text[:80].replace('\n', ' ').strip()
                    speak(f"Anomaly detected on screen, Boss: {preview}")

            time.sleep(3)

        except Exception as e:
            print(f"[LIVE SCREEN ERROR] {e}")
            time.sleep(4)

    print("[LIVE] Screen monitoring stopped.")

def start_live_screen():
    global live_screen_mode, live_screen_thread
    if live_screen_mode and live_screen_thread and live_screen_thread.is_alive():
        speak("Already monitoring your screen, Boss.")
        return
    live_screen_mode   = True
    live_screen_thread = threading.Thread(target=live_screen_monitor_with_control, daemon=True)
    live_screen_thread.start()

def stop_live_screen():
    global live_screen_mode
    if live_screen_mode:
        live_screen_mode = False
        speak("Screen monitoring offline, Boss.")
    else:
        speak("Screen monitoring was not active, Boss.")

def click_on_screen(element_name):
    capture_screen()
    if find_and_click_element(element_name):
        speak(f"Clicked {element_name}, Boss.")
    else:
        speak(f"Could not locate {element_name} on screen, Boss.")

def type_on_screen(field_name, text):
    capture_screen()
    if find_and_type_in_field(field_name, text):
        speak(f"Typed in {field_name}, Boss.")
    else:
        speak(f"Field '{field_name}' not found on screen, Boss.")

def press_key(key):
    try:
        pyautogui.press(key)
        speak(f"Pressed {key}, Boss.")
    except Exception as e:
        speak(f"Key error: {e}")

def perform_screen_action(command):
    speak("Analysing screen, Boss.")
    capture_screen()
    action_data = analyze_screen_with_ai_for_action(command)
    if action_data['confidence'] in ['high', 'medium']:
        speak(execute_screen_action(action_data))
    else:
        speak("Insufficient confidence to act, Boss. Be more specific.")

# ── Memory ───────────────────────────────────────────────────────────────────
def save_memory(text):
    try:
        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        data = []
    data.append(text)
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f)

def get_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

# ── Listen ───────────────────────────────────────────────────────────────────
_selected_mic_index = None

def get_microphone_index():
    global _selected_mic_index

    if _selected_mic_index is not None:
        return _selected_mic_index

    env_index = os.environ.get("FRIDAY_MIC_INDEX")
    if env_index is not None:
        try:
            _selected_mic_index = int(env_index)
            return _selected_mic_index
        except ValueError:
            print(f"[LISTEN] Invalid FRIDAY_MIC_INDEX: {env_index}")

    mics = sr.Microphone.list_microphone_names()
    blocked_words = ("output", "speaker", "headphone", "primary sound driver", "mapper - output")
    preferred_words = ("microphone array", "microphone", "mic")

    for preferred in preferred_words:
        for index, name in enumerate(mics):
            lower_name = name.lower()
            if preferred in lower_name and not any(word in lower_name for word in blocked_words):
                _selected_mic_index = index
                print(f"[LISTEN] Using microphone {index}: {name}")
                return _selected_mic_index

    _selected_mic_index = None
    print("[LISTEN] Using system default microphone.")
    return _selected_mic_index

def listen():
    """
    FIX: 'NoneType has no attribute close' was caused by sr.Microphone()
    failing silently when PyAudio has no default input device initialised yet,
    OR when the microphone object was garbage-collected before __exit__ ran.

    Fixes applied:
    1. Check sr.Microphone.list_microphone_names() before opening — if empty,
       wait and retry up to 3 times instead of crashing.
    2. Wrap the entire block in try/finally so the source is always released.
    3. Increased adjust_for_ambient_noise to 1s — more stable on first call.
    4. Added timeout + phrase_time_limit so listen() never hangs forever.
    """
    r = sr.Recognizer()
    r.dynamic_energy_threshold = True
    r.pause_threshold = 0.8
    r.non_speaking_duration = 0.4

    # Retry loop — microphone may not be ready immediately at startup
    for attempt in range(3):
        source = None
        try:
            # Guard: make sure at least one mic is available
            mics = sr.Microphone.list_microphone_names()
            if not mics:
                print(f"[LISTEN] No microphone found (attempt {attempt+1}/3), retrying...")
                time.sleep(1)
                continue

            mic_index = get_microphone_index()
            with sr.Microphone(device_index=mic_index) as source:
                r.adjust_for_ambient_noise(source, duration=0.6)
                r.energy_threshold = min(r.energy_threshold, 4000)
                print(f"\n[LISTENING] Waiting for command... energy={int(r.energy_threshold)}")
                audio = r.listen(source, timeout=12, phrase_time_limit=8)
            source = None

            print("[LISTEN] Audio captured. Recognising...")
            command = r.recognize_google(audio).lower()
            print(f"[USER] {command}")
            return command

        except sr.WaitTimeoutError:
            print("[LISTEN] Timeout — nothing heard.")
            return ""
        except sr.UnknownValueError:
            print("[LISTEN] Heard audio, but could not understand it.")
            return ""
        except sr.RequestError as e:
            print(f"[SR ERROR] {e}")
            return ""
        except Exception as e:
            print(f"[LISTEN ERROR] attempt {attempt+1}: {e}")
        finally:
            # Always release mic even if an exception happened mid-block
            if source is not None:
                try:
                    source.__exit__(None, None, None)
                except Exception:
                    pass
        time.sleep(0.5)

    return ""

# ── System monitor ───────────────────────────────────────────────────────────
def monitor_system():
    global vmonitoring
    print("[MONITOR] Started")
    while vmonitoring:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        update_status(f"CPU: {cpu}% | RAM: {ram}%")
        time.sleep(1)

# ── Close helpers ────────────────────────────────────────────────────────────
def close_current_tab():
    try:
        pyautogui.hotkey('ctrl', 'w')
        return True
    except Exception:
        return False

def close_application(app_name):
    try:
        for proc in psutil.process_iter(['name']):
            proc_name = proc.info.get('name') or ""
            if app_name.lower() in proc_name.lower():
                proc.terminate()
                return True
        pyautogui.hotkey('alt', 'f4')
        return True
    except Exception:
        return False

def close_active_window():
    try:
        pyautogui.hotkey('alt', 'f4')
        return True
    except Exception:
        return False

def minimize_all_windows():
    try:
        pyautogui.hotkey('win', 'd')
        return True
    except Exception:
        return False

RISKY_COMMAND_WORDS = [
    "format", "diskpart", "bcdedit", "reg delete", "takeown", "cipher",
    "remove-item", "rm ", "rmdir", "rd ", "del ", "erase ",
    "shutdown", "restart-computer", "stop-computer",
]

def run_local_command(command_text, powershell=False):
    command_text = (command_text or "").strip()
    if not command_text:
        return "Command missing, Boss."

    lowered = f" {command_text.lower()} "
    if any(word in lowered for word in RISKY_COMMAND_WORDS):
        return "Risky command blocked, Boss."

    try:
        if powershell:
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command_text]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        else:
            result = subprocess.run(command_text, shell=True, capture_output=True, text=True, timeout=25)

        output = (result.stdout or result.stderr or "").strip()
        if output:
            print("[COMMAND OUTPUT]")
            print(output)
            first_line = output.replace("\r", "\n").split("\n")[0].strip()
            return f"Done, Boss: {first_line}"
        return "Done, Boss."
    except subprocess.TimeoutExpired:
        return "Command timed out, Boss."
    except Exception as e:
        return f"Command failed, Boss: {e}"

# ── Command router ───────────────────────────────────────────────────────────
# FIX: Reordered checks so specific commands always match before broad ones.
# "open website" now checked BEFORE generic "open " to avoid false triggers.
# "play" now requires word boundary check to avoid triggering on "replay" etc.

def execute(command):
    global vmonitoring, latest_frame_path

    command = (command or "").strip().lower()
    if not command:
        return
    log_history("command", command)

    if command in [
        "connect phone", "connect my phone", "phone remote", "open phone remote",
        "open phone control", "phone control", "mobile remote", "mobile control",
        "phone link", "open phone link"
    ]:
        speak(open_phone_remote_dashboard())
        return

    if command.startswith("run powershell "):
        speak(run_local_command(command.split("run powershell ", 1)[1], powershell=True))
        return
    if command.startswith("run command "):
        speak(run_local_command(command.split("run command ", 1)[1], powershell=False))
        return
    if command.startswith("run cmd "):
        speak(run_local_command(command.split("run cmd ", 1)[1], powershell=False))
        return
    if command == "shutdown":
        speak("Say confirm shutdown, Boss.")
        return
    if command == "confirm shutdown":
        speak("Shutting down, Boss.")
        os.system("shutdown /s /t 1")
        return
    if command == "restart":
        speak("Say confirm restart, Boss.")
        return
    if command == "confirm restart":
        speak("Restarting, Boss.")
        os.system("shutdown /r /t 1")
        return

    email_result = handle_email_command(command)
    if email_result:
        speak(email_result)
        return

    code_result = handle_code_command(command)
    if code_result:
        speak(code_result)
        return

    context_result = handle_context_and_learning_command(command)
    if context_result:
        speak(context_result)
        return

    next_level_result = handle_next_level_command(command)
    if next_level_result:
        speak(next_level_result)
        return

    if any(word in command for word in ["news", "headlines"]) or "todays new" in command or "today's new" in command:
        speak(fetch_news(extract_news_topic(command)))
        return

    if command.startswith("search ") or command.startswith("google "):
        query = command.split(" ", 1)[1].strip() if " " in command else ""
        speak(open_google_search(query))
        return

    if command.startswith("search for "):
        speak(open_google_search(command.split("search for ", 1)[1]))
        return

    if command.startswith("look up "):
        speak(open_google_search(command.split("look up ", 1)[1]))
        return

    if "weather" in command or "temperature" in command:
        speak(open_weather(command))
        return

    if command in ["time", "what time is it", "current time", "tell me time"]:
        speak(current_time_reply())
        return

    if command in ["date", "today date", "what is today's date", "what date is it"]:
        speak(current_date_reply())
        return

    if command.startswith("open "):
        special_result = open_special_target(command)
        if special_result:
            speak(special_result)
            return
        app_name = command.replace("open", "", 1).strip()
        if app_name in ["code", "vs code", "vscode", "visual studio code"]:
            speak(open_code())
            return

    if any(word in command for word in ["latest", "current", "recent", "today"]) and not any(
        skip in command for skip in ["start monitoring", "stop monitoring", "today date", "current tab"]
    ):
        speak(open_google_search(command))
        return

    print(f"\n[CMD] {command}")
    original_command = command
    command = correct_command(command)
    if original_command != command:
        print(f"[CORRECTED] '{original_command}' -> '{command}'")

    # ── System monitoring ────────────────────────────────────────────────────
    if "start monitoring" in command:
        if not vmonitoring:
            vmonitoring = True
            threading.Thread(target=monitor_system, daemon=True).start()
        update_status("Monitoring: ON")
        speak("System monitoring active, Boss.")
        return

    if "stop monitoring" in command:
        vmonitoring = False
        update_status("Monitoring: OFF")
        speak("System monitoring offline, Boss.")
        return

    # ── Live screen ──────────────────────────────────────────────────────────
    if "start live screen" in command or "start screen monitoring" in command:
        start_live_screen()
        return

    if "stop live screen" in command or "stop screen monitoring" in command:
        stop_live_screen()
        return

    if "screen monitoring status" in command or "is screen monitoring on" in command:
        state = "active" if live_screen_mode else "offline"
        speak(f"Screen monitoring is {state}, Boss.")
        return

    # ── Screen click ─────────────────────────────────────────────────────────
    if "click on" in command:
        element = command.replace("click on", "").strip()
        click_on_screen(element) if element else speak("Specify what to click, Boss.")
        return

    if command.startswith("click the "):
        element = command.replace("click the", "", 1).strip()
        click_on_screen(element)
        return

    # ── Screen type ──────────────────────────────────────────────────────────
    if "type in" in command:
        parts = command.split("type in", 1)[1].strip()
        if " as " in parts:
            field, text_to_type = parts.split(" as ", 1)
            type_on_screen(field.strip(), text_to_type.strip())
        else:
            speak("Format: 'type in [field] as [text]', Boss.")
        return

    # ── Key press ────────────────────────────────────────────────────────────
    if "press" in command and ("key" in command or "button" in command):
        key = command.replace("press","").replace("key","").replace("button","").strip()
        press_key(key)
        return

    # ── Smart screen action ──────────────────────────────────────────────────
    if any(p in command for p in ["do that", "perform that", "do this"]):
        if live_screen_mode:
            perform_screen_action(command)
        else:
            speak("Activate live screen mode first, Boss.")
        return

    # ── Screen navigation ────────────────────────────────────────────────────
    if "go to" in command and "website" in command:
        site = command.replace("go to","").replace("website","").strip()
        if site:
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.5)
            pyautogui.write(site)
            pyautogui.press('enter')
            speak(f"Navigating to {site}, Boss.")
        return

    # ── Find on screen ───────────────────────────────────────────────────────
    if "find" in command and "on screen" in command:
        capture_screen()
        element  = command.replace("find","").replace("on screen","").strip()
        elements = detect_ui_elements()
        found    = [e for e in elements if element.lower() in e['text']]
        if found:
            x, y = found[0]['center']
            pyautogui.moveTo(x, y, duration=0.5)
            speak(f"Found {len(found)} match(es) for '{element}', Boss.")
        else:
            speak(f"'{element}' not found on screen, Boss.")
        return

    # ── Music / video control ────────────────────────────────────────────────
    if "stop music" in command or "pause music" in command:
        pyautogui.press('space')
        speak("Paused, Boss.")
        return

    if "resume music" in command:
        pyautogui.press('space')
        speak("Resumed, Boss.")
        return

    # ── Close tab ────────────────────────────────────────────────────────────
    if "close tab" in command:
        speak("Closing tab, Boss." if close_current_tab() else "Could not close tab, Boss.")
        return

    # ── Close application ────────────────────────────────────────────────────
    if "close application" in command or "close app" in command:
        app_name = command.replace("close application","").replace("close app","").strip()
        if app_name:
            speak(f"Closed {app_name}, Boss." if close_application(app_name) else f"Could not close {app_name}, Boss.")
        else:
            speak("Closing active window, Boss." if close_active_window() else "Could not close window, Boss.")
        return

    # ── Minimize all ─────────────────────────────────────────────────────────
    if "minimize all" in command or "show desktop" in command:
        speak("Minimised all windows, Boss." if minimize_all_windows() else "Could not minimise, Boss.")
        return

    # ── Shutdown / restart ───────────────────────────────────────────────────
    if "shutdown" in command:
        speak("Shutting down, Boss.")
        os.system("shutdown /s /t 1")
        return
    if "restart" in command:
        speak("Restarting, Boss.")
        os.system("shutdown /r /t 1")
        return

    # ── Open website — MUST be before generic "open" check ──────────────────
    if "open website" in command:
        site = command.replace("open website","").strip().lower()
        if site:
            url = website_urls.get(site, f"https://www.{site}.com" if "." not in site else f"https://{site}")
            speak(f"Opening {site} in Chrome, Boss.")
            open_in_chrome(url)
        else:
            speak("Which website, Boss?")
        return

    # ── Go to (website) ──────────────────────────────────────────────────────
    if command.startswith("go to "):
        site = command.replace("go to","").strip().lower()
        url  = website_urls.get(site, f"https://www.{site}.com" if "." not in site else f"https://{site}")
        speak(f"Opening {site} in Chrome, Boss.")
        open_in_chrome(url)
        return

    # ── Play (YouTube) ───────────────────────────────────────────────────────
    # word-boundary check — "replay", "display" etc. won't trigger
    _words = command.split()
    if _words and _words[0] == "play" and len(_words) > 1:
        song = command.split("play", 1)[1].strip()
        kit = get_pywhatkit()
        if not kit:
            speak("YouTube play needs internet, Boss.")
            return
        speak(f"Playing {song} on YouTube, Boss.")
        try:
            kit.playonyt(song)
        except Exception as e:
            speak(f"Playback error, Boss: {e}")
        return

    # ── Open application ─────────────────────────────────────────────────────
    # FIX: only match "open X" where X is not empty, checked after website
    if command.startswith("open "):
        app = command.replace("open","",1).strip()
        if app:
            if app in ["code", "vs code", "vscode", "visual studio code"]:
                speak(open_code())
                return
            configured_path = app_paths.get(app)
            if configured_path:
                try:
                    os.startfile(configured_path)
                    speak(f"Opening {app}, Boss.")
                except Exception as e:
                    speak(f"Could not open {app}, Boss: {e}")
            elif app in app_paths:
                speak(f"No working path configured for {app}, Boss.")
            else:
                try:
                    os.startfile(app)
                    speak(f"Opening {app}, Boss.")
                except Exception:
                    try:
                        subprocess.Popen(app)
                        speak(f"Opening {app}, Boss.")
                    except Exception:
                        speak(f"Application '{app}' not found, Boss.")
        return

    # ── Launch (alias for open) ───────────────────────────────────────────────
    if "launch" in command:
        app = command.replace("launch","").strip()
        if app in ["code", "vs code", "vscode", "visual studio code"]:
            speak(open_code())
            return
        configured_path = app_paths.get(app)
        if configured_path:
            try:
                os.startfile(configured_path)
                speak(f"Launching {app}, Boss.")
            except Exception as e:
                speak(f"Could not launch {app}, Boss: {e}")
        elif app in app_paths:
            speak(f"No working path configured for {app}, Boss.")
        else:
            speak(f"No path configured for '{app}', Boss.")
        return

    # ── Screen capture ───────────────────────────────────────────────────────
    if "see my screen" in command or "capture screen" in command:
        if capture_screen():
            latest_frame_path = "live_screen.png"
            open_in_chrome(os.path.abspath("live_screen.png"))
            speak("Screen captured, Boss.")
        else:
            speak("Screen capture failed, Boss.")
        return

    # ── Read screen ──────────────────────────────────────────────────────────
    if "read my screen" in command or "what's on my screen" in command:
        speak("Scanning screen, Boss.")
        capture_screen()
        text = extract_text_from_screen()
        if text:
            for chunk in [text[i:i+200] for i in range(0, len(text), 200)]:
                speak(chunk)
        else:
            speak("No readable text detected, Boss.")
        return

    # ── Analyse screen ───────────────────────────────────────────────────────
    if "analyze screen" in command:
        speak("Running analysis, Boss.")
        capture_screen()
        speak(analyze_screen_with_ai())
        return

    # ── Screen summary ───────────────────────────────────────────────────────
    if "summarize screen" in command or "screen summary" in command:
        capture_screen()
        text = extract_text_from_screen()
        if text:
            speak(ask_ai(f"Concise summary of this screen content: {text[:500]}"))
        else:
            speak("No content to summarise, Boss.")
        return

    # ── Memory ───────────────────────────────────────────────────────────────
    if "remember that" in command:
        info = command.split("remember that", 1)[1].strip()
        if not info:
            speak("What should I remember, Boss?")
            return
        save_memory(info)
        speak("Logged to memory, Boss.")
        return

    if "what do you remember" in command:
        memories = get_memory()
        if memories:
            speak("Memory contents, Boss:")
            for mem in memories:
                speak(mem)
        else:
            speak("Memory banks empty, Boss.")
        return

    if "clear memory" in command:
        with open(MEMORY_FILE, "w") as f:
            json.dump([], f)
        speak("Memory wiped, Boss.")
        return

    # ── API status command ────────────────────────────────────────────────────
    if any(p in command for p in ["api status", "which api", "current api"]):
        status = "Groq" if api_client else "Not configured"
        speak(f"API status: {status}, Boss.")
        return

    # ── Deep Learning powered features ───────────────────────────────────────
    if DL_AVAILABLE:
        if any(p in command for p in ["dl status", "deep learning status", "ai module status"]):
            status = get_dl_status()
            lines = [f"{k}: {v}" for k, v in status.items()]
            speak("Deep learning status, Boss: " + ", ".join(lines))
            return

        if any(p in command for p in ["analyze my emotion", "detect my emotion", "detect emotion", "my emotion"]):
            capture_screen()
            screen_text = extract_text_from_screen()
            text_to_analyze = screen_text[:500] if screen_text else command
            emotion_data = dl_emotion(text_to_analyze)
            dominant = emotion_data.get("dominant_emotion", "neutral")
            sentiment = emotion_data.get("sentiment", "neutral")
            speak(f"Detected emotion: {dominant}, sentiment: {sentiment}, Boss.")
            return

        if any(p in command for p in ["describe image", "describe picture", "what's in this image", "what is in this image", "analyze image with ai vision"]):
            if latest_frame_path and os.path.exists(latest_frame_path):
                speak("Running deep learning vision analysis, Boss.")
                description = dl_describe_image(latest_frame_path)
                if description:
                    speak(f"Vision analysis: {description}")
                else:
                    speak("Vision model unavailable, using text analysis instead.")
                    text = extract_text_from_screen()
                    speak(text if text else "No content detected, Boss.")
            else:
                speak("No recent screen capture, Boss.")
            return

        if any(p in command for p in ["dl classify", "intent classify", "classify intent", "what intent"]):
            result = dl_classify(command)
            intent = result.get("intent", "general_chat")
            confidence = result.get("intent_confidence", 0)
            emotion = result.get("emotion", {}).get("dominant_emotion", "neutral")
            top = result.get("top_intents", [])[:3]
            top_str = ", ".join(f"{i[0]}({i[1]:.2f})" for i in top)
            speak(f"Intent: {intent} ({confidence:.2f}). Top: {top_str}. Emotion: {emotion}. Boss.")
            return

        if any(p in command for p in ["dl train", "dl record", "log intent"]):
            dl_trainer.record(command, "general_chat", True)
            stats = dl_trainer.get_stats()
            speak(f"Recorded, Boss. Total samples: {stats.get('total', 0)}, accuracy: {stats.get('accuracy', 0):.2f}")
            return

    # ── Help with task ───────────────────────────────────────────────────────
    if "help me with" in command:
        task = command.split("help me with", 1)[1].strip()
        speak(ask_ai(f"How can I help with: {task}"))
        return

    # ── Summary (generic) ────────────────────────────────────────────────────
    if "summary" in command:
        capture_screen()
        text = extract_text_from_screen()
        speak(ask_ai("Summarise this text: " + text) if text else "No text found, Boss.")
        return

    # ── Analyse this (from last frame) ───────────────────────────────────────
    if any(p in command for p in ["analyze this", "what's in this", "what is in this"]):
        if latest_frame_path:
            text = extract_text_from_screen()
            speak(text if text else "No text detected, Boss.")
        else:
            speak("No recent screen capture available, Boss.")
        return

    # ── Read PDF on screen ───────────────────────────────────────────────────
    if "read this pdf on my screen" in command:
        capture_screen()
        text = extract_text_from_screen()
        speak(text if text else "No text found, Boss.")
        return

    # ── DL-Enhanced routing (catches commands rule-based router misses) ──────
    if DL_AVAILABLE:
        dl_result = dl_classify(command)
        dl_intent = dl_result.get("intent", "")
        dl_confidence = dl_result.get("intent_confidence", 0)
        dl_mapped = dl_result.get("mapped_command", "")

        emotion_modifier = ""
        emotion_data = dl_result.get("emotion", {})
        if emotion_data:
            emotion_modifier = dl_router.get_emotion_response_modifier(emotion_data)

        if dl_confidence > 0.80 and dl_intent not in ("general_chat", "help_request"):
            if dl_mapped and dl_mapped != command:
                print(f"[DL ROUTE] {command} -> {dl_mapped} (intent={dl_intent}, conf={dl_confidence:.2f})")
                dl_trainer.record(command, dl_intent, True)
                action_result = ai_execute_task(dl_mapped)
                if action_result:
                    speak(str(action_result) + emotion_modifier)
                    return

        if dl_intent == "help_request":
            dl_trainer.record(command, dl_intent, True)
            result = ask_ai(f"User needs help. Briefly suggest useful FRIDAY commands for: {command}", use_history=False)
            speak(result + emotion_modifier)
            return

        dl_trainer.record(command, dl_intent, True)

    # ── Fallback: send to Groq as conversation ───────────────────────────────
    action_result = ai_execute_task(command)
    if action_result:
        speak(action_result)
        return

    if DL_AVAILABLE:
        emotion_data = dl_emotion(command)
        modifier = dl_get_emotion_modifier(command)
        reply = ask_ai(command, use_history=True)
        if modifier:
            reply = reply.rstrip(".") + ". " + modifier.strip()
        speak(reply)
    else:
        speak(ask_ai(command, use_history=True))


# ── Wait for FRIDAY to finish speaking before mic opens ──────────────────────
def wait_until_done_speaking(extra_pause=0.7):
    """
    Waits for speech to finish so mic does not pick up FRIDAY voice as command.
    Uses a polling loop with timeout instead of queue.join() to avoid deadlock.
    """
    # Wait up to 15s for queue to empty + mixer to finish
    deadline = time.time() + 15
    while time.time() < deadline:
        if voice_queue.empty() and not pygame.mixer.music.get_busy():
            break
        time.sleep(0.05)
    time.sleep(extra_pause)  # extra silence so mic echo settles

# ── Main loop ────────────────────────────────────────────────────────────────
def run():
    global stop_speaking
    speak("Systems online.")
    wait_until_done_speaking()

    while True:
        cmd = listen()
        if "friday" in cmd:
            stop_speaking = True
            pygame.mixer.music.stop()
            inline_command = cmd.replace("friday", "", 1).strip(" ,.")
            if inline_command:
                execute(inline_command)
                wait_until_done_speaking()
                continue
            speak("Yes, Boss?")
            wait_until_done_speaking()   # mic opens only AFTER Yes Boss is done playing
            command = listen()
            if command:
                execute(command)
            wait_until_done_speaking()   # wait after response too before next loop
        elif cmd:
            execute(cmd)
            wait_until_done_speaking()

# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    create_status_overlay()
    try:
        start_phone_remote()
    except Exception as e:
        print(f"[PHONE REMOTE START ERROR] {e}")
    try:
        start_auto_learning()
    except Exception as e:
        print(f"[AUTO LEARN START ERROR] {e}")
    try:
        start_reminder_worker()
    except Exception as e:
        print(f"[REMINDER START ERROR] {e}")
    threading.Thread(target=run, daemon=True).start()
    root.mainloop()
