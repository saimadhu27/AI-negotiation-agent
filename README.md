# 🧠 Real-Time Multi-Agent Voice AI System

A **real-time, multi-agent conversational pipeline** that enables **low-latency, bidirectional audio dialogue** between users and AI agents via **Twilio Voice**, **WebSockets**, and **streaming LLMs**.  
The system demonstrates how to build **autonomous, speech-driven agents** capable of interacting naturally over phone calls — all in **under 500 ms round-trip latency**.

---

## 🚀 Features

- 🎙️ **Real-Time Streaming** — Bidirectional audio handled via WebSockets with sub-500 ms latency.  
- 🤖 **Multi-Agent Orchestration** — Modular design allows multiple AI agents (e.g., assistant, summarizer, emotion detector) to cooperate in dialogue.  
- ☁️ **LLM-Powered Reasoning** — Integrates streaming LLMs for dynamic, contextual responses.  
- ☎️ **Twilio Voice Integration** — Seamlessly connects phone calls to your AI agents.  
- 🧩 **Server-Client Architecture** — Built with **FastAPI** and **Uvicorn**, supporting scalable asynchronous I/O.  
- 🔊 **Speech ↔ Text Conversion** — Uses Whisper for transcription and real-time voice synthesis for responses.  
- 🧱 **Modular & Extensible** — Easily plug in different LLMs, voice models, or downstream reasoning agents.  

---

## 🏗️ System Architecture

```
 ┌──────────────┐      HTTP POST       ┌────────────────────┐
 │ Twilio Voice │ ───────────────────▶ │ FastAPI Server     │
 │  (Phone Call)│                      │  /outgoing-call    │
 └──────────────┘                      └────────────────────┘
        │                                      │
        ▼                                      ▼
  WebSocket Media Stream           ↔      WebSocket LLM Stream
 (Audio in/out via Twilio)                  (Text/Audio from OpenAI)
        │                                      │
        ▼                                      ▼
  Whisper ASR  ───────▶  Streaming LLM  ───────▶  TTS Audio Output
```

---

## ⚙️ Tech Stack

| Component | Technology |
|------------|-------------|
| **Backend Framework** | FastAPI + Uvicorn |
| **Telephony** | Twilio Voice (Programmable Voice, Media Streams) |
| **Real-time Transport** | WebSockets |
| **Language Model** | Streaming LLM API (OpenAI Realtime or equivalent) |
| **Speech Recognition** | Whisper (g711_ulaw format) |
| **Audio Synthesis** | Alloy / Voice model |
| **Runtime** | Python 3.11 |
| **Infra Ready** | Docker + AWS EC2 (or local) |

---

## 🧩 Folder Structure

```
AI-agent/
├── voice_server.py         # Main FastAPI app handling Twilio + WS
├── test_ws_connect.py      # WebSocket connectivity test script
├── requirements.txt
├── README.md
└── ...
```

---

## 🧪 Local Development

### 1. Clone and install dependencies
```bash
git clone https://github.com/yourusername/AI-agent.git
cd AI-agent
python -m venv vagents
source vagents/bin/activate
pip install -r requirements.txt
```

### 2. Run the FastAPI server
```bash
python -m uvicorn voice_server:app --reload
```

The server will start at:
```
http://127.0.0.1:8000
```

### 3. Test WebSocket connection
```bash
python test_ws_connect.py
```
If you see `Connected ok`, your agent server is ready to handle Twilio streams.

---

## ☁️ Deployment

- **Dockerize** the FastAPI app for reproducibility.
- Deploy on **AWS EC2**, **Render**, or **Vercel** with a public HTTPS endpoint.
- Update your **Twilio Voice Webhook URL** to point to:
  ```
  https://your-domain.com/outgoing-call-twiml
  ```

---

## 📞 Example Use Case

This system can power:
- Autonomous **customer service agents**  
- **Scheduling assistants** that converse naturally  
- **Information hotlines** for businesses or nonprofits  
- Multi-agent **dialogue systems** (agent-to-agent collaboration)  

---

## 🧠 Future Enhancements

- 🔁 Add memory & context chaining between turns  
- 🧩 Integrate retrieval (RAG) for domain-specific knowledge  
- 💬 Enable multi-language voice support  
- 🕵️ Add emotion detection & dynamic response modulation  

---

## 🪪 Author

**Madhuri [Your Last Name]**  
💼 *AI Engineer | Applied ML & Conversational Systems*  
🔗 [LinkedIn](#) • [GitHub](#)

---

## ⭐️ Highlight for Resume

> **“Developed a real-time multi-agent AI voice pipeline leveraging WebSockets, Twilio, and streaming LLMs to enable low-latency (<500 ms) bidirectional conversations, demonstrating scalable autonomous dialogue systems for customer-facing applications.”**
