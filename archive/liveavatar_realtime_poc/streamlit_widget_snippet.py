"""
Streamlit widget snippet for the live, conversational HeyGen LiveAvatar
integration -- pulled out of House Of Wax's app.py when the project moved to
a simpler pre-recorded FAQ video approach instead. Kept here as a working
reference for reuse on a future project.

Depends on: liveavatar_service.py (the FastAPI backend in this same folder)
being deployed somewhere reachable, with its URL in Streamlit's Secrets as
LIVEAVATAR_BACKEND_URL, and LIVEAVATAR_AVATAR_ID also set (used here only as
a "is this configured" gate -- the backend itself is where the avatar ID is
actually used, via its own HEYGEN_AVATAR_ID env var).

See README.md in this folder for the full story: what worked, what didn't,
and the real bottleneck that killed this approach for House Of Wax (HeyGen's
own text-to-speech step took 30-60+ seconds per answer).
"""
import streamlit as st


def liveavatar_configured():
    try:
        return bool(st.secrets.get('LIVEAVATAR_BACKEND_URL', '')) and bool(st.secrets.get('LIVEAVATAR_AVATAR_ID', ''))
    except Exception:
        return False


def liveavatar_enabled():
    # Swap `setting(...)` for whatever this project's own settings/feature-flag
    # helper is -- House Of Wax used a simple SQLite/Supabase app_settings table.
    return liveavatar_configured() and setting('liveavatar_enabled', 'false') == 'true'


def render_liveavatar_widget():
    if not liveavatar_enabled():
        return
    backend_url = safe(st.secrets.get('LIVEAVATAR_BACKEND_URL', '')).rstrip('/')
    st.markdown('### Ask House Of Wax')
    st.caption('Talk to our AI assistant about grading, buying, or selling.')
    st.components.v1.html(f"""
    <div id="avatar-container">
      <video id="avatarVideo" autoplay playsinline style="width:100%;max-width:400px;border-radius:8px;"></video>
      <div style="display:flex;gap:8px;margin-top:8px;">
        <input id="questionInput" placeholder="Ask about grading, buying, selling..." style="flex:1;padding:6px;"/>
        <button id="askButton">Ask</button>
      </div>
      <div id="avatarStatus" style="font-size:12px;color:#888;margin-top:4px;"></div>
    </div>

    <script type="module">
      import {{ LiveAvatarSession, SessionEvent }} from "https://esm.sh/@heygen/liveavatar-web-sdk";

      const statusEl = document.getElementById("avatarStatus");
      let session;

      async function init() {{
        try {{
          const tokenRes = await fetch("{backend_url}/get-token", {{ method: "POST" }});
          if (!tokenRes.ok) throw new Error("token request failed");
          const {{ session_token }} = await tokenRes.json();

          session = new LiveAvatarSession(session_token, {{ apiUrl: "https://api.liveavatar.com", voiceChat: false }});
          session.on(SessionEvent.SESSION_STREAM_READY, () => {{
            session.attach(document.getElementById("avatarVideo"));
          }});
          await session.start();
        }} catch (err) {{
          statusEl.textContent = "The avatar assistant is unavailable right now.";
        }}
      }}

      document.getElementById("askButton").onclick = async () => {{
        const input = document.getElementById("questionInput");
        const question = input.value;
        if (!question.trim()) return;
        statusEl.textContent = "Thinking...";
        try {{
          const res = await fetch("{backend_url}/ask", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ question }}),
          }});
          const {{ answer, audio }} = await res.json();
          if (session && audio) await session.repeatAudio(audio);
          statusEl.textContent = "";
        }} catch (err) {{
          statusEl.textContent = "Sorry, that didn't go through -- try again.";
        }}
        input.value = "";
      }};

      init();
    </script>
    """, height=520)
