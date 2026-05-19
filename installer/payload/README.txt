Z1N MF Analyser - End-user notes
================================

The system tray icon (bottom-right corner of your screen) gives you:
  - Open Dashboard    -> opens the app in your browser
  - View Logs         -> shows the launcher log file
  - Restart Backend   -> restarts the data service
  - Quit              -> stops the backend and exits

Data location
-------------
All data lives inside Docker volumes managed by Docker Desktop. The
launcher's own log + state file are at:
  %LOCALAPPDATA%\Z1NMFAnalyser\

Configuration
-------------
Edit %LOCALAPPDATA%\Z1NMFAnalyser\payload\.env to change ports,
admin token, Sentry DSN, etc. Restart the launcher (tray menu) after
any change.

Troubleshooting
---------------
- Docker Desktop must be running for the app to work.
- If the dashboard does not open at http://localhost:5173 after launch,
  give it 30-60 seconds on first run (images need to download).
- Logs: tray menu -> View Logs.
