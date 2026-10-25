
import webbrowser
import pyperclip


IMAGE_SITES = {
    "chatgpt": "https://chatgpt.com/",
    "gemini": "https://gemini.google.com/",
}


def OpenImageGenerator(prompt: str, website: str = "both") -> bool:
    """Open an image-generation website and copy the prompt."""

    prompt = prompt.strip()

    if not prompt:
        print("Image prompt is empty.")
        return False

    if website not in ("chatgpt", "gemini", "both"):
        print("Choose chatgpt, gemini, or both.")
        return False

    try:
        # Copy the prompt so it is ready to paste in the browser.
        pyperclip.copy(prompt)

        if website == "both":
            print("Choose ChatGPT or Gemini:")
            print("1. ChatGPT")
            print("2. Gemini")
            choice = input("Enter 1 or 2: ").strip()

            if choice == "1":
                website = "chatgpt"
            elif choice == "2":
                website = "gemini"
            else:
                print("Invalid choice.")
                return False

        webbrowser.open_new_tab(IMAGE_SITES[website])

        print(f"Opened {website.title()}.")
        print("Your image prompt is copied to the clipboard.")
        print("Click the website's prompt box and press Ctrl+V.")
        print("Review the prompt and click Generate yourself.")

        return True

    except Exception as error:
        print(f"Could not open image generator: {error}")
        return False


if __name__ == "__main__":
    OpenImageGenerator(
        " anime girl with long hair and glowing blue eyes",
        "both",
    )
