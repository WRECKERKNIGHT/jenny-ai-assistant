"""
J.E.N.N.Y - Wake Word Detector
Listens for "Hey Jenny" or "Hey Friday" and activates the assistant
Lightweight - uses minimal CPU/RAM
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
WAKE_WORDS = ["hey jenny", "hey jenni", "hey jeeny", "hey friday", "hey jeni"]
LISTEN_TIMEOUT = 7
PHRASE_LIMIT = 10


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
    except Exception as e:
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
    idx = text_lower.find(wake_word)
    if idx >= 0:
        command = text_lower[idx + len(wake_word):].strip()
        if command.startswith((',', '.', '!', '?')):
            command = command[1:].strip()
        return command
    return text.strip()


def main():
    print("=" * 50)
    print("  J.E.N.N.Y - Wake Word Detector")
    print("  Say 'Hey Jenny' or 'Hey Friday' to activate")
    print("=" * 50)
    print("  Listening... (Ctrl+C to stop)")
    print("=" * 50)

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 1.0

    with sr.Microphone() as source:
        print("[*] Calibrating microphone...")
        recognizer.adjust_for_ambient_noise(source, duration=2)
        print("[*] Ready! Listening for wake words...")
        print()

    while True:
        try:
            with sr.Microphone() as source:
                audio = recognizer.listen(source, timeout=LISTEN_TIMEOUT, phrase_time_limit=PHRASE_LIMIT)

            try:
                text = recognizer.recognize_google(audio).lower()
                print(f"[Heard] {text}")

                if check_wake_word(text):
                    print("[*] Wake word detected!")
                    speak("Yes Boss? I'm listening!")

                    with sr.Microphone() as source:
                        print("[*] Listening for command...")
                        recognizer.adjust_for_ambient_noise(source, duration=0.3)
                        audio = recognizer.listen(source, timeout=8, phrase_time_limit=12)

                    try:
                        command = recognizer.recognize_google(audio).lower()
                        print(f"[Command] {command}")

                        if any(w in command for w in ["goodbye", "bye", "sleep", "stop listening"]):
                            speak("Going back to sleep mode, Boss! Say Hey Jenny to wake me up.")
                            print("[*] Going back to sleep mode...")
                        else:
                            send_to_jenny(command)

                    except sr.UnknownValueError:
                        speak("I didn't catch that, Boss. Could you repeat?")
                    except sr.WaitTimeoutError:
                        speak("I didn't hear anything, Boss. Going back to sleep.")

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
