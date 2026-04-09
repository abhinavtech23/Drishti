import cv2
import serial
import requests
import base64
import edge_tts
import asyncio
import os
import io
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
# SERIAL
# =============================

ser = serial.Serial(SERIAL_PORT, BAUD)
print("Connected to serial:", SERIAL_PORT)

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
    communicate = edge_tts.Communicate(
        text=text,
        voice="en-US-GuyNeural"
    )
    await communicate.save("output.mp3")
    os.system("start output.mp3")

# =============================
# MOONDREAM CALL
# =============================

def call_moondream(frame, prompt_text):

    # Resize for consistency
    frame = cv2.resize(frame, (640, 480))

    # Convert BGR → RGB
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Convert to PIL image (same as Streamlit)
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

    response = requests.post(
        "https://api.moondream.ai/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30
    )

    result = response.json()
    return result["choices"][0]["message"]["content"]

# =============================
# PROMPTS
# =============================

SCENE_PROMPT = (
    "You are assisting a blind person. "
    "Describe only what is clearly visible in this image. "
    "Mention obstacles and direction (left, right, center)." \
    "if you are  not able to assist then describe the scene in the image "
    "Be short and factual. Do not imagine."
)

READ_PROMPT = (
    "Extract only clearly readable English text from this image. "
    "Return only the text exactly as written. "
    "If no readable text is present, say 'No readable text found.'"
)

# =============================
# MAIN LOOP
# =============================

while True:

    if ser.in_waiting:

        command = ser.readline().decode().strip()
        print("Command received:", command)

        # Let camera adjust exposure
        for _ in range(5):
            ret, frame = cap.read()

        if not ret:
            print("Frame capture failed.")
            continue

        # Save debug image
        cv2.imwrite("debug.jpg", frame)

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

# Cleanup (if script ever stops)
cap.release()
ser.close()