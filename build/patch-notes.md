## v0.1.6 — War Room Diagnostic Logging & stderr Fix

**Bug Fixes**
- Fixed `start-server-online.bat` silently suppressing all server error/warning output (`2>nul` on uvicorn), which made v0.1.5 diagnostics invisible

**Diagnostics**
- Added `print()` diagnostics to WebSocket connect, match creation, hero selection, class selection, and profile loading — all visible in server console
- Added client-side `console.log` tracing for match creation and hero_select dispatch
- Server now prints `✓ Connect OK` or `✗ Connect MISMATCH` on every WebSocket connection with full active-match state
