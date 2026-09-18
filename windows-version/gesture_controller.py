"""
U.L.T.R.O.N. Gesture Controller
Hand-tracking PC control via MediaPipe Tasks API + OpenCV + PyAutoGUI
"""
import cv2
import time
import math
import json
import threading
import numpy as np
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.03
    HAS_PYAUTOGUI = True
except Exception:
    HAS_PYAUTOGUI = False

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_PATH = Path(__file__).resolve().parent / "data" / "hand_landmarker.task"


def _ensure_model():
    """Download the hand_landmarker.task model if it isn't present yet."""
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 0:
        return True
    try:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"[ULTRON] Downloading hand_landmarker.task ...")
        import urllib.request
        import ssl as _ssl
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        ok = MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 0
        print("[ULTRON] Model ready" if ok else "[ULTRON] Model download failed")
        return ok
    except Exception as exc:
        print(f"[ULTRON] Model download failed: {exc}")
        return False


landmarker = None
try:
    from mediapipe import Image as MPImage
    from mediapipe import ImageFormat as MPImageFormat
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    base_options = mp_python.BaseOptions(model_asset_path=str(MODEL_PATH))
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    if _ensure_model():
        landmarker = vision.HandLandmarker.create_from_options(options)
    HAS_MEDIAPIPE = landmarker is not None
except Exception as exc:
    print(f"[ULTRON] MediaPipe init failed: {exc}")
    HAS_MEDIAPIPE = False

try:
    import pc_actions
    HAS_PC_ACTIONS = True
except Exception:
    HAS_PC_ACTIONS = False

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
    "num_hands": 0,
    "hands": {
        "left": {"present": False, "gesture": "NO_HAND", "x": 0, "y": 0},
        "right": {"present": False, "gesture": "NO_HAND", "x": 0, "y": 0},
    },
    "control_mode": "pointer",   # pointer | windows | browser | system | media
    "orb_drive": False,          # when ON, hand position steers the orb instead of the mouse
    "orb_x": 0.0,
    "orb_y": 0.0,
    "orb_target_x": 0.0,
    "orb_target_y": 0.0,
    "cam_error": "",
}

MODE_ORDER = ["pointer", "windows", "browser", "system", "media"]

WINDOWS_ACTIONS = {
    "OPEN_PALM": "window_maximize",
    "FIST": "window_minimize",
    "TWO_FINGERS": "window_snap_left",
    "THUMBS_UP": "window_snap_right",
    "THUMBS_DOWN": "window_restore",
}

BROWSER_ACTIONS = {
    "POINT": "browser_search",
    "TWO_FINGERS": "browser_new_tab",
    "OPEN_PALM": "browser_close_tab",
    "FIST": "browser_back",
    "THUMBS_UP": "browser_refresh",
    "PINCH": "browser_forward",
    "DOUBLE_PINCH": "browser_reopen_tab",
}

SYSTEM_ACTIONS = {
    "OPEN_PALM": "screenshot",
    "TWO_FINGERS": "show_desktop",
    "FIST": "task_manager",
    "THUMBS_UP": "lock_pc",
    "POINT": "close_window",
}

MEDIA_ACTIONS = {
    "THUMBS_UP": "volume_up",
    "THUMBS_DOWN": "volume_down",
    "OPEN_PALM": "volume_mute",
    "TWO_FINGERS": "media_play_pause",
    "FIST": "media_next",
    "PINCH": "media_prev",
    "POINT": "open_app",
}

last_mode_action_time = 0
MODE_ACTION_COOLDOWN = 0.8
last_mode_cycle_time = 0
MODE_CYCLE_COOLDOWN = 1.2


def cycle_control_mode():
    global last_mode_cycle_time
    now = time.time()
    if (now - last_mode_cycle_time) < MODE_CYCLE_COOLDOWN:
        return
    last_mode_cycle_time = now
    cur = gesture_state.get("control_mode", "pointer")
    try:
        idx = MODE_ORDER.index(cur)
    except ValueError:
        idx = 0
    nxt = MODE_ORDER[(idx + 1) % len(MODE_ORDER)]
    gesture_state["control_mode"] = nxt
    gesture_state["gesture"] = f"MODE:{nxt.upper()}"
    return nxt


def process_two_hands(left, right):
    """Dual-hand combos: both palms toggles control mode, one fist+one palm pauses."""
    l_g = left["gesture"] if left else None
    r_g = right["gesture"] if right else None

    if l_g == "OPEN_PALM" and r_g == "OPEN_PALM":
        if is_stable("OPEN_PALM_OPEN_PALM", "combo"):
            return cycle_control_mode()

    if l_g == "FIST" and r_g == "OPEN_PALM":
        if is_stable("FIST_OPEN_PALM", "combo"):
            return "toggle"

    if l_g == "OPEN_PALM" and r_g == "FIST":
        if is_stable("OPEN_PALM_FIST", "combo"):
            return "toggle"

    return None

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
_hold_name = {}
_hold_start = {}

# CPU/GPU budget caps to stop ULTRON from freezing a low-end machine.
GESTURE_FPS = 12           # target hand-tracking frame rate
FRAME_INTERVAL = 1.0 / GESTURE_FPS
ENCODE_EVERY = 3           # only JPEG-encode every Nth frame (frame feed is a preview)
# Two hands roughly doubles tracking cost; adapt so a 2-hand tracker still fits the FPS budget.
MAX_HANDS = 2
MAX_HANDS_DRAW = 2        # cap limbs drawn per frame
last_heartbeat = time.time()

# Rolling gesture history (per hand slot) for UI feedback & stability debugging.
GESTURE_HISTORY_MAX = 8
_gesture_history = {"left": [], "right": []}


def _push_gesture_history(slot, gesture):
    buf = _gesture_history.get(slot, [])
    buf.append({"g": gesture, "t": round(time.time(), 3)})
    if len(buf) > GESTURE_HISTORY_MAX:
        del buf[: len(buf) - GESTURE_HISTORY_MAX]
    _gesture_history[slot] = buf


def get_gesture_history(slot="right"):
    return list(_gesture_history.get(slot, []))

CONFIG_PATH = "gesture_config.json"
DEFAULTS = {
    "smooth_factor": 0.3,
    "click_cooldown": 0.5,
    "scroll_cooldown": 0.15,
    "hold_threshold": 0.3,
    "gesture_fps": 12,
    "encode_every": 3,
    "orb_sensitivity": 1.0,
}
gesture_cfg = dict(DEFAULTS)


def load_config():
    global gesture_cfg, SMOOTH_FACTOR, CLICK_COOLDOWN, SCROLL_COOLDOWN, HOLD_THRESHOLD, GESTURE_FPS, FRAME_INTERVAL, ENCODE_EVERY
    gesture_cfg = dict(DEFAULTS)
    try:
        if Path(CONFIG_PATH).exists():
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k in DEFAULTS:
                    if k in data:
                        gesture_cfg[k] = data[k]
    except Exception:
        pass
    SMOOTH_FACTOR = float(gesture_cfg["smooth_factor"])
    CLICK_COOLDOWN = float(gesture_cfg["click_cooldown"])
    SCROLL_COOLDOWN = float(gesture_cfg["scroll_cooldown"])
    HOLD_THRESHOLD = float(gesture_cfg["hold_threshold"])
    GESTURE_FPS = max(1, int(gesture_cfg["gesture_fps"]))
    FRAME_INTERVAL = 1.0 / GESTURE_FPS
    ENCODE_EVERY = max(1, int(gesture_cfg["encode_every"]))


def save_config(updates):
    global gesture_cfg, SMOOTH_FACTOR, CLICK_COOLDOWN, SCROLL_COOLDOWN, HOLD_THRESHOLD, GESTURE_FPS, FRAME_INTERVAL, ENCODE_EVERY
    for k in DEFAULTS:
        if k in updates:
            try:
                gesture_cfg[k] = float(updates[k]) if k != "gesture_fps" and k != "encode_every" else int(updates[k])
            except Exception:
                pass
    SMOOTH_FACTOR = float(gesture_cfg["smooth_factor"])
    CLICK_COOLDOWN = float(gesture_cfg["click_cooldown"])
    SCROLL_COOLDOWN = float(gesture_cfg["scroll_cooldown"])
    HOLD_THRESHOLD = float(gesture_cfg["hold_threshold"])
    GESTURE_FPS = max(1, int(gesture_cfg["gesture_fps"]))
    FRAME_INTERVAL = 1.0 / GESTURE_FPS
    ENCODE_EVERY = max(1, int(gesture_cfg["encode_every"]))
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(gesture_cfg, f, indent=2)
    except Exception:
        pass
    return dict(gesture_cfg)


def get_config():
    return dict(gesture_cfg)


if Path(CONFIG_PATH).exists():
    load_config()


def dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def fingers_up(lm):
    return [
        lm[8].y < lm[6].y,
        lm[12].y < lm[10].y,
        lm[16].y < lm[14].y,
        lm[20].y < lm[18].y,
    ]


def thumb_orientation(lm):
    """Clear-up / clear-down thumb; anything else is ambiguous (FIST)."""
    if lm[4].y < (lm[3].y - 0.05) and not index_mid_down(lm):
        return "THUMBS_UP"
    if lm[4].y > (lm[6].y + 0.05) and not index_mid_down(lm):
        return "THUMBS_DOWN"
    return None


def index_mid_down(lm):
    return (lm[8].y > lm[6].y) and (lm[12].y > lm[10].y)


def classify_gesture(lm):
    index, middle, ring, pinky = fingers_up(lm)
    pinch = dist(lm[4], lm[8]) < 0.06
    if pinch and (dist(lm[4], lm[12]) < 0.06):
        return "DOUBLE_PINCH"
    if pinch:
        return "PINCH"
    if index and middle and not ring and not pinky:
        return "TWO_FINGERS"
    if index and not middle and not ring and not pinky:
        return "POINT"
    if index and middle and ring and pinky:
        return "OPEN_PALM"
    if not index and not middle and not ring and not pinky:
        thumb = thumb_orientation(lm)
        return thumb if thumb else "FIST"
    return "UNKNOWN"


def is_stable(gesture, slot="g"):
    """HOLD_THRESHOLD on a per-slot key so two hands don't reset each other."""
    now = time.time()
    if gesture != _hold_name.get(slot):
        _hold_name[slot] = gesture
        _hold_start[slot] = now
        return False
    return (now - _hold_start.get(slot, now)) >= HOLD_THRESHOLD


def set_orb_drive(on):
    gesture_state["orb_drive"] = bool(on)
    gesture_state["gesture"] = "ORB_ON" if on else "ORB_OFF"
    return gesture_state["orb_drive"]


# ---------------------------------------------------------------------------
# Tony Stark window control (self-contained via ctypes Win32 API)
# ---------------------------------------------------------------------------

def _get_foreground_window():
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        return hwnd or None
    except Exception:
        return None


def move_active_window(dx, dy):
    """Move the active (foreground) window by dx/dy screen pixels."""
    try:
        import ctypes
        import ctypes.wintypes as _wt
        dx, dy = int(dx), int(dy)
        if dx == 0 and dy == 0:
            return True
        user32 = ctypes.windll.user32
        hwnd = _get_foreground_window()
        if not hwnd:
            return False
        rect = _wt.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        return bool(user32.MoveWindow(hwnd, rect.left + dx, rect.top + dy,
                                      rect.right - rect.left, rect.bottom - rect.top, True))
    except Exception:
        return False


def _show_window_command(cmd):
    try:
        import ctypes
        hwnd = _get_foreground_window()
        if not hwnd:
            return False
        return bool(ctypes.windll.user32.ShowWindow(hwnd, cmd))
    except Exception:
        return False


def _win_hotkey(*keys):
    if HAS_PYAUTOGUI:
        try:
            pyautogui.hotkey(*keys)
            return True
        except Exception:
            pass
    return False


def window_maximize():
    return _show_window_command(3)      # SW_MAXIMIZE


def window_minimize():
    return _show_window_command(6)      # SW_MINIMIZE


def window_restore():
    return _show_window_command(9)      # SW_RESTORE


def window_snap_left():
    return _win_hotkey("win", "left")


def window_snap_right():
    return _win_hotkey("win", "right")


WINDOW_ACTION_RUNNERS = {
    "window_maximize": window_maximize,
    "window_minimize": window_minimize,
    "window_restore": window_restore,
    "window_snap_left": window_snap_left,
    "window_snap_right": window_snap_right,
}


def run_window_action(name):
    fn = WINDOW_ACTION_RUNNERS.get(name)
    if fn is None:
        return False
    try:
        return fn()
    except Exception:
        return False


WINDOW_MOVE_GAIN = 2.5
_win_grab = {
    "active": False,
    "hwnd": None,
    "last_x": 0.0,
    "last_y": 0.0,
}


def process_gesture(lm, gesture, role="right", slot="g"):
    global smooth_x, smooth_y, last_click_time, last_scroll_time, prev_index_y, gesture_state, last_mode_action_time, _win_grab
    now = time.time()

    is_pointer = role == "left"
    control_mode = gesture_state.get("control_mode", "pointer")

    if control_mode == "windows" and not is_pointer:
        if gesture == "POINT":
            # Grab-and-move the active window while pointing (pinch-to-move).
            if not _win_grab["active"]:
                _win_grab["active"] = True
                _win_grab["hwnd"] = _get_foreground_window()
                _win_grab["last_x"] = lm[8].x
                _win_grab["last_y"] = lm[8].y
                gesture_state["gesture"] = "WINDOW_GRAB"
            else:
                dx = (lm[8].x - _win_grab["last_x"]) * SCREEN_W * WINDOW_MOVE_GAIN
                dy = (lm[8].y - _win_grab["last_y"]) * SCREEN_H * WINDOW_MOVE_GAIN
                _win_grab["last_x"] = lm[8].x
                _win_grab["last_y"] = lm[8].y
                if move_active_window(dx, dy):
                    gesture_state["gesture"] = "WINDOW_MOVE"
        else:
            _win_grab["active"] = False
            _win_grab["hwnd"] = None
            action = WINDOWS_ACTIONS.get(gesture)
            if action and is_stable(gesture, slot) and (now - last_mode_action_time) > MODE_ACTION_COOLDOWN:
                run_window_action(action)
                last_mode_action_time = now
                gesture_state["gesture"] = f"WINDOWS:{action}"
        prev_index_y = None
        return

    if control_mode != "pointer" and not is_pointer:
        action_map = {
            "browser": BROWSER_ACTIONS,
            "system": SYSTEM_ACTIONS,
            "media": MEDIA_ACTIONS,
        }.get(control_mode, {})
        action = action_map.get(gesture)
        if action and is_stable(gesture, slot) and (now - last_mode_action_time) > MODE_ACTION_COOLDOWN:
            if HAS_PC_ACTIONS:
                pc_actions.run_action(action)
            last_mode_action_time = now
            gesture_state["gesture"] = f"{control_mode.upper()}:{action}"
        prev_index_y = None
        return

    if gesture == "POINT":
        if is_pointer or gesture_state["hands"]["left"]["gesture"] in ("NO_HAND", "UNKNOWN", "FIST"):
            raw_x = np.interp(lm[8].x, [0.15, 0.85], [0, SCREEN_W])
            raw_y = np.interp(lm[8].y, [0.15, 0.85], [0, SCREEN_H])
            if gesture_state.get("orb_drive"):
                gesture_state["orb_target_x"] = float((1.0 - lm[8].x) * 2 - 1)
                gesture_state["orb_target_y"] = float((lm[8].y - 0.5) * 2)
            else:
                smooth_x += (raw_x - smooth_x) * SMOOTH_FACTOR
                smooth_y += (raw_y - smooth_y) * SMOOTH_FACTOR
                gesture_state["mouse_x"] = int(smooth_x)
                gesture_state["mouse_y"] = int(smooth_y)
                if HAS_PYAUTOGUI:
                    pyautogui.moveTo(int(smooth_x), int(smooth_y))
            gesture_state["gesture"] = "POINTING"
        prev_index_y = None

    elif gesture == "PINCH":
        if is_pointer and gesture_state["gesture"].startswith("POINT"):
            if is_stable(gesture, slot) and (now - last_click_time) > CLICK_COOLDOWN:
                if HAS_PYAUTOGUI:
                    pyautogui.click()
                last_click_time = now
                gesture_state["gesture"] = "CLICK"
        elif not is_pointer:
            if is_stable(gesture, slot) and (now - last_click_time) > CLICK_COOLDOWN:
                if HAS_PYAUTOGUI:
                    pyautogui.rightClick()
                last_click_time = now
                gesture_state["gesture"] = "RIGHT_CLICK"
        prev_index_y = None

    elif gesture == "DOUBLE_PINCH":
        if not is_pointer:
            if is_stable(gesture, slot) and (now - last_click_time) > CLICK_COOLDOWN:
                if HAS_PYAUTOGUI:
                    pyautogui.doubleClick()
                last_click_time = now
                gesture_state["gesture"] = "DOUBLE_CLICK"
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
        if is_stable(gesture, slot):
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


# ---------------------------------------------------------------------------
# Hand overlay drawing (MediaPipe Tasks removed mp_draw.draw_landmarks)
# ---------------------------------------------------------------------------

DRAW_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]
TIP_LANDMARKS = (4, 8, 12, 16, 20)


def _draw_hand(frame, lm):
    """Simple cv2-only overlay: key landmark circles + connecting lines."""
    h, w = frame.shape[:2]
    pts = [(int(l.x * w), int(l.y * h)) for l in lm]
    for a, b in DRAW_CONNECTIONS:
        if a < len(pts) and b < len(pts):
            cv2.line(frame, pts[a], pts[b], (0, 255, 0), 2)
    for i, p in enumerate(pts):
        if i == 0:                       # wrist
            cv2.circle(frame, p, 5, (0, 165, 255), -1)
        elif i == 8:                     # index tip
            cv2.circle(frame, p, 6, (0, 0, 255), -1)
        elif i in TIP_LANDMARKS:         # other fingertips
            cv2.circle(frame, p, 4, (255, 0, 255), -1)
        else:
            cv2.circle(frame, p, 2, (255, 255, 0), -1)


def run_gesture_loop():
    if not HAS_MEDIAPIPE or landmarker is None:
        print("[ULTRON] MediaPipe not available")
        gesture_state["active"] = False
        return

    global last_heartbeat
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    gesture_state["active"] = True
    if not cap.isOpened():
        gesture_state["cam_error"] = "OPEN_FAILED"
        gesture_state["active"] = False
        print("[ULTRON] Camera 0 could not be opened")
        return

    frame_idx = 0
    timestamp_ms = 0
    no_frame_seconds = 0.0
    try:
        while gesture_state["active"]:
            iter_start = time.time()

            success, frame = cap.read()
            if not success:
                gesture_state["cam_error"] = "NO_FRAME"
                if no_frame_seconds <= 0:
                    print("[ULTRON] Camera open but no frame — is another app using it?")
                no_frame_seconds += 0.05
                if no_frame_seconds > 10:
                    gesture_state["cam_error"] = "CAMERA_BUSY"
                    no_frame_seconds = -1
                last_heartbeat = time.time()
                time.sleep(0.05)
                continue
            no_frame_seconds = 0.0
            gesture_state["cam_error"] = ""

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            timestamp_ms += int((time.time() - iter_start) * 1000) + 1
            result = landmarker.detect_for_video(
                MPImage(image_format=MPImageFormat.SRGB, data=rgb),
                timestamp_ms,
            )

            gesture = "NO_HAND"
            detected_hands = []

            if result.hand_landmarks:
                for i, hand in enumerate(result.hand_landmarks):
                    lm = hand
                    handedness = "Right"
                    try:
                        label = result.handedness[i][0].category_name
                        if label in ("Left", "Right"):
                            handedness = label
                    except Exception:
                        pass
                    key = handedness.lower()
                    palm_x = (lm[0].x + lm[5].x + lm[17].x) / 3
                    palm_y = (lm[0].y + lm[5].y + lm[17].y) / 3
                    detected_hands.append({
                        "side": key,
                        "lm": lm,
                        "x": palm_x,
                        "y": palm_y,
                    })
                    gesture_state["hands"][key]["present"] = True
                    gesture_state["hands"][key]["x"] = round(palm_x, 4)
                    gesture_state["hands"][key]["y"] = round(palm_y, 4)

            if detected_hands:
                gesture_state["num_hands"] = len(detected_hands)
                drawn = 0
                for h in detected_hands:
                    h["gesture"] = classify_gesture(h["lm"])
                    gesture_state["hands"][h["side"]]["gesture"] = h["gesture"]
                    _push_gesture_history(h["side"], h["gesture"])
                    if drawn < MAX_HANDS_DRAW:
                        _draw_hand(frame, h["lm"])
                        drawn += 1

                navigator = None
                commander = None
                for h in detected_hands:
                    if h["side"] == "left":
                        navigator = h
                    else:
                        commander = h

                if navigator:
                    process_gesture(navigator["lm"], navigator["gesture"], role="left", slot="left")
                if commander:
                    process_gesture(commander["lm"], commander["gesture"], role="right", slot="right")

                combo = process_two_hands(navigator, commander)
                if combo == "toggle":
                    gesture_state["enabled"] = not gesture_state["enabled"]
                    gesture_state["gesture"] = "TOGGLE_ON" if gesture_state["enabled"] else "TOGGLE_OFF"

                gesture = (commander or navigator)["gesture"]
            else:
                gesture_state["num_hands"] = 0
                for k in ("left", "right"):
                    gesture_state["hands"][k]["present"] = False
                    gesture_state["hands"][k]["gesture"] = "NO_HAND"

            gesture_state["gesture"] = gesture_state.get("gesture", gesture)
            last_heartbeat = time.time()

            # Only encode/preview a subset of frames to save CPU.
            # When 2 hands are tracked, halve the preview encode rate to keep the CPU budget safe.
            encode_every = ENCODE_EVERY * (2 if gesture_state.get("num_hands", 0) >= 2 else 1)
            frame_idx += 1
            if frame_idx % encode_every == 0:
                _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 55])
                gesture_state["frame"] = jpeg.tobytes()

            # Throttle to a low target FPS instead of spinning at webcam rate.
            elapsed = time.time() - iter_start
            sleep_for = FRAME_INTERVAL - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

    except Exception as e:
        print(f"[ULTRON] Gesture error: {e}")
    finally:
        cap.release()
        gesture_state["active"] = False


def start_gesture_control():
    if gesture_state.get("active"):
        return
    gesture_state["active"] = True
    t = threading.Thread(target=run_gesture_loop, daemon=True)
    t.start()


def stop_gesture_control():
    gesture_state["active"] = False


def get_gesture_status():
    return {
        "active": gesture_state.get("active", False),
        "gesture": gesture_state.get("gesture", "NO_HAND"),
        "enabled": gesture_state.get("enabled", False),
        "num_hands": gesture_state.get("num_hands", 0),
        "hands": gesture_state.get("hands", {}),
        "control_mode": gesture_state.get("control_mode", "pointer"),
        "orb_drive": gesture_state.get("orb_drive", False),
        "orb_x": gesture_state.get("orb_target_x", 0.0),
        "orb_y": gesture_state.get("orb_target_y", 0.0),
        "mouse_x": gesture_state.get("mouse_x", 0),
        "mouse_y": gesture_state.get("mouse_y", 0),
        "history_right": get_gesture_history("right"),
        "history_left": get_gesture_history("left"),
        "has_mediapipe": HAS_MEDIAPIPE,
        "has_pyautogui": HAS_PYAUTOGUI,
        "cam_error": gesture_state.get("cam_error", ""),
        "last_heartbeat": round(last_heartbeat, 3),
        "heartbeat_age": round(time.time() - last_heartbeat, 3),
    }