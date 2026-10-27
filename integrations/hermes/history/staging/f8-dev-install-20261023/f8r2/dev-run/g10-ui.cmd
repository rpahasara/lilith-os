@echo off
rem F8r2 G-10: existing finalized UI (worktree lilith-os-devui @ b9eb32c, unmodified) on 127.0.0.1 only, DEV-only
rem process env: server-side proxy -> IAP tunnel localhost:18765 -> lilith-dev-01:8765. No direct/browser URL, no capture token.
cd /d C:\Users\edufo\Documents\Projects\lilith-os-devui
set "LILITH_API_URL=http://127.0.0.1:18765"
set "NEXT_PUBLIC_LILITH_API_URL="
set "LILITH_OS_OWNER_CAPTURE_TOKEN="
npx next dev --hostname 127.0.0.1 -p 3210
