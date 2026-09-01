# AI Doc Reader — Web UI

A React front-end for the AI Doc Reader RAG Q&A API. Upload PDFs, ask
questions, and get answers grounded in the source text with page-level
citations.

<p align="center">
  <em>Sidebar (documents) · Chat area (Markdown answers + source cards) · Document details</em>
</p>

## Stack

| Concern | Choice |
| --- | --- |
| Framework | React 18 + TypeScript |
| Build tool | Vite 5 |
| Styling | Tailwind CSS 3 (semantic design tokens, light/dark) |
| Icons | lucide-react |
| Markdown | react-markdown + remark-gfm |
| State | React hooks only (`useDocuments`, `useChat`, `useConnection`, `useTheme`) |
| HTTP | `fetch` wrapped in a small typed client (timeouts, abort, typed errors) |

No other runtime dependencies. No global state library.

## Prerequisites

- Node.js 18+
- The **FastAPI backend running** (this repo's root project). From the
  repo root:

  ```bash
  uvicorn app.main:app --reload
  # -> http://127.0.0.1:8000
  ```

  The backend already enables CORS (`cors_allow_origins`, default `*`),
  so a browser on another origin can call it.

## Setup

```bash
cd web
npm install
cp .env.example .env      # optional — see below
npm run dev               # http://localhost:3000
```

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | Base URL of the FastAPI backend |

- Only `VITE_*` variables are exposed to the browser (Vite convention).
- **Never put LLM / embedding / vector-DB credentials here.** The browser
  only ever talks to FastAPI; every provider secret stays server-side in
  the backend's own `.env`.
- The API URL can also be changed at runtime from the in-app **Settings**
  dialog (⚙️ in the header). That value is stored in `localStorage`
  (`aidr:apiBaseUrl`) and overrides the build-time default — handy for
  pointing a deployed UI at a different backend without rebuilding.

## Scripts

| Command | Description |
| --- | --- |
| `npm run dev` | Dev server with HMR on port 3000 |
| `npm run build` | Type-check (`tsc --noEmit`) then production build to `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run typecheck` | Type-check only |

## Production build

```bash
npm run build     # outputs dist/
npm run preview   # sanity-check the build
```

## Deploying to Vercel

This is a static SPA — any static host works. For Vercel:

1. **Import the repo** in the Vercel dashboard.
2. Set **Root Directory** to `web`.
3. Framework preset: **Vite** (auto-detected). Build command
   `npm run build`, output directory `dist` — already declared in
   [`vercel.json`](./vercel.json).
4. Add an **Environment Variable** `VITE_API_BASE_URL` pointing at a
   backend the browser can reach over HTTPS.

   > ⚠️ The FastAPI backend in this project listens on `127.0.0.1:8000`
   > (local only). A Vercel-hosted page can reach that **only from a
   > machine that is itself running the backend** — browsers do allow an
   > HTTPS page to call `http://127.0.0.1`, and CORS is already open. To
   > share the UI publicly you must also host the backend somewhere with
   > a public HTTPS URL (Render / Railway / Fly / a VM) and set
   > `VITE_API_BASE_URL` to that. Users can also override the URL at
   > runtime via the in-app Settings dialog.

Or from the CLI:

```bash
npm i -g vercel
cd web
vercel            # first run links the project; set Root Directory = . when prompted
vercel --prod
```

## Project structure

```
web/
├── index.html                  # pre-paint theme script, #root
├── vite.config.ts              # @ alias -> src, dev port 3000
├── tailwind.config.js          # semantic color tokens, dark mode = class
├── vercel.json                 # Vite preset, SPA rewrite, headers
└── src/
    ├── main.tsx
    ├── App.tsx                  # composition root: wires hooks -> layout
    ├── index.css               # design tokens (light/dark), component classes, markdown styles
    ├── types/index.ts          # backend response types + UI-only shapes
    ├── api/
    │   ├── client.ts           # base-URL resolution, timeout/abort, ApiError
    │   ├── documents.ts        # list / get / upload / delete
    │   ├── chat.ts             # ask (optionally scoped to a document)
    │   └── health.ts           # connection check
    ├── hooks/
    │   ├── useDocuments.ts     # list, selection, upload (staged), delete
    │   ├── useChat.ts          # per-document conversation, thinking stages, retry, abort
    │   ├── useConnection.ts    # polls /health for the status indicator
    │   └── useTheme.ts         # light/dark, persisted
    ├── lib/format.ts           # bytes / dates / score formatting
    └── components/
        ├── layout/             # AppLayout, Header, Sidebar
        ├── documents/          # DocumentList, DocumentItem, UploadModal, DocumentDetails
        ├── chat/               # ChatWindow, ChatMessage, ChatInput, SourceCard, ThinkingIndicator, EmptyState
        └── common/             # Button, Modal, Drawer, StatusDot, ThemeToggle, SettingsModal, LoadingState
```

## API integration

All calls go through `src/api/`. Nothing calls `fetch` directly from a
component.

| UI action | Request |
| --- | --- |
| Load sidebar | `GET /documents` |
| Upload | `POST /documents/upload` (multipart `file`) |
| Delete | `DELETE /documents/{id}` |
| Ask (scoped to selected doc) | `POST /chat` `{ question, document_id }` |
| Source "open page" link / details "Open PDF" | `GET /documents/{id}/file` |
| Connection indicator | `GET /health` (polled every 20s) |

`ApiError` carries a `kind` (`network` / `timeout` / `http` / `parse`)
and a `userMessage` that is always safe to render — backend stack traces
are never surfaced.

## Behaviour notes

- **One document at a time.** Selecting a document starts a fresh
  conversation and scopes retrieval to it. The API layer already
  supports an unscoped (all-documents) search, so a future
  "Search across all documents" mode is a small addition.
- **Thinking stages** (`Searching → Reading → Generating`) are driven on
  a timer — the backend call is a single synchronous request, so the
  stages communicate *that* RAG retrieval is happening, not real
  sub-step progress. If the backend later streams stage events, wire
  them into `useChat`.
- **"Not found" is not an error.** When the answer has no sources or
  matches a "couldn't find it" pattern, it renders as a neutral
  informational message.
- **Accessibility:** focus-trapped modals/drawers, `Esc` to close,
  visible focus rings, `aria-live` on the message list, labelled icon
  buttons, keyboard-operable everything.
