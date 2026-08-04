# Legal and acceptable-use stance

**This is not legal advice.** Laws and site terms vary by jurisdiction. You are
responsible for how you run CareerPilot and which job boards you enable.

## What CareerPilot is for

CareerPilot is a **local-first** assistant that helps you:

- Discover public / API-accessible job listings
- Score them against your resume
- Notify you (local file, and optionally WhatsApp/email when configured)
- Draft tailored resume PDFs for **your** review

You choose what to apply to. CareerPilot does **not** submit applications for you.

## Prefer APIs and public feeds

Use official APIs, RSS, or clearly public listing endpoints whenever possible.
They are the most permission-aligned way to fetch jobs.

## Scraping

Some boards are accessed via HTTP/browser automation. That may violate a site’s
Terms of Service even when pages are publicly visible. Risks include account
bans, IP blocks, and civil claims. Run scrapers politely (low rate, backoff) and
disable sources you are not comfortable using.

## No captcha solving or access-control circumvention

CareerPilot’s policy:

- **Do not** integrate captcha solvers or anti-bot bypass kits
- **Do not** defeat login walls, device checks, or other access controls
- Playwright scrapers are **best-effort**: they parse listing cards when present.
  Challenge pages typically yield zero cards (no bypass). HTTP API clients may
  still mark a source unhealthy on clear challenge responses.

Browser-like headers, delays, and optional proxies are for polite, human-paced
traffic — not for circumventing blocks.

## No auto-apply

Automated apply flows, mass form submission, or “AI applies on your behalf” are
**out of scope** and intentionally excluded from the product roadmap. Discovery
and notification stay human-in-the-loop.

## Cookies and accounts

If you optionally supply session cookies for a board:

- They must be **your** cookies from a session you control
- Aggressive use can get **your** account restricted or banned
- Prefer API sources; treat cookie mode as advanced and high-risk
- Never commit cookies or tokens to git

## Privacy

Resumes and generated PDFs are intended to stay on your machine. Do not commit
`resumes/`, `generated_resumes/`, databases, or `.env` files. Notifiers only
send content you configure them to send.

## Your responsibility

By enabling a job source or notifier, you accept that site’s terms and any
applicable law. Maintainers provide software as-is for personal / portfolio use;
they do not authorize misuse of third-party services.
