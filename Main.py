
"""
ULTRON AI Assistant
Main entry point.

Project structure:
    Main.py
    Frontend/Gui.py
    Backend/Chatbot.py
    Backend/Automation.py
    Backend/Model.py
    Backend/TextToSpeech.py
"""

import sys
import os
import traceback
import importlib.util
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
GUI_FILE = PROJECT_DIR / "Frontend" / "Gui.py"

# Allow imports such as `from Backend.Chatbot import ChatBot`
# even when the application is launched from another directory.
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def check_project():
    """Check essential project files before launching the GUI."""
    required_files = [
        GUI_FILE,
    ]

    missing = [str(path) for path in required_files if not path.is_file()]

    if missing:
        print("ULTRON startup failed. Missing required files:")
        for path in missing:
            print(f"  - {path}")
        return False

    return True


def launch_gui():
    """Load and launch the existing PyQt5 GUI."""
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox

        # Import Gui.py by its path so the existing GUI class is reused.
        spec = importlib.util.spec_from_file_location(
            "ultron_frontend_gui", str(GUI_FILE)
        )

        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load GUI file: {GUI_FILE}")

        gui_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gui_module)

        if not hasattr(gui_module, "Ultron"):
            raise AttributeError(
                "Frontend/Gui.py does not define a class named 'Ultron'."
            )

        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName("ULTRON AI Assistant")

        window = gui_module.Ultron()
        window.show()

        print("ULTRON GUI launched successfully.")
        return app.exec_()

    except Exception:
        details = traceback.format_exc()
        print("\nULTRON startup error:\n")
        print(details)

        # Show a dialog if Qt is available and an application exists.
        try:
            from PyQt5.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance()
            if app is not None:
                QMessageBox.critical(
                    None,
                    "ULTRON Startup Error",
                    "ULTRON could not start.\n"
                    "Check the terminal for the full traceback.",
                )
        except Exception:
            pass

        return 1


def main():
    print("=" * 45)
    print("       ULTRON AI ASSISTANT")
    print("=" * 45)
    print(f"Project: {PROJECT_DIR}")

    if not check_project():
        return 1

    return launch_gui()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nULTRON shutdown requested.")
        sys.exit(0)
