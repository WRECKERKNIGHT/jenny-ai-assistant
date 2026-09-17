"""
J.E.N.N.Y - Wake Word Detector (mode-aware, neural voice)

Listens for "Hey Jenny", "Hey Friday", "Hey Jarvis" or "Hey Ultron" and
activates the assistant with the matching persona. Wake acknowledgements and
replies are spoken through the JENNY server (neural edge-tts voice), with a
gentle chime so you always know it heard you.

Usage: python wakeword.py [--server http://localhost:3005] [--energy 300]
                          [--timeout 7] [--push-to-talk]
"""

import sys
import time
import json
import urllib.request
import urllib.parse

try:
    import speech_recognition as sr
except ImportError:
    print("Install SpeechRecognition: pip install SpeechRecognition")
    sys.exit(1)

SERVER_URL = "http://localhost:3005"
WAKE_WORDS = ["hey friday", "hello friday", "hey jarvis", "hello jarvis",
              "hey ultron", "hello ultron",
              "friday", "jarvis", "ultron"]
WAKE_TO_MODE = {
    "hey friday": "friday", "hello friday": "friday", "friday": "friday",
    "hey jarvis": "jarvis", "hello jarvis": "jarvis", "jarvis": "jarvis",
    "hey ultron": "ultron", "hello ultron": "ultron", "ultron": "ultron",
}
LISTEN_TIMEOUT = 7
PHRASE_LIMIT = 10
ENERGY_THRESHOLD = 300
PUSH_TO_TALK = False

ACK_PHRASES = {
    "friday": "Friday here! What can I help you with, Boss?",
    "jarvis": "Jarvis at your service, Sir. What may I do for you?",
    "ultron": "Ultrons listening. State your command.",
}
SLEEP_PHRASES = {
    "friday": "Going back to sleep, Boss! Say Hey Friday to wake me up.",
    "jarvis": "Very well, Sir. I shall remain on standby.",
    "ultron": "Powering down. Say Hey Ultron when you need me.",
}


def server_online(timeout=2):
    """Preflight /api/speak/status check so we don't listen for nothing."""
    try:
        req = urllib.request.Request(f"{SERVER_URL}/api/speak/status", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def server_speak(text):
    """Speak through the neural voice engine on the server (preferred)."""
    try:
        req = urllib.request.Request(
            f"{SERVER_URL}/api/speak/fallback",
            data=json.dumps({"text": text}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def local_speak(text):
    """Last-resort feedback when the server voice is unreachable.

    Uses only a soft beep — never a second SAPI/pyttsx3 voice — so the single
    neural voice rule is preserved and we can never double-speak."""
    try:
        import winsound
        winsound.Beep(880, 90)
        winsound.Beep(1320, 120)
    except Exception:
        pass


def speak(text):
    if not server_speak(text):
        local_speak(text)


def play_chime():
    """Soft two-note chime so the user always knows the wake word was heard."""
    try:
        import winsound
        winsound.Beep(880, 80)
        winsound.Beep(1320, 110)
    except Exception:
        pass


def set_mode(mode):
    try:
        req = urllib.request.Request(
            f"{SERVER_URL}/api/mode",
            data=json.dumps({"mode": mode}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass


def send_to_jenny(text):
    try:
        req = urllib.request.Request(
            f"{SERVER_URL}/api/chat",
            data=json.dumps({"message": text}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            reply = data.get("reply", {})
            spoken = reply.get("speech") or reply.get("text", "I didn't quite get that, Boss!")
            speak(spoken)
            print(f"[Jenny] {reply.get('text', spoken)}")
            return reply
    except Exception:
        speak("Server is not running. Please start the server first, Boss!")
        return None


def check_wake_word(text):
    text_lower = text.lower().strip()
    for word in WAKE_WORDS:
        if word in text_lower:
            return word
    return None


def extract_command(text, wake_word):
    text_lower = text.lower().strip()
    idx = text_lower.find(wake_word.lower())
    if idx >= 0:
        command = text_lower[idx + len(wake_word):].strip()
        if command.startswith((',', '.', '!', '?')):
            command = command[1:].strip()
        return command
    return text.strip()


def is_dismissal(text):
    return any(w in text for w in ["goodbye", "bye", "sleep", "stop listening",
                                   "dismiss", "shut up", "quiet now"])


def main():
    global SERVER_URL, ENERGY_THRESHOLD, LISTEN_TIMEOUT, PUSH_TO_TALK

    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--server" and i + 1 < len(argv):
            SERVER_URL = argv[i + 1].rstrip("/")
        elif argv[i] == "--energy" and i + 1 < len(argv):
            try:
                ENERGY_THRESHOLD = int(argv[i + 1])
            except ValueError:
                pass
        elif argv[i] == "--timeout" and i + 1 < len(argv):
            try:
                LISTEN_TIMEOUT = int(argv[i + 1])
            except ValueError:
                pass
        elif argv[i] == "--push-to-talk":
            PUSH_TO_TALK = True
        i += 1

    if not server_online():
        print(f"[!] JENNY server unreachable at {SERVER_URL}. Start it first (python server.py).")
        print("[!] Wake word detector will still run; commands will queue until server is up.")

    print("=" * 50)
    print(f"  J.E.N.N.Y - Wake Word Detector  (server: {SERVER_URL})")
    print("  Say 'Hey Jenny' / 'Hey Friday' / 'Hey Jarvis' / 'Hey Ultron'")
    print("=" * 50)
    print("  Listening... (Ctrl+C to stop)")
    print("=" * 50)

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = ENERGY_THRESHOLD
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 1.0

    with sr.Microphone() as source:
        print("[*] Calibrating microphone...")
        recognizer.adjust_for_ambient_noise(source, duration=2)
        print("[*] Ready! Listening for wake words...")
        print()

    wake_word_used = None
    last_wake = 0

    while True:
        try:
            with sr.Microphone() as source:
                if PUSH_TO_TALK:
                    print("[*] PUSH-TO-TALK MODE: press Enter to speak a command...")
                    input()
                audio = recognizer.listen(source, timeout=LISTEN_TIMEOUT, phrase_time_limit=PHRASE_LIMIT)

            try:
                text = recognizer.recognize_google(audio).lower()
                print(f"[Heard] {text}")

                if wake_word_used and (time.time() - last_wake) < 30:
                    command = extract_command(text, wake_word_used)
                    wake_word_used = None
                    if is_dismissal(command):
                        speak(SLEEP_PHRASES.get("friday", "Going back to sleep."))
                        print("[*] Going back to sleep mode...")
                    else:
                        send_to_jenny(command)
                    continue

                found = check_wake_word(text)

                if found:
                    print("[*] Wake word detected!")
                    play_chime()
                    mode = WAKE_TO_MODE.get(found, "friday")
                    set_mode(mode)
                    speak(ACK_PHRASES.get(mode, ACK_PHRASES["friday"]))
                    wake_word_used = found
                    last_wake = time.time()

                    if PUSH_TO_TALK:
                        print("[*] Command mode active: press Enter then speak your command, or say it now.")
                    else:
                        with sr.Microphone() as source:
                            print("[*] Listening for command...")
                            recognizer.adjust_for_ambient_noise(source, duration=0.3)
                            audio = recognizer.listen(source, timeout=8, phrase_time_limit=12)

                        try:
                            command = recognizer.recognize_google(audio).lower()
                            print(f"[Command] {command}")
                            if is_dismissal(command):
                                speak(SLEEP_PHRASES.get(mode, "Going back to sleep."))
                                print("[*] Going back to sleep mode...")
                            else:
                                send_to_jenny(command)
                        except sr.UnknownValueError:
                            speak("I didn't catch that, Boss. Could you repeat?")
                        except sr.WaitTimeoutError:
                            speak("I didn't hear anything, Boss. Going back to sleep.")
                        wake_word_used = None

            except sr.UnknownValueError:
                pass
            except sr.WaitTimeoutError:
                pass

        except KeyboardInterrupt:
            print("\n[*] Stopping wake word detector...")
            speak("Goodbye Boss! I'll be here when you need me!")
            break
        except Exception as e:
            print(f"[Error] {e}")
            time.sleep(1)


if __name__ == '__main__':
    main()