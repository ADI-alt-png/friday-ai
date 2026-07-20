# FRIDAY AI Assistant 🤖

**FRIDAY** — Iron Man style AI voice assistant for Windows. Voice-controlled automation, screen analysis, deep learning, and more.

## 🚀 Features

- **Voice Control** — Say "FRIDAY" then your command
- **System Control** — Open/close apps, websites, files
- **Screen Analysis** — OCR text reading, UI element detection, click/type automation
- **Live Monitoring** — Watch screen for errors and alerts
- **Deep Learning** — Intent classification, emotion detection, image recognition
- **Web Search** — Google search, news headlines, weather
- **Phone Remote** — Control PC from phone via browser
- **Tasks & Reminders** — Set reminders, manage tasks
- **Code Generation** — Write & paste code with AI
- **Email** — Compose Gmail drafts via voice
- **Auto-Learning** — Researches topics automatically
- **File Indexing** — Search through files using AI

## 📦 Requirements

- Python 3.11+
- Windows 10/11
- Microphone
- Internet connection (for API)

## ⚡ Quick Start

```bash
# Clone the repo
git clone https://github.com/ADI-alt-png/friday-ai.git
cd friday-ai

# Install dependencies
pip install -r requirements.txt

# Set your API key
# Option 1: Environment variable
set GROQ_API_KEY=your_key_here

# Option 2: Create friday_config.json (copy from example)
copy friday_config.example.json friday_config.json
# Edit friday_config.json and add your key

# Run FRIDAY
python friday.py
```

## 🎤 How to Use

1. Run `python friday.py`
2. FRIDAY says "Systems online"
3. Say **"FRIDAY"** to activate
4. FRIDAY says "Yes, Boss?"
5. Speak your command

### Example Commands

| Command | Action |
|---------|--------|
| `open chrome` | Opens Chrome |
| `search python tutorial` | Google search |
| `what time is it` | Current time |
| `tell me the news` | Top headlines |
| `weather in mumbai` | Weather search |
| `see my screen` | Capture screenshot |
| `read my screen` | OCR text from screen |
| `analyze screen` | AI screen analysis |
| `click on search` | Click UI element |
| `shutdown` | Shutdown PC |
| `play despacito` | Play on YouTube |
| `remember that ...` | Save to memory |
| `set reminder` | Create reminder |
| `dl classify` | AI intent classification |

## 🔧 API Configuration

FRIDAY uses **Groq API** with Llama 3.3 70B. Get your free API key:

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up and create an API key
3. Set it via environment variable or config file

## 🧠 Deep Learning

Optional DL features (auto-enabled if dependencies installed):
- Zero-shot intent classification
- Emotion & sentiment analysis
- Image description (vision transformer)

```bash
pip install transformers torch
```

## 📁 Project Structure

```
friday-ai/
├── friday.py              # Main assistant
├── api_config.py          # API configuration
├── deep_learning.py       # DL models
├── emotion_recognition.py # Emotion analysis
├── action_planner.py      # Intent routing
├── workflow_executor.py   # Automation workflows
├── android_controller.py  # Phone control
├── overlay.py             # Screen overlay
├── status_overlay.py      # Status display
├── ui.py                  # User interface
└── mobile_ui/             # Phone remote web UI
```

## 📜 License

MIT
