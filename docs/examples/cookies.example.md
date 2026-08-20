# Optional board cookies (Phase 6)

Advanced only. Prefer APIs. Read [`docs/LEGAL.md`](../LEGAL.md) first.

## Setup

1. Set `SCRAPE_COOKIES_ENABLED=true` in `.env`
2. Create `data/cookies/` (created automatically; **gitignored**)
3. Add one file per board id (e.g. `linkedin`, `indeed`, `glassdoor`):

| File | Format |
|------|--------|
| `{board}.txt` | Cookie header line `name=value; name2=value2` **or** Netscape cookie export |
| `{board}.json` | List of Playwright-style cookie objects |

4. Restart the API. Setup shows which boards have cookie files (values never displayed).

## Example — header line (`indeed.txt`)

```text
# Do not commit this file
SESSION_ID=your_session_value; other=...
```

## Example — JSON (`linkedin.json`)

```json
[
  {
    "name": "li_at",
    "value": "REPLACE_ME",
    "domain": ".linkedin.com",
    "path": "/",
    "secure": true,
    "httpOnly": true
  }
]
```

## Behavior

- HTTP scrapers send a `Cookie` header when a file exists for that `source_id`
- Playwright scrapers inject cookies into the browser context
- With `SCRAPE_COOKIES_STRICT=true` (default): longer delays + concurrency 1
- Captcha / challenge pages still **abort** — never solved
- **No auto-apply**

## Safety

- Never commit `data/cookies/` or paste cookies into chat / PRs
- Rotate / delete cookies if leaked
- Disable the feature (`SCRAPE_COOKIES_ENABLED=false`) when unused
