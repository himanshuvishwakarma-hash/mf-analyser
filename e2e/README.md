# Z1N MF Analyser - End-to-end tests

Playwright tests that exercise the running stack.

## Prerequisites

1. The stack is running and seeded (~9k funds + scores):
   ```
   docker compose up -d
   # wait for first-boot cascade to complete (~60 min) OR seed locally
   ```
2. Node 20+ installed.

## Run

```
cd e2e
npm install
npx playwright install --with-deps chromium
npm test
```

## Skip when stack isn't ready

```
E2E_SKIP_SMOKE=1 npm test
```

## Tests

- `smoke.spec.ts`      - app load + search + fund detail
- `calculator.spec.ts` - SIP/lumpsum projection
- `export.spec.ts`     - Word factsheet download
