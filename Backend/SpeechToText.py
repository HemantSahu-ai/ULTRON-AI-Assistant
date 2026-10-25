from pathlib import Path
import json
import time

from dotenv import dotenv_values
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, NoSuchElementException
import mtranslate as mt

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"
DATA_DIR = PROJECT_ROOT / "Data"
HTML_PATH = DATA_DIR / "Voice.html"
STATUS_DIR = PROJECT_ROOT / "Frontend" / "Files"

env_vars = dotenv_values(ENV_PATH)
InputLanguage = (env_vars.get("InputLanguage") or "en-US").strip() or "en-US"

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ULTRON Speech Recognition</title></head>
<body>
<button id="start" type="button">Start Listening</button>
<button id="end" type="button">Stop Listening</button>
<p id="output" aria-live="polite"></p><p id="interim"></p><p id="status">Ready</p>
<script>
const output = document.getElementById("output");
const interim = document.getElementById("interim");
const statusText = document.getElementById("status");
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null, shouldContinue = false, manuallyStopped = true, restartTimer = null;
let finalParts = [];

function startRecognition() {
  if (!SpeechRecognition) { statusText.textContent = "Speech recognition is not supported in this Chrome version."; return; }
  if (shouldContinue && recognition) return;
  shouldContinue = true; manuallyStopped = false; finalParts = [];
  output.textContent = ""; interim.textContent = ""; makeRecognition();
}
function makeRecognition() {
  if (!shouldContinue || !SpeechRecognition) return;
  recognition = new SpeechRecognition();
  recognition.lang = "__INPUT_LANGUAGE__";
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;
  recognition.onstart = () => statusText.textContent = "Listening...";
  recognition.onresult = (event) => {
    let currentInterim = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i], transcript = result[0].transcript.trim();
      if (!transcript) continue;
      if (result.isFinal) finalParts.push(transcript);
      else currentInterim += transcript + " ";
    }
    output.textContent = finalParts.join(" ").trim();
    interim.textContent = currentInterim.trim() ? "Hearing: " + currentInterim.trim() : "";
  };
  recognition.onerror = (event) => {
    statusText.textContent = "Recognition issue: " + event.error;
    if (["not-allowed", "service-not-allowed", "audio-capture"].includes(event.error)) {
      shouldContinue = false; manuallyStopped = true;
    }
  };
  recognition.onend = () => {
    if (shouldContinue && !manuallyStopped) {
      statusText.textContent = "Restarting listener...";
      clearTimeout(restartTimer);
      restartTimer = setTimeout(() => { if (shouldContinue && !manuallyStopped) makeRecognition(); }, 350);
    } else statusText.textContent = "Stopped";
  };
  try { recognition.start(); }
  catch (error) { statusText.textContent = "Could not start: " + error.message; }
}
function stopRecognition() {
  shouldContinue = false; manuallyStopped = true; clearTimeout(restartTimer);
  if (recognition) { try { recognition.stop(); } catch (error) {} }
  statusText.textContent = "Stopped";
}
function takeUtterance() {
  const text = finalParts.join(" ").trim();
  finalParts = []; output.textContent = ""; interim.textContent = "";
  return text;
}
window.takeUtterance = takeUtterance;
window.startRecognition = startRecognition;
window.stopRecognition = stopRecognition;
document.getElementById("start").addEventListener("click", startRecognition);
document.getElementById("end").addEventListener("click", stopRecognition);
</script></body></html>"""

def SetAssistantStatus(Status):
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    (STATUS_DIR / "Status.data").write_text(str(Status), encoding="utf-8")

def QueryModifier(Query):
    query = " ".join((Query or "").lower().strip().split())
    if not query: return ""
    question_words = ("how", "what", "who", "where", "when", "why", "which", "whose", "whom", "can you", "could you", "would you")
    is_question = any(query == word or query.startswith(word + " ") for word in question_words)
    query = query.rstrip(".!?")
    if not query: return ""
    return query.capitalize() + ("?" if is_question else ".")

def UniversalTranslator(Text):
    if not Text or not Text.strip(): return ""
    try:
        result = mt.translate(Text, "en", "auto")
        return result.strip() if result else Text
    except Exception as exc:
        print(f"Translation failed: {exc}")
        return Text

def _create_driver():
    options = Options()
    options.add_argument("--use-fake-ui-for-media-stream")
    options.add_argument("--disable-notifications")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    return webdriver.Chrome(options=options)

class _SpeechSession:
    """A persistent Chrome session, reused for all speech turns."""
    def __init__(self):
        HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATUS_DIR.mkdir(parents=True, exist_ok=True)
        html = HTML_TEMPLATE.replace("__INPUT_LANGUAGE__", json.dumps(InputLanguage)[1:-1])
        HTML_PATH.write_text(html, encoding="utf-8")
        self.driver = _create_driver()
        self.driver.get(HTML_PATH.as_uri())
        self.driver.find_element(By.ID, "start").click()
        time.sleep(0.5)

    def listen(self, timeout_seconds=120, silence_seconds=1.5):
        started = time.monotonic()
        last_change = None
        last_seen = ""
        while time.monotonic() - started < timeout_seconds:
            try:
                status = self.driver.find_element(By.ID, "status").text
                final_text = self.driver.find_element(By.ID, "output").text.strip()
                interim_text = self.driver.find_element(By.ID, "interim").text.strip()
                current = (final_text + " " + interim_text).strip()
                if current and current != last_seen:
                    last_seen = current
                    last_change = time.monotonic()
                # Wait for a pause and at least one finalized phrase.
                if final_text and last_change is not None and time.monotonic() - last_change >= silence_seconds:
                    result = self.driver.execute_script("return window.takeUtterance();")
                    if result: return result
                if status.startswith("Recognition issue:") and any(
                    e in status for e in ("not-allowed", "service-not-allowed", "audio-capture")
                ):
                    print(status)
                    return ""
            except (NoSuchElementException, WebDriverException):
                time.sleep(0.2)
            time.sleep(0.15)
        try:
            return self.driver.execute_script("return window.takeUtterance();") or ""
        except WebDriverException:
            return ""

    def close(self):
        try: self.driver.execute_script("window.stopRecognition();")
        except Exception: pass
        try: self.driver.quit()
        except Exception: pass

def SpeechRecognition(timeout_seconds=30):
    """Compatibility wrapper for code that calls this function once."""
    session = None
    try:
        session = _SpeechSession()
        text = session.listen(timeout_seconds=timeout_seconds)
        if not text:
            print("No speech was recognized. Check the microphone, internet, and Chrome support.")
            return ""
        if not InputLanguage.lower().startswith("en"):
            SetAssistantStatus("Translating...")
            text = UniversalTranslator(text)
        return QueryModifier(text)
    except Exception as exc:
        print(f"Speech recognition setup failed: {exc}")
        print("Check Chrome installation and microphone permissions.")
        return ""
    finally:
        if session: session.close()

def _main_loop():
    session = None
    try:
        session = _SpeechSession()
        print("ULTRON speech recognition is ready.")
        print("Chrome stays open. Speak naturally, then pause briefly after each utterance.")
        print("Press Ctrl+C in this terminal to exit.")
        while True:
            text = session.listen(timeout_seconds=120, silence_seconds=1.5)
            if text:
                if not InputLanguage.lower().startswith("en"):
                    SetAssistantStatus("Translating...")
                    text = UniversalTranslator(text)
                print("You:", QueryModifier(text))
            else:
                time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nSpeech recognition stopped.")
    except Exception as exc:
        print(f"Speech recognition setup failed: {exc}")
        print("Check Chrome installation, internet, and microphone permission.")
    finally:
        if session: session.close()

if __name__ == "__main__":
    _main_loop()
