"""
U.L.T.R.O.N. Gesture Controller
Hand-tracking PC control via MediaPipe + OpenCV + PyAutoGUI
"""
import cv2
import time
import math
import threading
import numpy as np

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.03
    HAS_PYAUTOGUI = True
except Exception:
    HAS_PYAUTOGUI = False

try:
    import mediapipe as mp
    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    )
    HAS_MEDIAPIPE = True
except Exception:
    HAS_MEDIAPIPE = False

SCREEN_W, SCREEN_H = (1920, 1080)
if HAS_PYAUTOGUI:
    try:
        SCREEN_W, SCREEN_H = pyautogui.size()
    except Exception:
        pass

gesture_state = {
    "active": False,
    "gesture": "NO_HAND",
    "enabled": False,
    "mouse_x": 0,
    "mouse_y": 0,
    "frame": None,
}

smooth_x = SCREEN_W // 2
smooth_y = SCREEN_H // 2
SMOOTH_FACTOR = 0.3
CLICK_COOLDOWN = 0.5
SCROLL_COOLDOWN = 0.15
HOLD_THRESHOLD = 0.3
last_click_time = 0
last_scroll_time = 0
last_gesture_name = None
gesture_hold_start = 0
prev_index_y = None


def dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def fingers_up(lm):
    return [
        lm[8].y < lm[6].y,
        lm[12].y < lm[10].y,
        lm[16].y < lm[14].y,
        lm[20].y < lm[18].y,
    ]


def classify_gesture(lm):
    index, middle, ring, pinky = fingers_up(lm)
    pinch = dist(lm[4], lm[8]) < 0.06
    if pinch:
        return "PINCH"
    if index and middle and not ring and not pinky:
        return "TWO_FINGERS"
    if index and not middle and not ring and not pinky:
        return "POINT"
    if index and middle and ring and pinky:
        return "OPEN_PALM"
    if not index and not middle and not ring and not pinky:
        return "FIST"
    if lm[4].y < lm[3].y and not index and not middle:
        return "THUMBS_UP"
    return "UNKNOWN"


def is_stable(gesture):
    global last_gesture_name, gesture_hold_start
    now = time.time()
    if gesture != last_gesture_name:
        last_gesture_name = gesture
        gesture_hold_start = now
        return False
    return (now - gesture_hold_start) >= HOLD_THRESHOLD


def process_gesture(lm, gesture):
    global smooth_x, smooth_y, last_click_time, last_scroll_time, prev_index_y, gesture_state
    now = time.time()

    if gesture == "POINT":
        raw_x = np.interp(lm[8].x, [0.15, 0.85], [0, SCREEN_W])
        raw_y = np.interp(lm[8].y, [0.15, 0.85], [0, SCREEN_H])
        smooth_x += (raw_x - smooth_x) * SMOOTH_FACTOR
        smooth_y += (raw_y - smooth_y) * SMOOTH_FACTOR
        gesture_state["mouse_x"] = int(smooth_x)
        gesture_state["mouse_y"] = int(smooth_y)
        if HAS_PYAUTOGUI:
            pyautogui.moveTo(int(smooth_x), int(smooth_y))
        gesture_state["gesture"] = "POINTING"
        prev_index_y = None

    elif gesture == "PINCH":
        if is_stable(gesture) and (now - last_click_time) > CLICK_COOLDOWN:
            if HAS_PYAUTOGUI:
                pyautogui.click()
            last_click_time = now
            gesture_state["gesture"] = "CLICK"
        prev_index_y = None

    elif gesture == "TWO_FINGERS":
        if prev_index_y is not None:
            dy = lm[8].y - prev_index_y
            if abs(dy) > 0.01 and (now - last_scroll_time) > SCROLL_COOLDOWN:
                if HAS_PYAUTOGUI:
                    pyautogui.scroll(int(-dy * 80))
                last_scroll_time = now
                gesture_state["gesture"] = "SCROLL"
        prev_index_y = lm[8].y

    elif gesture == "OPEN_PALM":
        if is_stable(gesture):
            gesture_state["enabled"] = not gesture_state["enabled"]
            gesture_state["gesture"] = "TOGGLE_ON" if gesture_state["enabled"] else "TOGGLE_OFF"
        prev_index_y = None

    elif gesture == "FIST":
        gesture_state["gesture"] = "PAUSED"
        prev_index_y = None

    elif gesture == "THUMBS_UP":
        gesture_state["gesture"] = "APPROVE"
        prev_index_y = None

    else:
        gesture_state["gesture"] = gesture
        prev_index_y = None


def run_gesture_loop():
    if not HAS_MEDIAPIPE:
        print("[ULTRON] MediaPipe not available")
        return

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    gesture_state["active"] = True

    try:
        while gesture_state["active"]:
            success, frame = cap.read()
            if not success:
                time.sleep(0.1)
                continue

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)

            gesture = "NO_HAND"

            if result.multi_hand_landmarks:
                hand = result.multi_hand_landmarks[0]
                lm = hand.landmark
                gesture = classify_gesture(lm)
                mp_draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)

                process_gesture(lm, gesture)
            else:
                gesture_state["gesture"] = "NO_HAND"
                prev_index_y_val = None

            gesture_state["gesture"] = gesture_state.get("gesture", gesture)

            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            gesture_state["frame"] = jpeg.tobytes()

    except Exception as e:
        print(f"[ULTRON] Gesture error: {e}")
    finally:
        cap.release()
        gesture_state["active"] = False


def start_gesture_control():
    t = threading.Thread(target=run_gesture_loop, daemon=True)
    t.start()


def stop_gesture_control():
    gesture_state["active"] = False


def get_gesture_status():
    return {
        "active": gesture_state.get("active", False),
        "gesture": gesture_state.get("gesture", "NO_HAND"),
        "enabled": gesture_state.get("enabled", False),
        "mouse_x": gesture_state.get("mouse_x", 0),
        "mouse_y": gesture_state.get("mouse_y", 0),
        "has_mediapipe": HAS_MEDIAPIPE,
        "has_pyautogui": HAS_PYAUTOGUI,
    }
