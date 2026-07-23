# HeyGen LiveAvatar real-time integration (archived)

Built for House Of Wax, then set aside in favor of pre-recorded FAQ video clips
(see the main app). Kept here because it's a fully working, hard-won reference
for wiring up a live, conversational HeyGen avatar in a future project.

**Status when archived: fully working end-to-end** (Claude answer -> HeyGen
speech -> LiveAvatar video, verified live in a browser), but with a real
latency problem that made it unsuitable for House Of Wax's needs. See
"The real blocker" below before reusing this.

## What this is

Three pieces:
1. `liveavatar_service.py` -- a FastAPI backend. Issues LiveAvatar session
   tokens, answers questions with Claude (grounded in whatever knowledge base
   you point it at), and converts the answer to speech via HeyGen's voice API.
2. `streamlit_widget_snippet.py` -- the front-end widget (video + text input),
   embedded via `st.components.v1.html`, talking to the backend above.
3. `liveavatar_requirements.txt` -- the backend's own dependencies (FastAPI,
   uvicorn, httpx, pydantic). Deploy the backend separately from your main
   app (Railway worked well) -- Streamlit itself can't serve real-time
   endpoints to the widget the way this needs.

## Accounts and keys needed

This surprised us -- there are **three separate HeyGen-adjacent accounts**,
not one:

| What | Where | Used for |
|---|---|---|
| HeyGen Developer key | developers.heygen.com -> Overview -> Create API Key | Voices list, text-to-speech (`/v3/voices/speech`, `/v2/voices` on `api.heygen.com`) |
| LiveAvatar API key | **app.liveavatar.com/developers** -- a different site, different login/billing | Session tokens (`/v1/sessions/token` on `api.liveavatar.com`) |
| Avatar itself | Cloned in HeyGen's main Avatar Studio ("Clone a real person") | The face -- but see below, its ID doesn't carry over |

**The HeyGen Developer API key does not work against `api.liveavatar.com`,
and vice versa.** HeyGen's own docs say so explicitly. Budget for creating
both.

**Your HeyGen Avatar Studio avatar ID will not work as a LiveAvatar
`avatar_id`.** LiveAvatar has its own separate avatar library
(`GET https://api.liveavatar.com/v1/avatars/public` for 80+ stock presets,
no auth needed) and its own "Custom Avatars" you create *inside*
app.liveavatar.com -- a second cloning/consent recording, separate from the
one you did in HeyGen's main product. Custom avatars there require a paid
plan (Starter, $19/mo at time of writing) -- the Free tier only gives you
their stock presets, 10 credits/month, 2-minute session cap, 1 concurrent
session.

## Correct API surface (as of when this was built)

The starter code we were originally handed referenced an outdated/wrong SDK
shape (`StreamingAvatar` default export, `AvatarQuality`/`StreamingEvents`/
`TaskType`). None of that exists in the real package. Confirmed the real
shape via runtime introspection of `@heygen/liveavatar-web-sdk@0.0.18` and
HeyGen's own demo app source (`github.com/heygen-com/liveavatar-web-sdk`,
`apps/demo`):

- Import: `import { LiveAvatarSession, SessionEvent } from "@heygen/liveavatar-web-sdk"`
- Session token: `POST https://api.liveavatar.com/v1/sessions/token`, header
  `x-api-key: <LIVEAVATAR_API_KEY>`, body
  `{"mode": "LITE", "avatar_id": "<uuid>", "is_sandbox": false}`
- Construct: `new LiveAvatarSession(session_token, { apiUrl: "https://api.liveavatar.com", voiceChat: false })`
- Video: `session.on(SessionEvent.SESSION_STREAM_READY, () => session.attach(videoEl))`, then `await session.start()`
- Speak: **LITE mode does not do text-to-speech for you.** You generate
  audio yourself and call `await session.repeatAudio(base64Audio)`. There is
  no "just speak this text" in LITE mode -- that's FULL mode, which hands
  the entire conversation (including the AI answering) to HeyGen instead of
  your own backend.

## The real blocker: HeyGen's TTS is slow

This is why the feature got shelved for House Of Wax, not the plumbing above.

Measured live: Claude answered in **5.7s**. HeyGen's own
`POST /v3/voices/speech` (used to turn that answer into audio) took
**55.6s** for a 366-character answer. Total round trip: ~61s. That's not a
config issue -- HeyGen's TTS endpoint is built for pre-rendered video
generation, not real-time conversation, and it shows.

**If you reuse this**: don't use HeyGen's own TTS for the speak step.
HeyGen's own demo app pairs LITE mode with **ElevenLabs**
(`https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format=pcm_24000`,
returns base64 PCM ready for `repeatAudio()`) specifically because it's fast
enough for real-time use. That's a fourth account/API key, but it's the
difference between an 8-second response and a 60-second one.

## What we didn't get to

- Never swapped in a real custom LiveAvatar (stayed on a stock preset,
  "Shawn Therapist", to avoid the $19/mo Starter plan before validating the
  feature was worth it).
- Never load-tested concurrent visitors (Free tier caps at 1 concurrent
  session anyway).
- Never switched the TTS step to ElevenLabs (see above) -- that's the next
  thing to try if reviving this.
