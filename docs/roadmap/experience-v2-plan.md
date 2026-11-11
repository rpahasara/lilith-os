# LILITH Experience V2: audit and implementation plan

Status: **ACCEPTED roadmap reference.** Phase 0 is delivered (see *Delivery status*). Audit date 2026-11-11, against `main` at `cda3d85`; the audit text below is kept as written.
Scope: the Next.js frontend (Command Center, Hsin/Presence, voice) and its private hosting.
Backend model and voice findings come from code plus the recorded 2026-11-02 diagnostics. Nothing was re-measured on PROD or DEV.

Boundaries for this whole workstream:
- No PROD or DEV deployments or restarts.
- No public exposure of the Core API, Hermes, canonical memory or authority services.
- No production credentials in frontend code.
- No canonical-memory, owner-authority or model-provider changes.
- No Hsin personality or identity changes without approval.
- UI PRs are not merged or deployed without separate authorization.
- #412, #416, #417 and #418 stay on their existing tracks. Timeline stays shadow, and P-5 stays disabled.

## Delivery status (updated 2026-11-11)

| Item | Delivered by | State |
|---|---|---|
| A: truthful status capsule | #419 → RC1 #426 | **On `main`** |
| B: disable controls with no function | #421 → RC1 #426 | **On `main`** |
| Home cards: real agenda or "unavailable", in the owner timezone | #422 → RC1 #426 | **On `main`** |
| C: conversation Stop, stale-reply safety, live-region announcements | #423 → RC1 #426 | **On `main`** |
| D: owner-facing voice toggle | #424 → RC1 #426 | **On `main`** |
| E: development-only diagnostics | #425 → RC1 #426 | **On `main`** |
| DEV deploy classifier: frontend-only lane | #427 | **On `main`** |

**RC1 #426** merged as `ccd045c` from the approved head `bccb485`. Main's Repository validation (run `43077524922`) passed with 249/249 combined tests. The DEV workflow (run `43078221038`) reported `MODE=CONTROL_ONLY_NO_DEPLOY` and `DEV_MUTATION=NONE`, and `lilith-os-api-dev` was not restarted. Details and the rollback plan are in `docs/roadmap/experience-v2-rc1.md`.

**#427** merged as `4d2e6ea`, also control-only. From now on, frontend-only merges do not redeploy the DEV Core API. Record: `docs/architecture/dev-deploy-classifier-frontend-only.md`.

**Next, in order:**
1. **Private web preview under our domain, owner-only** (§2, H1–H3): Cloudflare Tunnel + Access, the app-level Access-JWT check, and Origin checks. It needs a host decision.
2. **Hsin avatar optimization** (S1–S2): the 113 MB VRM. `public/**` is outside the frontend lane, so its own reviewed classifier addition is needed first, or one authorized same-code DEV redeploy.
3. **Mobile UI** (X1–X2): including the avatar-layer overflow on phones.

---

## 1. Maturity at a glance

| Area | Rating | Summary |
|---|---|---|
| Visual identity (glass, wine/orchid palette, wallpaper layers) | **Mature** | It is consistent across all workspaces. Keep it. |
| Command Center layout (desktop ≥1280px) | **Good** | Hsin is centred, with TODAY/NEXT floating around her. Command lifecycle, approval and history work against the Command Core. |
| Conversation | **Functional, thin** | It sends and gets a reply, with retry, a per-browser session and a 60-message local transcript. There is no streaming, no cancel, no aria-live, and the transcript is capped at 240px. It only exists on `/`. |
| Shell chrome (top bar, rail, status) | **Partly placeholder** | Search, Apps, Notifications (fake unread dot), Settings, Account and the Mic button have no handlers. The status capsule was hard-coded; that is fixed in PR A. |
| Workspaces: Career, Memory, Meetings | **Good, read-only** | They have live/demo diagnostics. Memory is still demo until the `/memory/*` endpoints are live through the proxy. |
| Automations, System | **Partial** | Automations works off `/system/status`. System is an honest static page with no telemetry source. |
| Responsive / mobile | **Weak** | The 88px rail is always visible (about 23% of a 375px phone). There is no mobile nav. The top-bar search is hidden below `md`. The home layout only stacks. |
| Accessibility | **Weak** | No live regions for replies. Icon buttons have labels but do nothing. No reduced-motion handling of the scene. |
| **Hsin overall** | **Mid prototype** | The renderer is real and carefully tuned. Behaviour is mostly a presence state machine with canned timing, and voice is off for the owner by default. |

### Hsin: what is real and what is a placeholder

| Capability | State | Evidence |
|---|---|---|
| VRM load and MToon render | **Real** | `avatar-scene.tsx` (3.6K lines), GLTFLoader with VRM and VRMA plugins, MToon to MeshBasic fallback, error boundary to a static presence. |
| Idle body motion | **Real** | Relaxed-idle VRMA plus procedural ambient idle (`hsin-ambient-idle.ts`) and rare motions (`hsin-rare-motion.ts`; auto-trigger off). |
| Blinking | **Real** | Driven through the VRM `blink` expression. |
| Gaze | **Real but basic** | Pointer-follow LookAt with manual yaw/pitch, on by default. It does not look at the input, the content or the speaker. |
| State expressions | **Partial** | Only `happy` and `puzzled` are driven, mapped per activity (idle, listening, thinking, speaking). Emotion from `presence.signal.emotion` is not mapped to `angry/sad/relaxed/surprised`. |
| Lip-sync | **Approximate** | Visemes (aa/ih/ou/ee/oh/sil) come from a text-vowel heuristic fitted to the decoded audio duration (`cue-fallback.ts`). Neither TTS route supplies alignment. It is audio-clock authoritative, so the mouth never runs past the audio. |
| Speaking motion | **Real** | `hsin-speaking-motion.ts`, gated on real audio. |
| Voice output | **Off by default** | The auto-speak production provider is ElevenLabs (`eleven_v3`). `autoSpeak` defaults to false, and the **only toggle is in the debug panel** (`NEXT_PUBLIC_PRESENCE_DEBUG=1`), so in normal use Hsin never speaks. With voice off, "speaking" is a canned 2.6 s transient. |
| Voice input / STT | **Placeholder** | The Mic button has no handler, and nothing calls `getUserMedia` or `SpeechRecognition`. |
| Interruption | **Typed only** | A new submit calls `lilithSpeech.stop()` and clears the visemes. A monotonic request id guards against a stale clip. There is no barge-in (no mic) and no stop button while she speaks. |
| Asset weight | **Blocking for the web** | The VRM is **113 MB** (`Hsin_FINAL_EXPORT_WORKING_FIXED.vrm`). It took 1.5 s on localhost and would take about 45 s at 20 Mbps. Unacceptable on a phone. |
| Debug surface | **Present** | 24 `console.info` diagnostic dumps in `avatar-scene.tsx` run on every load. |

---

## 2. Private hosting: recommendation

### What has to be protected
The Next server is not a thin static site: **it holds the service credentials** (`LILITH_OS_READ_TOKEN`, `LILITH_OS_WRITE_TOKEN`, `LILITH_OS_OWNER_CAPTURE_TOKEN`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`), and its routes relay conversation, drafts and tasks with those credentials attached. So **anyone who can reach the Next app can talk to Hsin and request approval-gated writes as the owner.** The edge gate is therefore the owner gate until a real owner session exists (`owner-capture-auth.ts` reports UNAVAILABLE by design). Two further points:
- There is no `src/proxy.ts`. In Next 16, Middleware is called Proxy. Nothing in the app checks who the caller is.
- The ordinary conversation, drafts and tasks POST/PATCH/DELETE routes do not check `Origin`. Only the evidence and capture paths do, The handlers parse JSON whatever the `Content-Type`, so a cross-site `text/plain` POST needs no preflight. Behind cookie-based edge auth that is a CSRF gap whenever the auth cookie is sent cross-site (SameSite=None), and only Lax/Strict closes it.

### Options compared

| | Cloudflare Tunnel + Access | Tailscale (tailnet only, `tailscale serve`) |
|---|---|---|
| Inbound ports on the VM | None (outbound tunnel) | None |
| Uses our domain | **Yes** (`os.<domain>`) | No: `*.ts.net`. A custom domain needs your own certs and split DNS. |
| Who can reach it | Anyone can reach the Cloudflare login, but only the allow-listed owner identity gets through | Only enrolled devices. Nothing is publicly resolvable. |
| Client requirement | A browser | The Tailscale app on every device (phone too) |
| Identity | Email OTP or Google IdP, optional device posture, session length policy | Tailnet device identity plus account |
| Static asset delivery (113 MB VRM) | CDN-cached at the edge | From the VM over WireGuard on every cold load |
| Third party sees traffic | Cloudflare terminates TLS (sees plaintext) | End-to-end WireGuard; Tailscale sees metadata only |
| Cost | Free (Zero Trust free plan) | Free (Personal) |
| Failure mode if misconfigured | A tunnel ingress rule could publish a backend port, so you need a deny-by-default ingress | `tailscale funnel` would make it public; never enable it |

### Recommendation: **Cloudflare Tunnel + Access, with defence in depth in the app**
It is the simplest option that meets "under our domain, owner only" and works from any browser. Keep Tailscale (or the existing IAP path) for **admin/SSH only**. Tailscale-only is the right fallback if a phone app is acceptable and the domain does not matter.

Target shape (nothing here is executed by this plan):

```
owner browser ──HTTPS──▶ Cloudflare Access (owner email allow-list, short session)
                               │ (Cloudflare Tunnel, outbound from host)
                               ▼
                     cloudflared ── ingress: os.<domain> → http://127.0.0.1:3000 ONLY
                               │                 catch-all: http_status:404
                               ▼
                     Next server (next start, standalone build), binds 127.0.0.1
                       ├─ src/proxy.ts: verify Cf-Access-Jwt-Assertion (JWKS, aud, iss, email) → else 403
                       ├─ mutating routes: require Origin == own origin
                       └─ server-only env: Core API tokens, TTS keys
                               │ localhost / private network only
                               ▼
                     Core API (127.0.0.1:8765), Hermes, memory, authority: never in tunnel ingress
```

Required controls, each with a test:
1. **The tunnel ingress lists exactly one hostname → Next.** Catch-all `http_status:404`. No route to 8765 or any other port. *Test:* `cloudflared tunnel ingress validate` plus `ingress rule https://os.<domain>/x` per hostname. Probe that `api.`/random subdomains return 404.
2. **Access application** on `os.<domain>/*` with an allow policy for the owner email only, session ≤ 24h, and no bypass rules. *Test:* a fresh browser gets the Access login. A non-owner email gets denied.
3. **App-level JWT check (`src/proxy.ts`).** Verify the `Cf-Access-Jwt-Assertion` header against the team JWKS (`https://<team>.cloudflareaccess.com/cdn-cgi/access/certs`), with `aud` = the application AUD tag and `email` = the owner. Fail closed when the variables are unset in production. *Test:* a direct request to the origin without the header gets 403. A forged JWT gets 403. A valid JWT gets 200.
4. **Origin check on every non-GET route** (conversation, drafts, tasks). *Test:* a cross-origin POST gets 403.
5. **Next binds 127.0.0.1.** The VM firewall has no inbound rule for 3000. *Test:* external `curl http://<vm-ip>:3000` times out.
6. **Security headers** (CSP, `frame-ancestors 'none'`, HSTS via Cloudflare). *Test:* check the response headers.

### Where Next runs: an open dependency
- **The GCP trial ends 2026-11-18.** The host choice should follow the migration decision, not precede it.
- Running Next on the PROD VM gives the simplest networking (localhost to the API), but that VM is an e2-small with 2 GB shared with Hermes. Build elsewhere (`output: "standalone"`) and measure RSS before committing. This is a PROD change that needs separate authorization.
- The alternative is a small separate host that reaches the API over a private link (Tailscale between hosts, or VPC-internal). It isolates the frontend from PROD but adds one more moving part.

---

## 3. Model, latency and voice findings (no provider changes)

| # | Finding | Evidence | Recommendation (approval needed?) |
|---|---|---|---|
| M1 | **No streaming.** The UI waits for the whole reply. The proxy timeout is 178 s and the only feedback is three dots. | `conversation/route.ts`, `conversation-view.tsx` | First **measure**: have the proxy return `Server-Timing` (upstream ms), and log time-to-reply client-side. Streaming (SSE from the relay) is a backend change and comes later. |
| M2 | **No cancel.** There is no AbortController, so a slow turn cannot be stopped. | `conversation-provider.tsx` | A frontend-only Stop button aborts the browser request. Note that the backend turn still completes. |
| M3 | Full-agent turn ≈ **23K fixed input tokens**. The lean social turn ≈ 4.7K. | 2026-11-02 measurements | The biggest latency/cost lever is context. Splitting the ops sections from SOUL is identity-adjacent and **needs owner approval**. |
| M4 | Fallback chain exists (full-agent fallback recorded in #349). | recorded | Add per-turn route/latency to the existing decision log for a weekly p50/p95 report (read-only analysis). |
| V1 | **Voice unreachable for the owner.** The toggle exists only in the debug panel. | `avatar-presence.tsx:1229` | Expose a user-facing **Voice on/off** in the shell, persisted per browser. Frontend only, same provider. |
| V2 | Time-to-first-audio scales with reply length, because the whole reply (≤4096 chars) is synthesized first. | `speech-controller.ts`, TTS routes | Sentence-chunked synthesis, playing chunk 1 while chunk 2 synthesizes. Same provider and voice. Frontend plus an unchanged route. |
| V3 | Lip-sync is heuristic (no alignment). | `cue-fallback.ts` | ElevenLabs `/with-timestamps` gives character alignment from the same provider and voice, so it is not a provider change. Confirm with the owner because it changes the API call shape. |
| V4 | `eleven_v3` is ElevenLabs' expressive model, not its low-latency one. | `elevenlabs/route.ts` | Only measure for now. Changing the TTS model changes Hsin's voice, so it is **identity and needs approval**. |
| C1 | Continuity is per browser: the session id and 60 messages live in localStorage. Phone and desktop are separate threads, and "Clear" starts a new backend session. | `conversation-provider.tsx` | With hosting, a shared device leaks the transcript. Add an "end session on sign-out" control, and later a server-side history read route (backend). |

---

## 4. Implementation sequence

Each item is one PR, independently testable, and keeps the current design language. **Q** = quick win (frontend only, no backend, no env). **H** = hosting. **X** = experience. Backend items are marked as such and need separate authorization.

### Phase 0: truthfulness and dead controls (Q, this week)
| PR | Change | Acceptance test |
|---|---|---|
| **A** (opened) | Status capsule from a real read-only `/system/status` probe: Online + measured API ms / Demo data / Backend unreachable | `npm run test:core` (13 shell-health checks). In the preview: 503 → "Demo data", 502 → "Backend unreachable", 200 → "Online · API n ms". |
| B | Hide or disable the dead controls (Search, Apps, Notifications dot, Settings, Account, Mic) until they are wired. Keep the layout slots so the look is unchanged. | Every visible button either does something or is `disabled` with a tooltip. No fake unread dot. |
| C | Conversation: `role="log"` + `aria-live="polite"` on the transcript, a **Stop** button (AbortController), elapsed-time hint after 10 s | Screen reader announces the reply. Stop aborts the fetch and restores the input. Self-test for the abort path. |
| D | User-facing **Voice on/off** toggle (V1), persisted, defaulting to off | Toggle on, then a reply speaks via the existing provider. Toggle off, then the canned transient. Nothing else changes. |
| E | Silence the avatar `console.info` dumps unless `NEXT_PUBLIC_PRESENCE_DEBUG=1` | Production console has no `[Hsin …]` lines. |

### Phase 1: private hosting (H; depends on the migration host decision)
| PR | Change | Acceptance test |
|---|---|---|
| H1 | `src/proxy.ts` Cloudflare Access JWT verification (fail closed in production) plus an Origin check on all mutating routes. Repo only, inert until env is set. | Self-tests: no JWT gets 403, bad `aud` gets 403, expired gets 403, valid gets pass. Cross-origin POST gets 403. Dev mode is unaffected. |
| H2 | `output: "standalone"`, security headers/CSP, documented `cloudflared` config with deny-by-default ingress (template only) | `next build` passes. Headers are present. `cloudflared tunnel ingress validate` passes on the template. |
| H3 | **Ops (separate authorization):** create the Access app and tunnel, install on the chosen host | The control tests 1–6 in §2 all pass, and are recorded. |

### Phase 2: UX V2 (X)
| PR | Change | Acceptance test |
|---|---|---|
| X1 | Mobile shell: the rail collapses to a bottom tab bar below `md`, with a compact top bar | 375×812: no horizontal scroll, all six workspaces reachable, Hsin ≥ 45% of the viewport on `/`. |
| X2 | Conversation surface: taller transcript with an expand-to-panel option. Conversation is reachable from every workspace (persistent dock), not only `/`. | Navigate mid-conversation and the transcript and input persist. Speech is not cut by the route change unless the owner stops it. |
| X3 | Approval flow polish: review/approve states visible in history, with clear irreversible-action copy | Existing Command Core self-tests plus a manual approve/deny walkthrough. |
| X4 | Settings sheet (voice, motion, reduced-motion, session end). Account shows the signed-in Access identity (read from the JWT, display only). | Settings persist. `prefers-reduced-motion` stops procedural idle. |

### Phase 3: Hsin V2 (X; any personality or identity change needs approval)
| PR | Change | Acceptance test |
|---|---|---|
| S1 | **Asset diet:** Draco/Meshopt geometry plus KTX2/WebP textures, target ≤ 20 MB, versioned immutable cache headers. Keep the original as the source of truth. | Visual diff against the current renders at 3 framings. Load time at 20 Mbps throttling ≤ 8 s. Same morph targets and expressions present. |
| S2 | Progressive presence: show the orb/static presence immediately, then cross-fade to the VRM when it is ready | First paint < 2 s on throttled 4G. No blank centre while loading. |
| S3 | Gaze targets: look at the input on focus, at the user while speaking, idle saccades. Respect reduced motion. | Self-test of the gaze target state machine. Visual check. |
| S4 | Emotion mapping from `signal.emotion` to the available VRM expressions, with weight caps | Each presence emotion shows a distinct, capped expression. Owner sign-off on the look (identity-adjacent). |
| S5 | Sentence-chunked TTS (V2) plus a "Stop speaking" control | Time-to-first-audio ≤ 1.5 s after the reply for a 600-char reply (measured). Stop ends audio and closes the mouth in under 100 ms. |
| S6 | Alignment-driven lip-sync from ElevenLabs timestamps (V3), keeping the heuristic as the fallback | Viseme timing error against the alignment is under 80 ms. Fallback still works when alignment is missing. |
| S7 | Voice input (push-to-talk via the browser STT where available) plus barge-in that stops speech | Speaking while she talks stops audio within 300 ms. Needs an owner decision on STT (browser vs provider). |

### Phase 4: backend-side (separate authorization each)
- M1 streaming relay (SSE)
- M3 context reduction (identity rehearsal required)
- C1 server-side history route
- the latency report (M4)

### Dependencies
- H3 depends on the migration and host decision (GCP trial ends 2026-11-18).
- X4 Account depends on H1.
- S5/S6 depend on D (the voice toggle).
- X2 should land before S7.
- S1 should land before any public-network (H3) use. A 113 MB first load over the tunnel is the most visible failure.

### Recommended order
A → B → C → D → E (frontend truthfulness and control, about 1 week) ∥ host decision → H1 → H2 → S1 → S2 → H3 → X1 → X2 → S5 → S3 → X3 → X4 → S4 → S6 → S7.
