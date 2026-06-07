import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import sys

# ==========================================
# 1. INITIAL CONFIGURATIONS & SAFETY CONTROLS
# ==========================================
# Safety Feature: Instantly kill the script by slamming your actual mouse pointer 
# into any of the 4 physical corners of your monitor screen.
pyautogui.FAILSAFE = False  
pyautogui.PAUSE = 0.05    # Short delay after OS input injection to maintain stability

# Fetch native monitor dimensions
screen_w, screen_h = pyautogui.size()

# Initialize MediaPipe Hands Pipeline
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    max_num_hands=1,            # Focus purely on tracking a single dominant hand
    min_detection_confidence=0.7, # High threshold to ignore background noise shapes
    min_tracking_confidence=0.7   # Ensures stability during continuous movement
)

# Open default webcam stream
cap = cv2.VideoCapture(0)

# ==========================================
# 2. FILTER & STATE MANAGEMENT SETUP
# ==========================================
# Exponential Moving Average (EMA) Co-efficient 
# (Value between 0 and 1. Lower = smoother/slower cursor; Higher = snappier/jitterier cursor)
alpha = 0.20  
smoothed_x, smoothed_y = 0, 0

# Debounce State Flags (Prevents the system from spamming clicks/hotkeys 30 times a second)
click_triggered = False
menu_triggered = False
close_triggered = False

# Overlay Customization UI tracking strings
current_action = "System Initialized"
ui_color = (255, 0, 0) # Standard BGR Blue

print("----------------------------------------------------------------")
print(" GESTURE INTERACTION ENGINE ONLINE")
print(" -> EMERGENCY ABORT: Move physical mouse to any screen corner.")
print(" -> MANUAL QUIT: Press 'q' while focusing the video window.")
print("----------------------------------------------------------------")

# ==========================================
# 3. CORE PROCESSING LOOP
# ==========================================
while cap.isOpened():
    success, frame = cap.read()
    if not success:
        print("Error: Live video stream frame dropped.")
        continue

    # Mirror the frame horizontally so your movements aren't inverted
    frame = cv2.flip(frame, 1)
    h, w, c = frame.shape

    # Convert the color space from BGR (OpenCV standard) to RGB (MediaPipe requirement)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_frame)

    # Check if any hand structure matches the model architecture
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            # Render visual mesh connections onto the video window preview
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            landmarks = hand_landmarks.landmark

            # A. CAPTURE & FILTER INTERACTION POINTER (Index Finger Tip - Landmark ID 8)
            raw_x = int(landmarks[8].x * w)
            raw_y = int(landmarks[8].y * h)

            # Apply the Exponential Moving Average formula to scrub micro-tremor jitter
            smoothed_x = int(alpha * raw_x + (1 - alpha) * smoothed_x)
            smoothed_y = int(alpha * raw_y + (1 - alpha) * smoothed_y)

            # Interpolate camera resolution coordinate space into native OS screen resolution.
            # We map an inner 70% deadzone region of the camera to the full screen size
            # so you don't have to reach your physical arm out of the camera view.
            cursor_x = np.interp(smoothed_x, (w * 0.15, w * 0.85), (10, screen_w - 10))
            cursor_y = np.interp(smoothed_y, (h * 0.20, h * 0.80), (10, screen_h - 10))

            # B. EVALUATE DISCRETE FINGER COMBINATIONS
            # Define specific Tip IDs and corresponding lower Knuckle (PIP joint) IDs
            finger_tips = [8, 12, 16, 20]     # Index, Middle, Ring, Pinky
            finger_knuckles = [6, 10, 14, 18] # Respective joints below tips
            
            # Binary state check: If Y-coord of Tip is lower than Knuckle, finger is up
            fingers_up = [1 if landmarks[tip].y < landmarks[knuckle].y else 0 
                          for tip, knuckle in zip(finger_tips, finger_knuckles)]

            # Check thumb configuration separately (X-axis comparison for side movement)
            thumb_up = 1 if landmarks[4].x > landmarks[3].x else 0
            total_fingers = sum(fingers_up)

            # C. INTERACTION MAPPING DETERMINATION
            
            # --- INTERACTION 1: CLOSED FIST GESTURE (Close Tab / Window Command) ---
            if total_fingers == 0 and thumb_up == 0:
                current_action = "TRIGGER OUT: Executing Tab Close (Ctrl+W)"
                ui_color = (0, 0, 255) # Red Alert
                
                if not close_triggered:
                    import sys
                    if sys.platform == "darwin":
                        pyautogui.hotkey('command', 'w' , interval=0.1) # MacOS hotkey
                    else:
                        pyautogui.hotkey('ctrl', 'w' , interval=0.1)    # Windows/Linux hotkey
                    close_triggered = True # Locks action until state resets

            # --- INTERACTION 2: ONE SINGLE FINGER UP (Smooth Mouse Navigation Mode) ---
            elif total_fingers == 1 and fingers_up[0] == 1:
                current_action = "NAVIGATING: Mapping Cursor Coordinates"
                ui_color = (255, 0, 0) # Clear Blue
                
                # Command OS cursor to follow mapped coordinates smoothly
                pyautogui.moveTo(cursor_x, cursor_y)
                
                # Instantly clear trigger blocks when user deliberately switches back to navigation mode
                click_triggered = False
                menu_triggered = False
                close_triggered = False

            # --- INTERACTION 3: TWO FINGERS UP (Left Click Action) ---
            elif total_fingers == 2 and fingers_up[0] == 1 and fingers_up[1] == 1:
                current_action = "TRIGGER OUT: Primary Click Dispatched"
                ui_color = (0, 255, 255) # Yellow Target
                
                if not click_triggered:
                    pyautogui.click()
                    click_triggered = True # Locks click state machine execution

            # --- INTERACTION 4: THREE FINGERS UP (Open System Menu Command) ---
            elif total_fingers == 3 and fingers_up[0] == 1 and fingers_up[1] == 1 and fingers_up[2] == 1:
                current_action = "TRIGGER OUT: Launching OS System Menu"
                ui_color = (0, 255, 0) # Green Success
                
                if not menu_triggered:
                    if sys.platform == "darwin":
                        pyautogui.hotkey('command', 'space') # Mac Spotlight Search
                    else:
                        pyautogui.press('win')               # Windows Start Menu
                    menu_triggered = True # Locks hotkey trigger state machine

            # --- SYSTEM STATE PROTECTION LOCK CLEAR ---
            else:
                # Releases lock protections safely if the hand falls into mixed/intermediary shapes
                click_triggered = False
                menu_triggered = False
                close_triggered = False
                current_action = "Scanning... System Ready"
                ui_color = (255, 0, 0)

    # ==========================================
    # 4. HEADS UP DISPLAY VISUAL HUD OVERLAY
    # ==========================================
    # Top Action status panel background bar block
    cv2.rectangle(frame, (0, 0), (w, 60), (30, 30, 30), -1)
    cv2.putText(frame, current_action, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, ui_color, 2)
    
    # Bottom Instruction manual guide layout label text
    cv2.rectangle(frame, (0, h - 35), (w, h), (15, 15, 15), -1)
    cv2.putText(frame, "1 Finger: Move Mouse | 2 Fingers: Click | 3 Fingers: Menu | Fist: Close Tab", 
                (15, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)

    # Render complete video stream matrix frame window
    cv2.imshow("OS Gesture Controller Pipeline", frame)

    # Process immediate manual kill key event ('q')
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Clean execution stack teardown processing
cap.release()
cv2.destroyAllWindows()
print("\nSystem Engine Process terminated cleanly.")