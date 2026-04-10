import cv2
import serial
import requests
import base64
import edge_tts
import asyncio
import os
import io
import time
import json
import threading
import queue
import speech_recognition as sr
from dotenv import load_dotenv
from PIL import Image

# =============================
# CONFIG
# =============================

CAM_INDEX = 2
SERIAL_PORT = "COM7"   # CHANGE if needed
BAUD = 115200

load_dotenv()
MOONDREAM_API_KEY = os.getenv("MOONDREAM_API_KEY")

if not MOONDREAM_API_KEY:
    print("MoonDream API key not found.")
    exit()

# =============================
# LOCATIONS INIT
# =============================

LOCATIONS_FILE = "locations.json"
if os.path.exists(LOCATIONS_FILE):
    with open(LOCATIONS_FILE, "r") as f:
        locations = json.load(f)
else:
    locations = {}

# =============================
# VOICE GLOBALS
# =============================

is_speaking = False
voice_queue = queue.Queue()

# =============================
# NAVIGATION PROMPT
# =============================

def get_navigate_prompt(target):
    return (
        f"You are helping a blind person navigate to '{target}'. "
        f"Look at the image carefully. "
        f"1. First, warn about any immediate obstacles (stairs, walls, poles, people) and their position (left, right, center). "
        f"2. Then, check if you see signs or the '{target}' itself. "
        f"Give a single short instruction like 'Obstacle ahead on the left. Turn right.' or 'Path is clear. Go straight.' or 'You have arrived at {target}.' "
        f"If nothing useful is visible say 'Path clear. Keep walking.' Do not imagine."
    )

# =============================
# VOICE COMMAND PARSER
# =============================

def parse_voice_command(text):
    """Parse natural speech into a system command."""
    text = text.lower().strip()

    # Navigation triggers — "navigate me to [place]", "take me to [place]", etc.
    nav_phrases = ["navigate me to", "take me to", "go to", "navigate to", "bring me to", "walk me to"]
    for phrase in nav_phrases:
        if phrase in text:
            target = text.split(phrase, 1)[1].strip()
            if target:
                return f"NAVIGATE {target}"
            return None

    # Stop navigation
    if any(p in text for p in ["stop navigation", "stop navigating", "cancel navigation", "stop navigate"]):
        return "STOP_NAVIGATE"

    # Scene
    if any(p in text for p in ["describe scene", "what's around", "what is around", "describe surrounding", "surroundings"]):
        return "SCENE"

    # Read
    if any(p in text for p in ["read text", "read this", "what does it say", "read aloud"]):
        return "READ"

    # Face / Person
    if any(p in text for p in ["describe person", "who is this", "describe face", "who is that"]):
        return "FACE"

    # Save location
    if any(p in text for p in ["save location", "save this place", "remember this place", "remember location"]):
        return "SAVE_LOCATION"

    # List locations
    if any(p in text for p in ["list locations", "saved places", "saved locations", "my locations"]):
        return "LIST_LOCATIONS"

    # Delete location
    for phrase in ["delete location", "remove location", "forget location"]:
        if phrase in text:
            target = text.split(phrase, 1)[1].strip()
            if target:
                return f"DELETE_LOCATION {target}"
            return None

    # Help
    if text.strip() == "help" or "available commands" in text or "what can you do" in text:
        return "HELP"

    return None

# =============================
# CONTINUOUS VOICE LISTENER
# =============================

def continuous_voice_listener():
    """Background thread that continuously listens for voice commands."""
    recognizer = sr.Recognizer()
    while True:
        # Pause listening while the system is speaking (avoids self-echo)
        if is_speaking:
            time.sleep(0.5)
            continue
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = recognizer.listen(source, timeout=4, phrase_time_limit=6)
                text = recognizer.recognize_google(audio).lower().strip()
                if text:
                    cmd = parse_voice_command(text)
                    if cmd:
                        print(f"🎤 Voice: \"{text}\" → {cmd}")
                        voice_queue.put(cmd)
                    else:
                        print(f"🎤 Heard (ignored): \"{text}\"")
        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except Exception as e:
            print(f"Voice listener error: {e}")
            time.sleep(1)

# =============================
# SERIAL
# =============================

try:
    ser = serial.Serial(SERIAL_PORT, BAUD)
    print("Connected to serial:", SERIAL_PORT)
except Exception as e:
    print("Could not connect to serial port:", e)
    ser = None

# =============================
# CAMERA
# =============================

cap = cv2.VideoCapture(CAM_INDEX)

if not cap.isOpened():
    print("Camera not detected.")
    exit()

print("AI Brain Running...")

# =============================
# TEXT TO SPEAK
# =============================

async def speak(text):
    global is_speaking
    is_speaking = True
    try:
        communicate = edge_tts.Communicate(
            text=text,
            voice="en-US-GuyNeural"
        )
        await communicate.save("output.mp3")
        os.system("start output.mp3")

        # Wait so speech doesn't overlap listening
        duration = max(1.0, len(text) * 0.08)
        time.sleep(duration)
    finally:
        is_speaking = False

# =============================
# MOONDREAM CALL
# =============================

def call_moondream(frame, prompt_text):

    # Resize for consistency
    frame = cv2.resize(frame, (640, 480))

    # Convert BGR → RGB
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Convert to PIL image
    image = Image.fromarray(frame_rgb)

    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {MOONDREAM_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "moondream-2",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_base64}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 200
    }

    try:
        response = requests.post(
            "https://api.moondream.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        result = response.json()
        return result.get("choices", [{}])[0].get("message", {}).get("content", "Error processing.")
    except Exception as e:
        print("API Request failed", e)
        return "Network error."

# =============================
# PROMPTS
# =============================

SCENE_PROMPT = (
    "You are assisting a blind person. "
    "Describe only what is clearly visible in this image. "
    "Mention obstacles and direction (left, right, center)."
    "if you are  not able to assist then describe the scene in the image "
    "Be short and factual. Do not imagine."
)

READ_PROMPT = (
    "Extract only clearly readable English text from this image. "
    "Return only the text exactly as written. "
    "If no readable text is present, say 'No readable text found.'"
)

FACE_PROMPT = (
    "Describe the person in this image. "
    "Mention gender, approximate height (short, average, tall), "
    "beard, glasses, hairstyle, and clothing. "
    "Be short and factual. Do not guess beyond what is visible."
)

SAVE_LOCATION_PROMPT = (
    "Identify a short name for the specific room, building, or location in this image based on signs or distinctive features. "
    "Return ONLY the short name (e.g., 'Library', 'Classroom 101'). Do not say anything else."
)

# =============================
# CAPTURE FRAME HELPER
# =============================

def capture_stable_frame(warmup=5):
    """Capture a frame after letting the camera auto-expose."""
    for _ in range(warmup):
        ret, frame = cap.read()
    if ret:
        cv2.imwrite("debug.jpg", frame)
    return ret, frame

# =============================
# START VOICE LISTENER THREAD
# =============================

voice_thread = threading.Thread(target=continuous_voice_listener, daemon=True)
voice_thread.start()
print("🎤 Voice listener active — always listening.")
print("   Say 'Navigate me to [place]' to start navigation.")
print("   Say 'Describe scene', 'Read text', 'Describe person', 'Help' for other commands.")

# =============================
# MAIN LOOP
# =============================

navigating = False
target_location = ""
last_nav_time = 0
nav_step_count = 0

while True:

    command = None

    # --- Check serial input (hardware buttons still work as fallback) ---
    if ser and ser.in_waiting:
        command = ser.readline().decode().strip()
        print("📡 Serial command:", command)

    # --- Check voice command queue ---
    if not command:
        try:
            command = voice_queue.get_nowait()
        except queue.Empty:
            pass

    # --- Process command (from either source) ---
    if command:

        ret, frame = capture_stable_frame()
        if not ret:
            print("Frame capture failed.")
            continue

        if command == "SCENE":
            print("Processing SCENE...")
            result = call_moondream(frame, SCENE_PROMPT)
            print("Result:", result)
            asyncio.run(speak(result))

        elif command == "READ":
            print("Processing READ...")
            result = call_moondream(frame, READ_PROMPT)
            print("Result:", result)
            asyncio.run(speak(result))

        elif command == "FACE":
            print("Processing FACE...")
            result = call_moondream(frame, FACE_PROMPT)
            print("Result:", result)
            asyncio.run(speak(result))

        elif command == "SAVE_LOCATION":
            print("Processing SAVE LOCATION...")
            asyncio.run(speak("Saving location. Please hold the camera steady."))
            result = call_moondream(frame, SAVE_LOCATION_PROMPT)
            loc_name = result.strip().strip('"').strip("'")

            if 0 < len(loc_name) < 40:
                locations[loc_name] = {
                    "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                with open(LOCATIONS_FILE, "w") as f:
                    json.dump(locations, f, indent=2)
                print("Saved:", loc_name)
                asyncio.run(speak(f"Location saved as {loc_name}."))
            else:
                asyncio.run(speak("Could not identify a clear location name. Try pointing at a sign."))

        elif command == "LIST_LOCATIONS":
            if locations:
                names = ", ".join(locations.keys())
                msg = f"Saved locations are: {names}."
            else:
                msg = "No saved locations yet."
            print(msg)
            asyncio.run(speak(msg))

        elif command.startswith("DELETE_LOCATION"):
            parts = command.split(" ", 1)
            if len(parts) > 1:
                del_name = parts[1].strip()
                if del_name in locations:
                    del locations[del_name]
                    with open(LOCATIONS_FILE, "w") as f:
                        json.dump(locations, f, indent=2)
                    asyncio.run(speak(f"Deleted {del_name} from saved locations."))
                else:
                    asyncio.run(speak(f"{del_name} not found in saved locations."))
            else:
                asyncio.run(speak("Please specify which location to delete."))

        elif command.startswith("NAVIGATE"):
            parts = command.split(" ", 1)
            target = parts[1].strip() if len(parts) > 1 else None

            if target:
                print("Starting navigation to:", target)
                navigating = True
                target_location = target
                nav_step_count = 0
                last_nav_time = time.time()
                asyncio.run(speak(f"Navigating to {target}. Keep the camera facing forward."))
            else:
                asyncio.run(speak("Could not determine navigation target. Try again."))

        elif command == "STOP_NAVIGATE":
            navigating = False
            target_location = ""
            asyncio.run(speak("Navigation stopped."))

        elif command == "HELP":
            help_msg = (
                "Available voice commands: "
                "Navigate me to, followed by a place name, to start navigation. "
                "Stop navigation, to cancel. "
                "Describe scene, to hear what is around you. "
                "Read text, to read visible text aloud. "
                "Describe person, to hear a person's description. "
                "Save location, to remember this place. "
                "List locations, to hear saved places. "
                "Help, to hear this message again."
            )
            asyncio.run(speak(help_msg))

    # --- Periodic navigation check (every 5 seconds) ---
    if navigating and time.time() - last_nav_time > 5:
        last_nav_time = time.time()
        nav_step_count += 1
        ret, frame = capture_stable_frame(warmup=3)
        if ret:
            prompt = get_navigate_prompt(target_location)
            print(f"NAV [{target_location}] step {nav_step_count} checking...")
            result = call_moondream(frame, prompt)
            print("NAV result:", result)
            if len(result.strip()) > 2:
                asyncio.run(speak(result))
            if "arrived" in result.lower():
                navigating = False
                target_location = ""
                print("Arrived at target.")
                asyncio.run(speak("You have reached your destination."))

    time.sleep(0.1)  # Prevent CPU spinning

# Cleanup
cap.release()
if ser:
    ser.close()