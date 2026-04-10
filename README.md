# Drishti 👁️ — AI-Powered Smart Glasses for the Visually Impaired

Drishti is a lightweight, camera-based AI assistant designed to help blind and visually impaired users navigate indoor environments like college campuses.  
It uses the **Moondream Vision Language Model (API)** for scene understanding, **continuous voice recognition** for hands-free control, and runs on any laptop connected to smart glasses hardware via serial (ESP32/Arduino).

---

## ✨ Features

### 🎤 Voice-Activated Commands (Always Listening)

Drishti runs a **background voice listener** — no buttons required. Just speak naturally:

| Say this | What it does |
|---|---|
| *"Navigate me to Library"* | Starts guided navigation to a target location |
| *"Take me to Cafeteria"* / *"Go to Lab 3"* | Same — multiple trigger phrases supported |
| *"Stop navigation"* / *"Cancel navigation"* | Cancels the active navigation session |
| *"Describe scene"* / *"What's around me"* | Describes surroundings — obstacles, objects, and positions |
| *"Read text"* / *"What does it say"* | Reads any visible English text (signs, boards, notices) aloud |
| *"Describe person"* / *"Who is this"* | Describes a person's appearance — clothing, glasses, beard, height |
| *"Save location"* / *"Remember this place"* | Identifies and saves the current place from visible signs |
| *"List locations"* / *"Saved places"* | Reads out all previously saved location names |
| *"Delete location Library"* / *"Forget location Lab"* | Removes a saved location |
| *"Help"* / *"What can you do"* | Lists all available commands aloud |

> 💡 The microphone **automatically pauses** while Drishti is speaking, so it won't hear its own voice.

### 📡 Serial Fallback

Hardware buttons on the glasses still work as a fallback. Send these strings over serial from your ESP/Arduino:

```
SCENE
READ
FACE
SAVE_LOCATION
LIST_LOCATIONS
DELETE_LOCATION Library
NAVIGATE Library
STOP_NAVIGATE
HELP
```

---

## 🧭 Navigation System

The navigation mode works using **vision-based landmark detection**, triggered entirely by voice:

1. The user says **"Navigate me to Library"** (or any trigger phrase + destination).
2. The system confirms: *"Navigating to Library. Keep the camera facing forward."*
3. Every **5 seconds**, the camera captures a frame and asks Moondream:
   - Are there **obstacles** ahead?  
   - Is there a **sign** pointing to the target?
4. The system speaks real-time directions: *"Obstacle on the left. Turn right."*
5. When the AI sees the destination, it says: *"You have arrived."*
6. To cancel at any time, say **"Stop navigation"**.

> All AI processing happens in the **cloud** via the Moondream API.  
> Your laptop only captures images and plays audio — it stays fast and lightweight.

---

## 📦 Setup

### 1. Clone
```bash
git clone https://github.com/abhinavtech23/Drishti.git
cd Drishti
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment
Create a `.env` file in the project root:
```
MOONDREAM_API_KEY=your_api_key_here
```

### 4. Hardware
- Connect your camera (update `CAM_INDEX` in `main.py` if needed)
- Connect your ESP/Arduino via USB (update `SERIAL_PORT` if needed)
- Ensure a working **microphone** is available on the laptop (required for voice commands)

### 5. Run
```bash
python main.py
```

On startup you will see:
```
AI Brain Running...
🎤 Voice listener active — always listening.
   Say 'Navigate me to [place]' to start navigation.
   Say 'Describe scene', 'Read text', 'Describe person', 'Help' for other commands.
```

---

## 🗂️ Project Structure

```
Drishti/
├── main.py              # Primary AI brain (voice listener + all commands + navigation)
├── main1.py             # Legacy version (scene/read/face only, serial-only)
├── face_detection.py    # (placeholder)
├── droidcam_search.py   # DroidCam utility
├── requirements.txt     # Python dependencies
├── locations.json       # Auto-generated saved locations (git-ignored)
├── .env                 # API key (git-ignored)
└── .gitignore
```

---

## 🛠️ Tech Stack

- **Vision AI**: Moondream-2 (cloud API)
- **Text-to-Speech**: Edge TTS (Microsoft)
- **Speech Recognition**: Google Speech Recognition (via `SpeechRecognition` library) — runs continuously in a background thread
- **Camera**: OpenCV
- **Hardware Interface**: PySerial
- **Concurrency**: Python `threading` + `queue` for non-blocking voice input
- **Language**: Python 3.10+
