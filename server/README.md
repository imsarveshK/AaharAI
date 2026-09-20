# AaharAI private API

The Android app calls this server for natural-language structure only. The Groq key never enters
the APK, and Groq never supplies nutrition values.

1. Copy `.env.example` to `.env` and put the real key after `GROQ_API_KEY=`.
2. From the repository root, run:

   ```bash
   uv sync
   uv run uvicorn aaharai_api.main:app --host 127.0.0.1 --port 8000
   ```

3. Android Emulator uses `http://10.0.2.2:8000` by default. For a private HTTPS server, set
   `AAHARAI_API_BASE_URL` before building the app.

Do not commit `server/.env`, expose the development server publicly, or put `GROQ_API_KEY` in
Gradle/local.properties.
