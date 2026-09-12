"""
J.E.N.N.Y - Wake Word Detector
Listens for "Hey Jenny" or "Hey Friday" and activates the assistant
Lightweight - uses minimal CPU/RAM

Usage: python wakeword.py [--server http://localhost:3005] [--energy 300]
                          [--timeout 7] [--push-to-talk]
"""

import sys
import time
import json
import urllib.request
import threading

try:
    import speech_recognition as sr
except ImportError:
    print("Install SpeechRecognition: pip install SpeechRecognition")
    sys.exit(1)

SERVER_URL = "http://localhost:3005"
WAKE_WORDS = ["hey jenny", "hey jenni", "hey jeeny", "hey friday", "hey jeni",
              "hello jenny", "hello friday", "jenny", "friday"]
LISTEN_TIMEOUT = 7
PHRASE_LIMIT = 10
ENERGY_THRESHOLD = 300
PUSH_TO_TALK = False


def server_online(timeout=2):
    """Preflight /api/health check so we don't listen for nothing."""
    try:
        req = urllib.request.Request(f"{SERVER_URL}/api/health", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def speak(text):
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        for v in voices:
            if any(name in v.name.lower() for name in ['david', 'mark']):
                engine.setProperty('voice', v.id)
                break
        engine.setProperty('rate', 175)
        engine.setProperty('volume', 0.9)
        engine.say(text)
        engine.runAndWait()
    except Exception:
        pass


def send_to_jenny(text):
    try:
        import urllib.request
        import urllib.parse
        req = urllib.request.Request(
            f"{SERVER_URL}/api/chat",
            data=json.dumps({"message": text}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            reply = data.get("reply", "I didn't quite get that, Boss!")
            speak(reply)
            print(f"[Jenny] {reply}")
            return reply
    except Exception:
        speak("Server is not running. Please start the server first, Boss!")
        return None


def check_wake_word(text):
    text_lower = text.lower().strip()
    for word in WAKE_WORDS:
        if word in text_lower:
            return True
    return False


def extract_command(text, wake_word):
    text_lower = text.lower().strip()
    idx = text_lower.find(wake_word.lower())
    if idx >= 0:
        command = text_lower[idx + len(wake_word):].strip()
        if command.startswith((',', '.', '!', '?')):
            command = command[1:].strip()
        return command
    return text.strip()


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
    print("  Say 'Hey Jenny' or 'Hey Friday' to activate")
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
                    if any(w in command for w in ["goodbye", "bye", "sleep", "stop listening", "dismiss"]):
                        speak("Going back to sleep mode, Boss! Say Hey Jenny to wake me up.")
                        print("[*] Going back to sleep mode...")
                    else:
                        send_to_jenny(command)
                    continue

                found = None
                for word in WAKE_WORDS:
                    if word in text:
                        found = word
                        break

                if found:
                    print("[*] Wake word detected!")
                    speak("Yes Boss? I'm listening!")
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
                            if any(w in command for w in ["goodbye", "bye", "sleep", "stop listening", "dismiss"]):
                                speak("Going back to sleep mode, Boss! Say Hey Jenny to wake me up.")
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
