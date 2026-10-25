"""
ULTRON AI Assistant - PyQt5 dashboard GUI

Install:   pip install PyQt5 psutil SpeechRecognition pyaudio
Optional:  pip install gputil
Run:       python Gui.py

Place this file in the project root or in Frontend/.
Your backend is called through ask_ai() and speak_reply().
"""
import sys
import os
import time
import math
import html
import webbrowser
import collections
import traceback
import zipfile
from datetime import datetime

import psutil
from PyQt5.QtCore import QEvent, Qt, QTimer, QThread, pyqtSignal, QRectF, QPointF
from PyQt5.QtGui import (QPainter, QColor, QPen, QFont, QPolygonF, QLinearGradient,
                         QPixmap, QIcon, QRadialGradient)
from PyQt5.QtWidgets import (
    QApplication, QWidget, QFrame, QLabel, QPushButton, QLineEdit, QVBoxLayout,
    QHBoxLayout, QGridLayout, QTextBrowser, QTextEdit, QStackedWidget,
    QProgressBar, QDialog,
)

try:
    import speech_recognition as sr
except ImportError:  # the app still runs; the mic button explains what is missing
    sr = None

# ----------------------------------------------------------------- paths
# If this file lives in Frontend/, the project root is its parent folder.
_GUI_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = (os.path.dirname(_GUI_DIR)
               if os.path.basename(_GUI_DIR).lower() == "frontend" else _GUI_DIR)
# Automation.py loads .env relative to the current working directory.
os.chdir(PROJECT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "Data")
BACKUP_DIR = os.path.join(PROJECT_DIR, "Backups")
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)  # so `from Backend...` works from Frontend/

# ----------------------------------------------------------------- palette
# ============================================================
# ULTRON — PREMIUM OBSIDIAN THEME
# ============================================================

BG = "#05070D"       # Deep obsidian black
PANEL = "#0B1120"    # Premium dark navy
RED = "#FF365E"      # Crimson alert accent
BLUE = "#00D9FF"     # Electric cyan
TEXT = "#EAF6FF"     # Ice-white text
DIM = "#8293AD"      # Muted silver-blue

# Additional premium accents
PURPLE = "#9D5CFF"   # Plasma violet
BORDER = "#1B3048"   # Subtle blue border
SUCCESS = "#36E6A5"  # Neon mint green

QSS = f"""
QWidget {{ background: transparent; color: {TEXT}; font-family: 'Segoe UI', 'Ubuntu', sans-serif; font-size: 20px; }}
#root {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #04081a, stop:1 #0a0612); }}
#panel {{ background: {PANEL}; border: 1px solid #1c3a78; border-radius: 10px; }}
#panelRed {{ background: {PANEL}; border: 1px solid #a01826; border-radius: 10px; }}
#panelTitle {{ font-size: 20px; font-weight: 600; letter-spacing: 1px; }}
#tab {{ border: 1px solid #1c3a78; border-radius: 6px; padding: 6px 14px; color: {DIM}; }}
#tab[active="true"] {{ border: 1px solid {RED}; color: white; background: #2a0c18; }}
#tool {{ background: #0a1a3a; border: 1px solid #1c3a78; border-radius: 8px; padding: 12px; }}
#tool:hover {{ border: 1px solid {BLUE}; background: #0e2350; }}
#tool:disabled {{ border: 1px solid {RED}; color: {RED}; }}
#action {{ background: #0b2a5e; border: 1px solid {BLUE}; border-radius: 5px; padding: 5px 12px; color: {BLUE}; }}
#action:hover {{ background: #11397a; }}
#action:disabled {{ color: {DIM}; border: 1px solid {DIM}; }}
#clear {{ background: #2a0c18; border: 1px solid {RED}; border-radius: 5px; padding: 5px 16px; color: {RED}; }}
QLineEdit {{ background: #07122a; border: 1px solid #1c3a78; border-radius: 8px; padding: 9px 12px; color: {TEXT}; }}
QLineEdit:focus {{ border: 1px solid {BLUE}; }}
QTextBrowser, QTextEdit {{ background: #060f24; border: 1px solid #12285a; border-radius: 8px; font-family: Consolas, 'DejaVu Sans Mono', monospace; font-size: 20px; }}
QProgressBar {{ background: #0a1a3a; border: none; border-radius: 3px; max-height: 6px; }}
QProgressBar::chunk {{ background: {BLUE}; border-radius: 3px; }}
"""

ERROR_MARK = "__ULTRON_ERROR__"


# ----------------------------------------------------------------- backend integration

def _direct_groq_answer(prompt: str) -> str:
    """Fallback chat engine when the optional Backend.Chatbot module is absent."""
    from dotenv import dotenv_values
    from groq import Groq
    env = dotenv_values(os.path.join(PROJECT_DIR, ".env"))
    key = env.get("GroqAPIKey")
    if not key:
        return ("ULTRON needs a GroqAPIKey in the project-root .env file "
                "for general chat. Add the key, then restart the app.")
    client = Groq(api_key=key)
    answer = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": "You are ULTRON, a helpful personal AI assistant. Give clear, practical answers."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=1600,
    )
    return answer.choices[0].message.content or "I couldn't generate a response."


def ask_ai(text: str) -> str:
    """Classify the request and route it to the supplied backend modules."""
    try:
        # Keep compatibility with an existing ChatBot implementation if present.
        try:
            from Backend.Chatbot import ChatBot
        except ImportError:
            ChatBot = None

        from Backend.Model import FirstLayerDMM
        tasks = FirstLayerDMM(text)
        if not tasks:
            tasks = [f"general {text}"]

        replies = []
        automation_commands = []
        for task in tasks:
            task = str(task).strip()
            lower = task.lower()
            if lower.startswith("general "):
                query = task[len("general "):].strip()
                if query:
                    replies.append(str(ChatBot(query)) if ChatBot else _direct_groq_answer(query))
            elif lower.startswith("realtime "):
                query = task[len("realtime "):].strip()
                from Backend.RealtimeSearchEngine import RealtimeSearchEngine
                replies.append(str(RealtimeSearchEngine(query)))
            elif lower.startswith("generate image "):
                prompt = task[len("generate image "):].strip()
                try:
                    from Backend.ImageGeneration import OpenImageGenerator
                except ImportError:
                    from ImageGeneration import OpenImageGenerator
                ok = OpenImageGenerator(prompt, "chatgpt")
                replies.append("Opened ChatGPT and copied your image prompt. Paste it into the prompt box and press Generate." if ok else "I couldn't open the image generator. Check pyperclip and your browser.")
            elif lower == "exit" or lower.startswith("exit "):
                replies.append("I'm here whenever you need me. You can close the ULTRON window to exit.")
            elif lower.startswith("reminder"):
                replies.append("Reminder commands are classified, but a reminder scheduler is not connected yet.")
            elif any(lower.startswith(prefix) for prefix in (
                "open ", "close ", "play ", "system ", "content ",
                "google search ", "youtube search ")):
                automation_commands.append(task)
            else:
                # Unknown classifier output: still answer instead of failing silently.
                replies.append(_direct_groq_answer(text))

        if automation_commands:
            import asyncio
            from Backend.Automation import Automation
            # Automation performs the commands on worker thread (AIWorker), not the GUI thread.
            asyncio.run(Automation(automation_commands))
            replies.append("Command(s) sent to automation: " + "; ".join(automation_commands))

        return "\n\n".join(reply for reply in replies if reply.strip()) or "I couldn't determine an action for that request. Try rephrasing it."
    except Exception:
        return ERROR_MARK + "\n" + traceback.format_exc()


# ----------------------------------------------------------------- worker threads
class AIWorker(QThread):
    done = pyqtSignal(str)

    def __init__(self, text):
        super().__init__()
        self.text = text

    def run(self):
        self.done.emit(ask_ai(self.text))


class TTSWorker(QThread):
    """Speaks a reply off the UI thread so the window never freezes."""
    error = pyqtSignal(str)

    def __init__(self, text):
        super().__init__()
        self.text = text

    def run(self):
        try:
            from Backend.TextToSpeech import TextToSpeech
            TextToSpeech(self.text)
        except Exception:
            self.error.emit(traceback.format_exc())


class MicWorker(QThread):
    recognized = pyqtSignal(str)
    status = pyqtSignal(str)
    error = pyqtSignal(str)

    def run(self):
        if sr is None:
            self.error.emit("Speech recognition is not installed. "
                            "Run: pip install SpeechRecognition pyaudio")
            return
        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                self.status.emit("Adjusting microphone...")
                recognizer.adjust_for_ambient_noise(source, duration=0.6)
                self.status.emit("Listening... speak now")
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=15)
            self.status.emit("Recognizing speech...")
            text = recognizer.recognize_google(audio).strip()
            if text:
                self.recognized.emit(text)
            else:
                self.error.emit("No speech was recognized.")
        except sr.WaitTimeoutError:
            self.error.emit("No speech detected. Click the microphone and try again.")
        except sr.UnknownValueError:
            self.error.emit("I couldn't understand that. Please try again.")
        except sr.RequestError as exc:
            self.error.emit(f"Speech recognition service unavailable: {exc}")
        except Exception as exc:
            self.error.emit(f"Microphone error: {exc}")


class BackupWorker(QThread):
    progress = pyqtSignal(int)
    skipped = pyqtSignal(str)
    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    EXCLUDED_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules", "Backups"}
    EXCLUDED_FILES = {".env", ".env.local", ".env.production"}  # keep API keys out of zips

    def run(self):
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(BACKUP_DIR, f"ULTRON_backup_{stamp}.zip")

            files = []
            for root, dirs, names in os.walk(PROJECT_DIR):
                dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
                for name in names:
                    if name in self.EXCLUDED_FILES or name.endswith((".pyc", ".pyo")):
                        continue
                    files.append(os.path.join(root, name))

            total = max(len(files), 1)
            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
                for i, path in enumerate(files, 1):
                    try:
                        archive.write(path, os.path.relpath(path, PROJECT_DIR))
                    except OSError as exc:
                        self.skipped.emit(f"Skipped {path}: {exc}")
                    self.progress.emit(int(i * 100 / total))
            self.progress.emit(100)
            self.done.emit(dest)
        except Exception:
            self.failed.emit(traceback.format_exc())


# ----------------------------------------------------------------- helpers
def make_panel(title, closable=False, red=False):
    f = QFrame()
    f.setObjectName("panelRed" if red else "panel")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(14, 10, 14, 12)
    head = QHBoxLayout()
    t = QLabel(title)
    t.setObjectName("panelTitle")
    head.addWidget(t)
    head.addStretch()
    if closable:
        x = QPushButton("✕")
        x.setFlat(True)
        x.setStyleSheet(f"color:{BLUE}; border:none; font-size:20px;")
        x.clicked.connect(f.hide)
        head.addWidget(x)
    lay.addLayout(head)
    f.body = lay
    f.header = head
    return f


# ----------------------------------------------------------------- widgets
class Gauge(QWidget):
    def __init__(self, label, color=BLUE):
        super().__init__()
        self.label, self.color, self.value, self.sub = label, color, 0, ""
        self.setMinimumSize(110, 130)

    def set(self, value, sub):
        self.value, self.sub = value, sub
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        d = min(w, h - 44) - 8
        r = QRectF((w - d) / 2, 22, d, d)
        p.setPen(QColor(DIM))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(0, 0, w, 18), Qt.AlignCenter, self.label)
        p.setPen(QPen(QColor("#12285a"), 7))
        p.drawArc(r, 0, 360 * 16)
        col = QColor(RED if self.value > 85 else self.color)
        p.setPen(QPen(col, 7, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(r, 90 * 16, -int(self.value * 3.6 * 16))
        p.setPen(QColor(TEXT))
        p.setFont(QFont("Segoe UI", 15, QFont.Bold))
        p.drawText(r, Qt.AlignCenter, f"{int(self.value)}%")
        p.setPen(QColor(DIM))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(0, 22 + d + 4, w, 16), Qt.AlignCenter, self.sub)


class Sparkline(QWidget):
    def __init__(self):
        super().__init__()
        self.data = collections.deque([0] * 60, maxlen=60)
        self.setMinimumHeight(60)

    def push(self, v):
        self.data.append(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        top = max(max(self.data), 1)
        pts = [QPointF(i * w / (len(self.data) - 1), h - 4 - (v / top) * (h - 10))
               for i, v in enumerate(self.data)]
        fill = QPolygonF(pts + [QPointF(w, h), QPointF(0, h)])
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, QColor(42, 168, 255, 90))
        g.setColorAt(1, QColor(42, 168, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawPolygon(fill)
        p.setPen(QPen(QColor(BLUE), 1.6))
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(QPolygonF(pts))


class Waveform(QWidget):
    """Animated audio bars. Only animates while `active` is True."""
    def __init__(self, color=RED):
        super().__init__()
        self.color, self.phase, self.active = color, 0.0, False
        self.setMinimumSize(120, 28)
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(100)

    def _tick(self):
        if self.active:
            self.phase += 0.5
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setPen(QPen(QColor(self.color), 2))
        n, h = self.width() // 5, self.height()
        for i in range(n):
            amp = (math.sin(self.phase + i * 0.5) + 1) / 2 if self.active else 0.1
            amp *= 0.4 + 0.6 * abs(math.sin(i * 0.3))
            a = max(2, amp * (h - 4))
            p.drawLine(i * 5 + 2, int((h - a) / 2), i * 5 + 2, int((h + a) / 2))


class MicPanel(QFrame):
    """Top-right panel. Click it to speak; the waveform moves only while listening."""
    clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("panelRed")
        self.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 16, 8)
        self.label = QLabel("🎙  Click to Speak")
        self.label.setStyleSheet("font-weight:600; font-size:20px;")
        self.wave = Waveform(RED)
        lay.addWidget(self.label)
        lay.addWidget(self.wave)
        self.setMinimumWidth(320)
        self.setMinimumHeight(48)

    def set_text(self, text):
        self.label.setText(text)

    def set_listening(self, on):
        self.wave.active = on

    def mousePressEvent(self, event):
        if self.isEnabled() and event.button() == Qt.LeftButton:
            self.clicked.emit()


class LogoWidget(QWidget):
    """ULTRON logo: red hexagon shield with a robot face.
    To use your own artwork instead, save it as Frontend/Graphics/ultron_logo.png
    (or Graphics/ultron_logo.png in the project root); it is picked up automatically."""
    def __init__(self, size=56):
        super().__init__()
        self.setFixedSize(size, size)
        self.pix = None
        for folder in (os.path.join(PROJECT_DIR, "Frontend", "Graphics"),
                       os.path.join(PROJECT_DIR, "Graphics")):
            path = os.path.join(folder, "ultron_logo.png")
            if os.path.exists(path):
                self.pix = QPixmap(path)
                break

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.pix is not None and not self.pix.isNull():
            p.drawPixmap(self.rect(), self.pix.scaled(self.size(), Qt.KeepAspectRatio,
                                                      Qt.SmoothTransformation))
            return
        w, h = self.width(), self.height()
        r = min(w, h) / 2 - 4
        c = QPointF(w / 2, h / 2)

        def pt(x, y):  # unit coordinates -> pixels
            return QPointF(c.x() + x * r, c.y() + y * r)

        hexagon = QPolygonF([pt(math.cos(math.radians(a)), math.sin(math.radians(a)))
                             for a in (-90, -30, 30, 90, 150, 210)])
        # soft red glow behind the shield
        glow = QRadialGradient(c, r * 1.3)
        glow.setColorAt(0.6, QColor(255, 42, 58, 70))
        glow.setColorAt(1.0, QColor(255, 42, 58, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(c, r * 1.3, r * 1.3)
        # shield body and double outline
        p.setBrush(QColor("#1a0610"))
        p.setPen(QPen(QColor(RED), 2.4))
        p.drawPolygon(hexagon)
        inner = QPolygonF([pt(q.x() * 0.82, q.y() * 0.82) for q in
                           [QPointF(math.cos(math.radians(a)), math.sin(math.radians(a)))
                            for a in (-90, -30, 30, 90, 150, 210)]])
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 42, 58, 120), 1))
        p.drawPolygon(inner)
        # robot face
        face = QPolygonF([pt(-0.38, -0.45), pt(0, -0.62), pt(0.38, -0.45), pt(0.42, 0.05),
                          pt(0.22, 0.5), pt(0, 0.62), pt(-0.22, 0.5), pt(-0.42, 0.05)])
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(RED))
        p.drawPolygon(face)
        dark = QColor("#1a0610")
        p.setBrush(dark)
        for sx in (-1, 1):  # slanted eyes
            p.drawPolygon(QPolygonF([pt(sx * 0.30, -0.14), pt(sx * 0.07, -0.02),
                                     pt(sx * 0.09, 0.09), pt(sx * 0.32, 0.0)]))
        p.setPen(QPen(dark, max(1.2, r * 0.07)))
        p.drawLine(pt(0, -0.58), pt(0, -0.24))          # forehead crest
        p.drawLine(pt(-0.12, 0.30), pt(0.12, 0.30))     # mouth grille
        p.drawLine(pt(-0.08, 0.40), pt(0.08, 0.40))


# ----------------------------------------------------------------- transparent floating assistant window
class FloatingAssistantWindow(QDialog):
    """Translucent, draggable desktop chat bar; closing it hides rather than quits ULTRON."""
    send_requested = pyqtSignal(str)
    mic_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setWindowTitle("ULTRON Transparent Assistant")
        self.setObjectName("floatingAssistant")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # Lower whole-window opacity for a lighter glass overlay.
        self.setWindowOpacity(0.76)
        self.resize(350, 160)
        self._drag_offset = None
        self.setStyleSheet(f"""
            QDialog#floatingAssistant {{ background: transparent; color: {TEXT}; }}
            QFrame#glass {{ background: rgba(5, 13, 31, 145); border: 1px solid rgba(42, 168, 255, 145); border-radius: 16px; }}
            QLabel {{ color: {TEXT}; background: transparent; }}
            QTextBrowser {{ background: rgba(4, 12, 28, 105); color: {TEXT}; border: 1px solid rgba(42,168,255,120); border-radius: 9px; padding: 5px; }}
            QLineEdit {{ background: rgba(8, 25, 49, 135); color: {TEXT}; border: 1px solid #245a86; border-radius: 10px; padding: 10px; }}
            QLineEdit:focus {{ border: 1px solid #55d9ff; }}
            QPushButton {{ background: rgba(13, 45, 76, 155); color: #e8f8ff; border: 1px solid #2aa8ff; border-radius: 9px; padding: 8px 12px; }}
            QPushButton:hover {{ background: rgba(20, 79, 120, 190); }}
            QPushButton#mic {{ background: rgba(0, 120, 170, 170); border: 1px solid #66e6ff; font-size: 20px; }}
            QPushButton#close {{ background: rgba(80, 15, 30, 155); border-color: #ff2a3a; }}
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)
        glass = QFrame()
        glass.setObjectName("glass")
        layout = QVBoxLayout(glass)
        layout.setContentsMargins(12, 9, 12, 10)
        layout.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel("◈  ULTRON")
        title.setStyleSheet(f"font-weight: 800; color: #69ddff; letter-spacing: 2px;")
        self.status_label = QLabel("READY  •  CLICK MIC TO SPEAK")
        self.status_label.setStyleSheet("color: #91abc6; font-size: 20px;")
        close_btn = QPushButton("×")
        close_btn.setObjectName("close")
        close_btn.setFixedSize(30, 28)
        close_btn.clicked.connect(self.hide)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.status_label)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self.transcript = QTextBrowser()
        self.transcript.setOpenExternalLinks(True)
        self.transcript.setMaximumHeight(82)
        self.transcript.setPlaceholderText("ULTRON's answers will appear here…")
        layout.addWidget(self.transcript)

        row = QHBoxLayout()
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Ask ULTRON anything…")
        self.entry.returnPressed.connect(self._send)
        self.mic_btn = QPushButton("🎙")
        self.mic_btn.setObjectName("mic")
        self.mic_btn.setToolTip("Click to speak")
        self.mic_btn.setFixedWidth(48)
        self.mic_btn.clicked.connect(self.mic_requested.emit)
        send_btn = QPushButton("➤")
        send_btn.setToolTip("Send message")
        send_btn.setFixedWidth(45)
        send_btn.clicked.connect(self._send)
        row.addWidget(self.entry, 1)
        row.addWidget(self.mic_btn)
        row.addWidget(send_btn)
        layout.addLayout(row)
        outer.addWidget(glass)

    def _send(self):
        message = self.entry.text().strip()
        if message:
            self.entry.clear()
            self.send_requested.emit(message)

    def add_message(self, who, text):
        color = "#69ddff" if who == "You" else "#ff6878"
        safe = html.escape(str(text)).replace("\n", "<br>")
        self.transcript.append(f"<p style='margin:4px 0'><b style='color:{color}'>{html.escape(str(who))}</b><br>{safe}</p>")
        self.transcript.verticalScrollBar().setValue(self.transcript.verticalScrollBar().maximum())

    def set_status(self, message):
        self.status_label.setText(str(message).upper()[:38])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        event.ignore()
        self.hide()


# ----------------------------------------------------------------- main window
class Ultron(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("ULTRON AI Assistant")
        self.setWindowIcon(QIcon(LogoWidget(64).grab()))
        self.resize(1536, 1000)
        self.setStyleSheet(QSS)
        self._net = psutil.net_io_counters()
        self._t = time.time()
        self.workers = []          # keeps running threads alive until they finish
        self.mic_worker = None
        self.backup_worker = None
        self.floating_window = None
        self.floating_enabled = False
        self.build()
        # Independent top-level tool window: it must remain visible when the dashboard is minimized.
        self.floating_window = FloatingAssistantWindow(None)
        self.floating_window.send_requested.connect(self.on_floating_send)
        self.floating_window.mic_requested.connect(self.toggle_listening)
        self.log("INFO: Starting ULTRON AI Assistant...", "Console")
        self.log("INFO: Frontend GUI loaded", "Console")
        self.log("INFO: System ready.", "Console")
        t = QTimer(self)
        t.timeout.connect(self.refresh)
        t.start(1000)
        self.refresh()
        self.say("ULTRON", "I am ULTRON. Your personal AI assistant. How can I help you today?")

    # ================================================================= layout
    def build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(14)

        # ---- centre
        main = QVBoxLayout()
        main.setSpacing(12)
        main.addLayout(self.top_bar())
        main.addLayout(self.stats_row())
        mid = QHBoxLayout()
        mid.setSpacing(12)
        mid.addWidget(self.chat_panel(), 5)
        right_mid = QVBoxLayout()
        right_mid.addWidget(self.code_panel(), 3)
        right_mid.addWidget(self.backup_panel(), 2)
        mid.addLayout(right_mid, 5)
        main.addLayout(mid, 1)
        tag = QLabel("ANALYZE  •  PROCESS  •  EXECUTE")
        tag.setStyleSheet(f"color:{RED}; letter-spacing:3px; font-weight:600;")
        tag.setAlignment(Qt.AlignCenter)
        main.addWidget(tag)
        root.addLayout(main, 1)

        # ---- right column
        right = QVBoxLayout()
        right.setSpacing(12)
        right.addWidget(self.hero_panel())
        right.addWidget(self.tools_panel())
        right.addWidget(self.activity_panel(), 1)
        rw = QWidget()
        rw.setLayout(right)
        rw.setFixedWidth(340)
        root.addWidget(rw)

    def top_bar(self):
        bar = QHBoxLayout()
        bar.setSpacing(16)
        bar.addWidget(LogoWidget(60))
        title = QVBoxLayout()
        logo = QLabel("ULTRON")
        logo.setStyleSheet("font-size:26px; font-weight:800; letter-spacing:4px;")
        sub = QLabel("AI ASSISTANT")
        sub.setStyleSheet(f"color:{DIM}; letter-spacing:5px; font-size:20px;")
        title.addWidget(logo)
        title.addWidget(sub)
        bar.addLayout(title)
        quote = QLabel("“BETTER TO BE FEARED THAN LOVED, IF YOU CANNOT BE BOTH.”  — ULTRON")
        quote.setStyleSheet(f"color:{BLUE}; font-weight:600;")
        bar.addWidget(quote, 1)
        self.float_btn = QPushButton("◈ Floating")
        self.float_btn.setObjectName("action")
        self.float_btn.clicked.connect(self.toggle_floating)
        bar.addWidget(self.float_btn)
        self.mic_panel = MicPanel()
        self.mic_panel.clicked.connect(self.toggle_listening)
        bar.addWidget(self.mic_panel)
        return bar

    def stats_row(self):
        row = QHBoxLayout()
        row.setSpacing(12)

        sp = make_panel("SYSTEM STATUS", closable=True)
        g = QHBoxLayout()
        self.g_cpu, self.g_ram, self.g_gpu, self.g_disk = (
            Gauge("CPU"), Gauge("RAM"), Gauge("GPU"), Gauge("Disk", RED))
        for x in (self.g_cpu, self.g_ram, self.g_gpu, self.g_disk):
            g.addWidget(x)
        sp.body.addLayout(g)
        row.addWidget(sp, 5)

        npn = make_panel("NETWORK", closable=True)
        self.l_down = QLabel("↓ Download  0 Mbps")
        self.l_up = QLabel("↑ Upload  0 Mbps")
        r = QHBoxLayout()
        r.addWidget(self.l_down)
        r.addWidget(self.l_up)
        npn.body.addLayout(r)
        self.spark = Sparkline()
        npn.body.addWidget(self.spark)
        row.addWidget(npn, 3)

        bp = make_panel("BATTERY")
        self.l_bat = QLabel("--%")
        self.l_bat.setAlignment(Qt.AlignCenter)
        self.l_bat.setStyleSheet("font-size:24px; font-weight:600;")
        self.l_chg = QLabel("")
        self.l_chg.setAlignment(Qt.AlignCenter)
        self.l_chg.setStyleSheet(f"color:{DIM};")
        bp.body.addWidget(self.l_bat)
        bp.body.addWidget(self.l_chg)
        row.addWidget(bp, 2)

        tp = make_panel("TIME & DATE")
        self.l_time = QLabel()
        self.l_time.setAlignment(Qt.AlignCenter)
        self.l_time.setStyleSheet("font-size:34px; font-weight:300;")
        self.l_date = QLabel()
        self.l_date.setAlignment(Qt.AlignCenter)
        tp.body.addWidget(self.l_time)
        tp.body.addWidget(self.l_date)
        row.addWidget(tp, 2)
        return row

    def chat_panel(self):
        p = make_panel("ULTRON - CHAT", red=True)
        on = QLabel("● Online")
        on.setStyleSheet("color:#2cff7a;")
        p.header.addWidget(on)
        self.chat = QTextBrowser()
        self.chat.setOpenExternalLinks(True)
        p.body.addWidget(self.chat, 1)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type your message...")
        self.input.returnPressed.connect(self.send)
        send = QPushButton("➤")
        send.setObjectName("action")
        send.clicked.connect(self.send)
        row.addWidget(self.input, 1)
        row.addWidget(send)
        p.body.addLayout(row)
        return p

    def code_panel(self):
        p = make_panel("AI CODE PANEL", closable=True, red=True)
        tabs = QHBoxLayout()
        self.stack = QStackedWidget()
        self.views, self.tabbtns = {}, {}
        for name in ["Console", "Code", "Logs", "Errors"]:
            b = QPushButton(name)
            b.setObjectName("tab")
            b.clicked.connect(lambda _, n=name: self.set_tab(n))
            tabs.addWidget(b)
            self.tabbtns[name] = b
            e = QTextEdit()
            e.setReadOnly(True)
            self.stack.addWidget(e)
            self.views[name] = e
        p.body.addLayout(tabs)
        p.body.addWidget(self.stack, 1)
        foot = QHBoxLayout()
        foot.addWidget(QLabel("AI Code Console"), 1)
        c = QPushButton("Clear")
        c.setObjectName("clear")
        c.clicked.connect(lambda: self.stack.currentWidget().clear())
        foot.addWidget(c)
        p.body.addLayout(foot)
        self.set_tab("Console")
        return p

    def backup_panel(self):
        p = make_panel("CODE BACKUP", closable=True)
        row = QHBoxLayout()
        left = QVBoxLayout()
        self.l_backup = QLabel("Last Backup\n—")
        left.addWidget(self.l_backup)
        self.backup_btn = QPushButton("Backup Now")
        self.backup_btn.setObjectName("action")
        self.backup_btn.clicked.connect(self.backup)
        left.addWidget(self.backup_btn)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        left.addWidget(self.bar)
        left.addWidget(QLabel("Auto Backup: ON"))
        row.addLayout(left, 1)
        files = QVBoxLayout()
        files.addWidget(QLabel("Project Files"))
        for f in ["Main.py", "Backend/", "Frontend/", "Data/", "Config Files"]:
            files.addWidget(QLabel(f"<span style='color:{BLUE}'>✓</span> {f}"))
        row.addLayout(files, 1)
        p.body.addLayout(row)
        return p

    def hero_panel(self):
        p = make_panel("ULTRON", red=True)
        p.body.addWidget(QLabel(
            "<span style='color:#ff2a3a'>“I am ULTRON.<br>Your personal AI assistant."
            "<br>How can I help you today?”</span>"))
        return p

    def tools_panel(self):
        p = make_panel("QUICK TOOLS")
        grid = QGridLayout()
        tools = [
            ("🌐  Open Chrome", lambda: self.run_cmd("open chrome")),
            ("▶  YouTube", lambda: self.run_cmd("open youtube")),
            ("🔍  Google Search", lambda: self.run_cmd("open google")),
            ("⚙  System Settings", self.open_settings),
            ("🔊  Volume", self.volume_up),
            ("📷  Screenshot", self.screenshot),
        ]
        for i, (name, fn) in enumerate(tools):
            b = QPushButton(name)
            b.setObjectName("tool")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, f=fn: f())
            grid.addWidget(b, i // 2, i % 2)
        p.body.addLayout(grid)
        return p

    def activity_panel(self):
        p = make_panel("RECENT ACTIVITY")
        self.act_box = QVBoxLayout()
        p.body.addLayout(self.act_box)
        p.body.addStretch()
        self.activity("Idle")
        return p

    # ================================================================= state helpers
    def set_tab(self, name):
        self.stack.setCurrentWidget(self.views[name])
        for n, b in self.tabbtns.items():
            b.setProperty("active", n == name)
            b.style().unpolish(b)
            b.style().polish(b)

    def log(self, msg, tab="Console"):
        """`msg` may contain basic HTML such as <br>; escape text before passing it in."""
        stamp = datetime.now().strftime("%H:%M:%S")
        color = RED if tab == "Errors" else BLUE
        self.views[tab].append(f"<span style='color:{color}'>[{stamp}] {msg}</span>")

    def log_text(self, text, tab="Console"):
        self.log(html.escape(text).replace("\n", "<br>"), tab)

    def activity(self, text):
        row = QHBoxLayout()
        row.addWidget(QLabel(f"<span style='color:{BLUE}'>●</span>  {html.escape(text)}"), 1)
        t = QLabel(datetime.now().strftime("%H:%M"))
        t.setStyleSheet(f"color:{DIM};")
        row.addWidget(t)
        w = QWidget()
        w.setLayout(row)
        self.act_box.insertWidget(0, w)
        # keep the newest 5 rows; the last item is the stretch, so count carefully
        rows = [self.act_box.itemAt(i).widget() for i in range(self.act_box.count())
                if self.act_box.itemAt(i).widget()]
        for old in rows[5:]:
            self.act_box.removeWidget(old)
            old.deleteLater()

    def say(self, who, text):
        stamp = datetime.now().strftime("%H:%M")
        color = BLUE if who == "You" else RED
        safe = html.escape(text).replace("\n", "<br>")
        self.chat.append(
            f"<p><b style='color:{color}'>{who}</b> "
            f"<span style='color:{DIM}'>{stamp}</span><br>{safe}</p>")
        if self.floating_window is not None:
            self.floating_window.add_message(who, text)

    def track(self, worker):
        """Keep a reference to a running QThread and release it when it ends."""
        self.workers.append(worker)
        worker.finished.connect(lambda w=worker: self.workers.remove(w)
                                if w in self.workers else None)

    # ================================================================= live stats
    def refresh(self):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage(os.path.abspath(os.sep))
        self.g_cpu.set(cpu, self.temp())
        self.g_ram.set(ram.percent, f"{ram.used / 2**30:.1f} / {ram.total / 2**30:.0f} GB")
        gpu = self.gpu()
        self.g_gpu.set(gpu[0], gpu[1])
        self.g_disk.set(disk.percent, f"{disk.used / 2**30:.0f} / {disk.total / 2**30:.0f} GB")

        now = time.time()
        net = psutil.net_io_counters()
        dt = max(now - self._t, 0.001)
        down = (net.bytes_recv - self._net.bytes_recv) * 8 / dt / 1e6
        up = (net.bytes_sent - self._net.bytes_sent) * 8 / dt / 1e6
        self._net, self._t = net, now
        self.l_down.setText(f"<span style='color:{BLUE}'>↓</span> Download  {down:.1f} Mbps")
        self.l_up.setText(f"<span style='color:{RED}'>↑</span> Upload  {up:.1f} Mbps")
        self.spark.push(down + up)

        bat = psutil.sensors_battery()
        if bat:
            self.l_bat.setText(f"🔋 {int(bat.percent)}%")
            self.l_chg.setText("Charging" if bat.power_plugged else "On battery")
        else:
            self.l_bat.setText("🔌 AC")
            self.l_chg.setText("No battery")
        d = datetime.now()
        self.l_time.setText(d.strftime("%H:%M"))
        self.l_date.setText(d.strftime("%b %d, %Y\n%A"))

    def temp(self):
        try:
            for entries in psutil.sensors_temperatures().values():
                if entries:
                    return f"{entries[0].current:.0f}°C"
        except Exception:
            pass
        return "--°C"

    def gpu(self):
        try:
            import GPUtil  # optional: pip install gputil
            g = GPUtil.getGPUs()[0]
            return g.load * 100, f"{g.temperature:.0f}°C"
        except Exception:
            return 0, "n/a"

    # ================================================================= voice input
    def toggle_listening(self):
        if self.mic_worker is not None and self.mic_worker.isRunning():
            self.log("INFO: Microphone is already active.", "Logs")
            return
        self.mic_panel.setEnabled(False)
        self.mic_panel.set_text("🎙  Starting...")
        self.mic_panel.set_listening(True)
        self.activity("Microphone activated")

        self.mic_worker = MicWorker()
        self.mic_worker.status.connect(self.update_mic_status)
        self.mic_worker.recognized.connect(self.on_speech_recognized)
        self.mic_worker.error.connect(self.on_mic_error)
        self.mic_worker.finished.connect(self.restore_mic_button)
        self.track(self.mic_worker)
        self.mic_worker.start()

    def update_mic_status(self, status):
        self.mic_panel.set_text(f"🎙  {status}")
        if self.floating_window is not None:
            self.floating_window.set_status(status)

    def on_speech_recognized(self, text):
        self.say("You", text)
        self.activity("Speech recognized")
        self.log("INFO: Speech recognized successfully.", "Logs")
        self.process_message(text)

    def on_mic_error(self, message):
        if self.floating_window is not None:
            self.floating_window.set_status("MICROPHONE ERROR")
        self.log_text(message, "Errors")
        self.activity("Microphone error")
        self.say("ULTRON", message)

    def restore_mic_button(self):
        if self.floating_window is not None:
            self.floating_window.set_status("READY  •  CLICK MIC TO SPEAK")
        self.mic_panel.set_listening(False)
        self.mic_panel.setEnabled(True)
        self.mic_panel.set_text("🎙  Click to Speak")

    # ================================================================= floating window
    def toggle_floating(self):
        if self.floating_window is None:
            return
        if self.floating_window.isVisible():
            self.floating_enabled = False
            self.floating_window.hide()
        else:
            self.floating_enabled = True
            self.floating_window.show()
            self.floating_window.raise_()
            self.floating_window.activateWindow()
            if not self.floating_window.transcript.toPlainText():
                self.floating_window.add_message("ULTRON", "Online. Type a question or tap 🎙 to speak.")
            screen = QApplication.primaryScreen()
            if screen is not None:
                area = screen.availableGeometry()
                self.floating_window.move(area.right() - self.floating_window.width() - 28, area.bottom() - self.floating_window.height() - 70)

    def on_floating_send(self, text):
        self.say("You", text)
        self.process_message(text)

    # ================================================================= chat flow
    def send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.say("You", text)
        self.process_message(text)

    def process_message(self, text):
        if self.run_cmd(text, from_chat=True):
            return
        self.activity("Chat request sent")
        worker = AIWorker(text)
        worker.done.connect(self.on_reply)
        self.track(worker)
        worker.start()

    def on_reply(self, text):
        if text.startswith(ERROR_MARK):
            details = text.split("\n", 1)[1] if "\n" in text else text
            self.say("ULTRON", "I couldn't process that request. "
                               "Open the AI Code panel → Errors to see the traceback.")
            self.log_text(details, "Errors")
            self.activity("AI error captured")
            self.set_tab("Errors")
            return
        self.say("ULTRON", text)
        self.speak_reply(text)
        self.activity("Chat response generated")
        self.log("INFO: Chat response generated", "Logs")

    def speak_reply(self, text):
        worker = TTSWorker(text)
        worker.error.connect(lambda tb: self.log_text("Text-to-speech failed:\n" + tb, "Errors"))
        self.track(worker)
        worker.start()

    # ================================================================= commands & tools
    def run_cmd(self, text, from_chat=False):
        t = text.lower().strip()
        sites = {"chrome": "https://www.google.com",
                 "youtube": "https://www.youtube.com",
                 "google": "https://www.google.com"}
        if t.startswith("open "):
            target = t[5:].strip()
            if target in sites:
                webbrowser.open(sites[target])
                if from_chat:
                    self.say("ULTRON", f"Opening {target.title()} for you.")
                self.activity(f"{target.title()} opened")
                return True
        if "system status" in t:
            ram = psutil.virtual_memory()
            self.say("ULTRON",
                     "Here's your current system status:\n"
                     f"• CPU : {psutil.cpu_percent():.0f}%\n"
                     f"• RAM : {ram.percent:.0f}%\n"
                     f"• Disk: {psutil.disk_usage(os.path.abspath(os.sep)).percent:.0f}%")
            self.activity("System status checked")
            return True
        if "screenshot" in t:
            self.screenshot()
            if from_chat:
                self.say("ULTRON", "Screenshot saved.")
            return True
        return False

    def open_settings(self):
        try:
            if sys.platform.startswith("win"):
                os.startfile("ms-settings:")
            elif sys.platform == "darwin":
                os.system("open -a 'System Settings'")
            else:
                os.system("gnome-control-center &")
            self.activity("Settings opened")
        except Exception as e:
            self.log_text(f"Error: {e}", "Errors")

    def volume_up(self):
        try:
            import ctypes
            for _ in range(5):  # Windows volume-up key
                ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
            self.activity("Volume raised")
        except Exception:
            self.log("Error: volume control is Windows-only in this build", "Errors")

    def screenshot(self):
        folder = os.path.join(DATA_DIR, "Screenshots")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, datetime.now().strftime("shot_%Y%m%d_%H%M%S.png"))
        QApplication.primaryScreen().grabWindow(0).save(path)
        self.activity("Screenshot saved")
        self.log_text(f"INFO: Screenshot saved to {path}", "Logs")

    # ================================================================= backup
    def backup(self):
        if self.backup_worker is not None and self.backup_worker.isRunning():
            return
        self.backup_btn.setEnabled(False)
        self.bar.setValue(0)
        self.backup_worker = BackupWorker()
        self.backup_worker.progress.connect(self.bar.setValue)
        self.backup_worker.skipped.connect(lambda m: self.log_text(m, "Logs"))
        self.backup_worker.done.connect(self.on_backup_done)
        self.backup_worker.failed.connect(self.on_backup_failed)
        self.backup_worker.finished.connect(lambda: self.backup_btn.setEnabled(True))
        self.track(self.backup_worker)
        self.backup_worker.start()

    def on_backup_done(self, path):
        self.l_backup.setText("Last Backup\n" + datetime.now().strftime("%b %d, %Y %H:%M"))
        self.activity("Backup completed")
        self.log_text(f"INFO: Backup completed: {path}", "Logs")

    def on_backup_failed(self, tb):
        self.log_text("Backup failed:\n" + tb, "Errors")
        self.activity("Backup failed")

    # Keep the floating overlay visible when the main dashboard is minimized to the taskbar.
    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange and self.isMinimized():
            if self.floating_enabled and self.floating_window is not None:
                QTimer.singleShot(120, self._restore_floating_overlay)

    def _restore_floating_overlay(self):
        if self.floating_enabled and self.floating_window is not None:
            self.floating_window.show()
            self.floating_window.raise_()

    # ================================================================= shutdown
    def closeEvent(self, event):
        if self.floating_window is not None:
            self.floating_window.hide()
        for w in list(self.workers):
            w.wait(2000)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Ultron()
    win.show()
    sys.exit(app.exec_())