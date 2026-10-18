# Secure email list

Design spec for [#239](https://github.com/Data-Science-Link/perspectiverse/issues/239). This file is the spec. It does not add a signup form, a database, or a sender.

**Risk of the build:** high. It stores people's addresses and sends them mail. Michael approves this spec before any of that is built. The 2026-10-18 decision that simple fixes ship immediately does not cover this.

**Refs:** #62 (the formatted digest), #50 (where signup sits in the UI), #240 (the visitor chat that shares the backend below).

Prices below were read from the provider pages on **2026-10-18**.

## Outcome

A visitor can ask to receive the digest the site already formats. They confirm by email. They can leave with one click. Addresses never land in the public repo or in `data.json`. Nothing is sent to the list until Michael has received a test copy and said yes.

## What exists today

`assemble_email` in `pipeline/briefs.py` builds `digest` on every edition: a subject (`This week: …`) and the published planets, largest first, each with up to six arguments and a disagreement paragraph. `pipeline/assemble.py` writes that object onto `data.json` from the main `topics` list only. Newspaper-section planets are not in the digest.

The site shows that object. The menu item **Weekly email digest** and the header mail button open `EmailView` in `src/components/ReadingScreen.jsx`, which can copy the text. There is no address field, no stored subscriber, and no outbound mail.

The site is static GitHub Pages (`https://data-science-link.github.io/perspectiverse/`). `.github/workflows/pages.yml` builds the Vite app and overlays `public/data.json` from the `data-snapshot` branch. Pages cannot keep a secret, store a private list, or send mail.

The retained corpus already lives in private Cloudflare R2 (`pipeline/r2.py`, object `live_corpus.db`). `data.json` is not in that bucket.

## Recommendation

One Cloudflare Worker, **`perspectiverse-edge`**, on the Workers Paid plan. It stores subscribers in a private D1 database, sends the weekly digest with Cloudflare Email Sending, and is the same Worker that serves visitor chat in [240-visitor-chat.md](240-visitor-chat.md). The static site moves from GitHub Pages to Cloudflare Pages on that account. The daily pipeline stays on GitHub Actions.

Why this shape: the list and the chat both need a secret and a private read of R2, and Pages can provide neither. One Worker is one place for keys, rate limits, and the kill switches. Email Sending is on that same account, so a second mail vendor is not required at 100, 1,000, or 10,000 weekly subscribers.

## Subscriber storage

**Recommended:** a D1 database named `perspectiverse-subscribers`, bound only to `perspectiverse-edge`. It is not the corpus database, not an R2 object, and not a file in git.

Each row holds:

| Column | What it is |
| --- | --- |
| `email_hmac` | HMAC-SHA256 of the trimmed, lowercased address, keyed with Worker secret `EMAIL_LOOKUP_PEPPER`. Unique. Used for lookup. |
| `ciphertext`, `nonce`, `key_version` | The address encrypted with AES-256-GCM and Worker secret `EMAIL_ENCRYPTION_KEY`. |
| `status` | `pending`, `confirmed`, or `unsubscribed`. |
| `requested_at`, `confirmed_at`, `unsubscribed_at` | UTC timestamps. |
| `consent_text_version` | The exact sentence they agreed to, by version id. |
| `confirm_token_hash` | Hash of the double-opt-in token. The raw token is only in the confirmation email. |
| `suppressed` | Stays true after unsubscribe so a later signup must confirm again and a send job will not mail them while they are unsubscribed. |

The Worker decrypts an address only while sending that one message. Logs, traces, and error reports record the row id, never the address, the token, or the ciphertext.

**Who can read plaintext.** The Worker, at send time. Michael, because he holds the Cloudflare account and the Worker secrets. GitHub Actions, the public site, and anyone who can read `data.json` or `live_corpus.db` cannot. A copy of the D1 file without `EMAIL_ENCRYPTION_KEY` is ciphertext plus a lookup hash, not a mailing list. A person who has both the database and the Worker secret can read every address. That is the same trust as the Cloudflare login. Turn on account 2FA before the first address is stored.

**Alternatives.**

- **A dedicated private R2 bucket of encrypted rows.** Same encryption, and R2 is already how the corpus is stored. Worse for "find this address" and "list everyone confirmed," which are the two operations the sender does. Use D1.
- **Workers KV.** Included on the same plan, and a bad fit for a consistent unique list. KV is eventually consistent and awkward to scan.
- **Columns in `live_corpus.db`.** Mixes a mailing list into the post corpus. One leaked snapshot or one pipeline log would expose it. Do not.
- **Resend or Buttondown as the system of record.** Their databases hold the plaintext. Reasonable if Michael would rather not operate the list. Compared under Sending service options. The recommendation keeps the list in D1 so the chat Worker and the sender share one backend and one access story.
- **Anything in `public/`, `data.json`, or `data-snapshot`.** Those are published. Out.

Do not strip Gmail dots or plus-tags. People use plus-tags to filter mail. Aliases are an abuse problem the rate limit covers, not a reason to rewrite the address.

## Signup flow

The form is a second action on the existing email sheet and the menu entry, next to the copy button. Copying the digest stays. The form is hidden until Worker config `EMAIL_SIGNUP_ENABLED` is on. If that config request fails, the form stays hidden.

Fields: email address, a consent checkbox with a versioned sentence ("Send me the weekly Perspectiverse digest. Unsubscribe any time."), a honeypot input named `website` positioned off screen (not `type=hidden`), and a Cloudflare Turnstile widget. The Turnstile site key is public. The Turnstile secret stays on the Worker. Re-check that the widget is still on Turnstile's free tier when the form is built.

`POST /v1/subscribe`:

1. Reject a missing or malformed address with `400` and the text "Enter an email address." That check does not reveal whether anyone has subscribed.
2. If the honeypot is filled, return the success body and write nothing.
3. Check the Turnstile token. On failure, return the success body and write nothing.
4. Rate limit: 5 subscribe attempts per IP per hour, and 20 per IP per day. Over the limit, return `429` with "Try again later." The body does not mention the address. Count the attempt before the database lookup.
5. Look up `email_hmac`.
   - Unknown address: insert `pending`, store a hashed single-use token that expires in 48 hours, send one confirmation email.
   - `pending`: replace the token and send one new confirmation. The old link dies.
   - `confirmed`: send nothing.
   - `unsubscribed`: treat as unknown. They must confirm again. The suppression flag flips back only after that confirmation.
6. Always return the same `200` body for steps 5's cases: "If this address can take mail, we sent a confirmation link. It expires in 48 hours."

The confirmation message is only the link. It is not the digest. Sending the digest before the click would deliver the list content before consent.

The link is `https://<domain>/v1/confirm?token=<random>`. The address is not in the query string. The confirm page says they are on the list, or that the link is expired, and never echoes the address into HTML that a referrer could leak. Unconfirmed rows are deleted after 48 hours by the same Worker cron that sends.

**No membership oracle.** Unknown, pending, and confirmed all return the same success body. An attacker who does not control the inbox cannot tell those apart. The person who owns the inbox can, because only a new or pending address gets a message. That is the point of double opt-in.

**Alternatives.**

- **Single opt-in.** Faster, and it puts every typo and every forged address straight onto a live send. Rejected for a first list.
- **A paid CAPTCHA.** Turnstile is the same vendor as the Worker. A second captcha vendor is an extra script on the page, which the project has avoided (no third-party scripts on the sponsor banner, #231).
- **Honeypot only.** Keeps the page script-free. Too weak once the form is linked from a public site. Honeypot plus Turnstile plus the rate limit is the set.
- **Magic-link login / accounts.** The digest does not need an account. An account would store more personal data than the list requires.

## Unsubscribe

Every digest and the confirmation email carry:

- A visible "Unsubscribe" link in the footer.
- `List-Unsubscribe: <https://<domain>/v1/unsubscribe?token=…>`
- `List-Unsubscribe-Post: List-Unsubscribe=One-Click`

The one-click POST body is `List-Unsubscribe=One-Click` (RFC 8058). GET on the same link also unsubscribes, for the human clicking in a browser, and shows a plain "You're unsubscribed" page.

The token is an HMAC over the row id and a key version, signed with `UNSUBSCRIBE_SIGNING_KEY`. It does not contain the address. It does not expire, so a footer link from an old edition still works. Rotating the signing key bumps the version; the sender puts the current token in the next edition. During rotation the Worker accepts the previous version for 60 days.

**Honored immediately.** The handler sets `status=unsubscribed`, deletes `ciphertext`, `nonce`, and `confirm_token_hash`, and commits that write before it returns `200`. The send loop reads status in the same database immediately before each recipient. A person who unsubscribes while a batch is running is skipped if their turn has not been handed to the mail API. A message already accepted by the mail API can still arrive. That one race is the limit of "immediate." The next edition will not include them.

The `email_hmac` and the timestamps stay, as a suppression record, so the address is not mailed again without a new confirmation. A separate "Delete my record" link on the unsubscribe page also removes the hmac. After that, the address can sign up as if it were new. Michael picks which of those two is the default footer action in the open questions. The recommendation is: the footer unsubscribes and keeps the suppression hash; deletion is the second link.

**Alternatives.**

- **Reply-to-unsubscribe by hand.** Meets the spirit of a small list and fails the moment Michael misses a day. Keep a `mailto:` in `List-Unsubscribe` as a second channel, and make the link the one the software honors.
- **Unsubscribe links that expire in 30 days.** Breaks old editions sitting in an inbox. The token stays valid.
- **A logged-in preference center.** Needs accounts. The link is enough.

## Sending service options

Steady-state volume assumes **one edition per week**, 52 weeks / 12 months = 4⅓ editions per month:

| Subscribers | Digest emails per month |
| ---: | ---: |
| 100 | 433⅓ |
| 1,000 | 4,333⅓ |
| 10,000 | 43,333⅓ |

Confirmations are extra and small next to those numbers once the list exists. A nightly send would be about 3,000 / 30,000 / 300,000 emails a month at the same list sizes. That cadence is priced under Cadence.

Dollar figures are the provider's published per-email or per-plan price. They ignore tax. They assume a text digest with no attachment and no open-tracking pixel.

### Recommended: Cloudflare Email Sending

Pages read on 2026-10-18:

- [Cloudflare Email Service pricing](https://developers.cloudflare.com/email-service/platform/pricing/) (page last updated 2026-06-09). Workers Paid: **3,000 outbound emails included per month, then $0.35 per 1,000**. Workers Free cannot send to arbitrary recipients. Sends to verified destination addresses are free and do not count toward the 3,000.
- [Cloudflare Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/) (page last updated 2026-10-02). Workers Paid is **$5 per month** minimum for the account, with 10 million requests and 30 million CPU-milliseconds included, then $0.30 per extra million requests and $0.02 per extra million CPU-milliseconds. Static asset requests are free and unlimited. No egress fee.

Email marginal cost on top of that $5, weekly cadence:

| Subscribers | Emails | Overage past 3,000 | Email overage | With the $5 plan |
| ---: | ---: | ---: | ---: | ---: |
| 100 | 433⅓ | none | $0 | **$5** |
| 1,000 | 4,333⅓ | 1,333⅓ | $0.47 | **$5.47** |
| 10,000 | 43,333⅓ | 40,333⅓ | $14.12 | **$19.12** |

The $5 is the shared host for chat as well. It is not charged twice. It is not part of the chat's $50 model cap.

Why this sender: the Worker, the R2 corpus, and the domain DNS are already the Cloudflare account the pipeline uses for R2. SPF, DKIM, and DMARC are then records on that zone. There is no second bill until the list passes 3,000 sends in a month. Deliverability work is still real (a new domain has no reputation) but it is one dashboard.

**Deliverability (every sender, including this one).** GitHub Pages hostnames cannot be the From domain. The build does not send until a domain Michael controls has:

- SPF authorizing the sender Cloudflare names when the domain is added.
- DKIM with the selector Cloudflare issues.
- DMARC, starting at `p=none` with an aggregate report mailbox, moved to `p=quarantine` only after Michael has looked at a week of reports.

From address: `Perspectiverse <digest@that-domain>`. The visible From, the envelope, and the DKIM domain match. No remote images, no open tracking, no click tracking. The digest is already public on the site; a tracking pixel would add a surveillance side channel the observatory does not otherwise have.

### Alternative: Amazon SES

[Amazon SES pricing](https://aws.amazon.com/ses/pricing/), read 2026-10-18.

New accounts, and account/region pairs with no metered SES use since 2025-06-01, start on the **Essentials** plan as of 2026-07-21: **$0.16 per 1,000** emails up to 10 million a month. **À la carte** outbound is **$0.10 per 1,000**, and the page says a new account can switch to it. The page's footnote describes an extra **$0.12 per GB of attachments**. Pricing Example 1 also applies $0.12/GB to the whole message body (a 32 KB message). A 40 KB digest at 10,000 weekly subscribers is about $0.21 a month if the body is billed that way. Ignored in the table below.

| Subscribers | Weekly emails | À la carte at $0.10 / 1,000 | Essentials at $0.16 / 1,000 |
| ---: | ---: | ---: | ---: |
| 100 | 433⅓ | $0.04 | $0.07 |
| 1,000 | 4,333⅓ | $0.43 | $0.69 |
| 10,000 | 43,333⅓ | $4.33 | $6.93 |

Why not the default: it is the cheapest unit price, and it is a second account, a sandbox approval, IAM keys, and a region, beside the Cloudflare account that already holds R2. Worth switching to if the list holds past a few tens of thousands of weekly sends and Cloudflare's $0.35 per 1,000 starts to matter. Pro ($0.22 / 1,000 plus $105 per account per region) and Enterprise are for dedicated IPs and features this list does not need.

### Alternative: Resend

[Resend pricing](https://resend.com/pricing), read 2026-10-18.

Transactional email (`/emails`):

| Plan | Price | Included | Notes |
| --- | ---: | ---: | --- |
| Free | $0 | 3,000 / month | **100 / day** cap |
| Pro | $20 / month | 50,000 | $0.90 per extra 1,000. Also a $35 tier at 100,000 |
| Scale | from $90 / month | 100,000 | Not needed at these sizes |

Marketing email (`/broadcasts`) is priced by contacts, with unlimited sends to those contacts: Free **1,000 contacts**, Pro marketing **$40 / month for 5,000** and **$80 / month for 10,000**.

Weekly list on the transactional API:

| Subscribers | Fits |
| ---: | --- |
| 100 | The free monthly quota, and exactly the 100/day cap if the digest is the only mail that UTC day. One confirmation the same day puts the day over 100. The free plan does not actually fit a send day. |
| 1,000 | Pro, $20. 4,333 is inside 50,000. |
| 10,000 | Pro, $20. 43,333 is inside 50,000. |

Weekly list on marketing broadcasts: $0 up to 1,000 contacts, **$80 / month at 10,000 contacts**.

Why not the default: the API and the dashboard are the nicest of the set, and at 10,000 subscribers the honest newsletter product (broadcasts) costs $80 against about $14 of Cloudflare overage. Using `/emails` at $20 keeps our own list, which Resend's own pricing page says is allowed if we add the unsubscribe link and the List-Unsubscribe headers ourselves. That is a good backup if Cloudflare Email Sending lands in spam during the test week. It is a second vendor and a second place addresses can show up in a 30-day log (their Free and Pro retention).

### Alternative: Buttondown

[Buttondown pricing](https://buttondown.com/pricing), read 2026-10-18. The visible page says the first 100 subscribers are free. The plan offers in that page's JSON-LD are:

| Plan | Price | Subscribers |
| --- | ---: | --- |
| Free | $0 | up to 100 |
| Basic | $9 / month | up to 1,000 |
| Standard | $29 / month | up to 5,000 |
| Professional | $79 / month | up to 10,000 |
| Advanced | $139 / month | up to 20,000 |

Their FAQ says those prices assume at most one email a day to the whole list. A weekly digest fits. Add-ons (analytics, surveys, and others at $9 to $79 a month) are not required to send.

| Subscribers | Plan |
| ---: | --- |
| 100 | Free, $0 |
| 1,000 | Basic, $9 |
| 10,000 | Professional, $79 |

Why not the default: Buttondown would host the list, run double opt-in, and send. That is less software for us to get wrong, and it is $79 at 10,000 subscribers against about $19 all-in on Cloudflare. The formatted digest would be pushed to their API, the addresses would live in their database rather than our encrypted D1, and the chat backend would still have to exist separately. Choose this if Michael wants a hosted newsletter more than a list we control.

### Alternative: MailChannels

Not the default.

- [MailChannels' 2024-06-30 notice](https://blog.mailchannels.com/important-update-mailchannels-email-sending-api-for-cloudflare-workers-to-be-terminated/): the free email API that used to ride inside Cloudflare Workers stopped accepting requests on **30 June 2024**.
- [MailChannels pricing](https://www.mailchannels.com/pricing/), read 2026-10-18. The Email API free plan is **$0, up to 3,000 emails a month, 100 a day, no overage**. The FAQ says paid Email API pricing is volume-based **from $10 a month**, and there is no tier between that free plan and a **10,000 emails/month** paid plan. The static page does not publish the dollar price of the 10,000 tier (it is a calculator), so this spec does not invent one.

A weekly list of 100 can sit on their free plan only if the send day stays at or under 100 messages. 1,000 and 10,000 weekly subscribers need the paid plan. It is a separate account from the Worker, which is the thing their old free path used to avoid. Cloudflare Email Sending replaced that role.

## Cadence and trigger

**Recommended cadence: weekly.** The menu already says "Weekly email digest," and the subject line is "This week." The pipeline keeps writing a fresh `digest` every successful night. The sender does not fire on that night.

**Recommended clock:** Monday 15:17 UTC, with guarded retries at 17:17 and 19:17 UTC. The daily pipeline's slots are 06:17, 07:47, 09:17, 10:47, and 12:17 UTC. 15:17 is after those, on an odd minute, in the same style as the pipeline crons. Each slot exits immediately if that edition id was already handed to the mail API. All three share one lock.

**What "send" means.**

1. Read `editions/latest/data.json` from R2 (the public snapshot the pipeline upload in the hosting section writes). Read `digest` and `last_updated`.
2. If `last_updated` is older than 36 hours, send nobody, and record the skip. A stale solar system should not go out as this week's letter.
3. If `EMAIL_SEND_ENABLED` is `off`, stop.
4. If it is `test`, render the message and send it only to Worker secret `TEST_RECIPIENT`. Do not read the subscriber table for recipients.
5. If it is `on`, select `confirmed` rows and, for each row, in order: re-read status, skip anything not `confirmed`, decrypt, call Email Sending with that single recipient, write a `sends(edition_date, row_id)` row. One recipient per API call so a Cc header can never leak the list. A retry of the same edition skips rows that already have a `sends` record.

The body is the same text `emailPlain` already builds from `digest` (subject, planet, percent, arguments, disagreement), plus a link to the site, the postal address, and the unsubscribe link. HTML is that letter with headings, no remote assets. The build adds the planet `id` onto each digest planet so the letter can link to the planet. Today `assemble_email` stores the name and not the id.

**Human approval before the first real send.** The Worker ships with `EMAIL_SEND_ENABLED=off`. Michael sets `test` and receives one edition at `TEST_RECIPIENT`. He says, in the factory room, that the test is the letter he wants to send. Only then does the flag become `on`. An agent does not flip it. A later edition does not wait for a fresh approval unless Michael asks for that (open question). The first-send gate is once, not every Monday.

**Alternatives.**

- **After every nightly edition.** Matches "when the pipeline finishes" and fights the UI copy. At 10,000 subscribers it is about 300,000 emails a month: Cloudflare overage about (300,000 − 3,000) / 1,000 × $0.35 = **$103.95**, plus the $5 plan. SES à la carte would be about $30. It also trains readers to ignore it. Rejected unless Michael explicitly wants a daily letter.
- **Michael clicks send each week.** Safest inbox, and it makes the list depend on him being at a keyboard. The test gate covers the dangerous first time. The cron covers Monday.
- **GitHub Actions sends the mail.** Actions would need the subscriber key and the mail key. Those secrets then sit next to the pipeline token. Keep them on the Worker.

## Compliance

This is the product bar, not a legal opinion and not a claim that Perspectiverse is certified for anything.

**CAN-SPAM (United States).** Treat the digest as commercial mail even though it is free.

- Honest From name and an honest subject. The subject stays `digest.subject`. Do not prefix it with "Re:" or anything that pretends to be a personal reply.
- A physical postal address in the footer. `src/lib/pages.js` only knows "Austin, Texas." A city is not the footer. The build reads Worker secret `POSTAL_ADDRESS`. If that secret is empty, the Worker refuses to leave `off`, including for the test send.
- An unsubscribe that works. The one-click path above is immediate, which is inside the statute's window.
- No harvested list. The only addresses are people who typed theirs into the form and clicked the confirmation.

**GDPR (and UK GDPR), if any subscriber is in the EEA or the UK.** The basis is consent, recorded by the double opt-in: when they asked, when they confirmed, which sentence they agreed to, and the version of that sentence. The form links to a short privacy note: what is stored (the address, those timestamps), why (to send the digest), and how to leave.

- Data minimization is the column list above. No name, no Bluesky handle, no raw IP. The rate limiter stores HMAC(IP) in Workers KV with a 36-hour TTL.
- Unsubscribe deletes the ciphertext in the same request. The suppression hash is the part Michael still has to choose (open questions).
- A copy of the row, decrypted, is available to the address owner via a "what do you store" link in the same footer, using the same signed token. It shows the address and the timestamps, nothing else.
- The note does not say "we are GDPR compliant." It says what the software does.

**CASL (Canada)** is the other reason the confirmation click exists. A pre-checked box does not count. The checkbox starts unchecked.

**Alternatives.** A US-only form (block other countries at the edge) shrinks the GDPR surface and also turns away readers the observatory otherwise serves. Not the recommendation. A lawyer reading the privacy note before launch is a decision for Michael, not a paragraph this spec can replace.

## Hosting

**Recommended shared backend:** the Cloudflare Worker `perspectiverse-edge`.

It serves both this list and the visitor chat:

| Route | Job |
| --- | --- |
| `POST /v1/subscribe`, `GET /v1/confirm`, `POST /v1/unsubscribe`, `GET /v1/unsubscribe` | The list |
| Cron, Monday 15:17 / 17:17 / 19:17 UTC | The weekly send |
| `POST /v1/chat`, `GET /v1/features` | Chat and the on/off flags, specified in [240-visitor-chat.md](240-visitor-chat.md) |
| `GET /v1/admin/spend` | Bearer token `ADMIN_TOKEN`. Returns the chat month total and the email send counts. No addresses. |

Bindings: D1 `perspectiverse-subscribers`, the existing R2 bucket (read `editions/` and `dossiers/`, never list subscribers into that bucket), Workers KV for rate limits.

**Recommended site host:** Cloudflare Pages for the Vite build, on the same account, with a route so the site and `/v1/*` are one origin. Custom domain on that zone. Email DNS lives on the same zone.

### What moving off GitHub Pages changes

Today `.github/workflows/pages.yml` checks out `main`, overlays `public/data.json` from `data-snapshot`, runs `npm run build` with `GITHUB_PAGES=true`, and deploys `dist`. Vite's base path is `/perspectiverse/` only when that env var is set (`vite.config.js`). The live URL is `https://data-science-link.github.io/perspectiverse/`. A push to `data-snapshot` is made with the Actions token, which does not start other workflows, so Pages redeploys via `workflow_run` after **Daily Discourse Pipeline** succeeds.

Moving the site to Cloudflare Pages changes the following. It does not change clustering, the $1 a day pipeline cap, the R2 corpus, or the React solar system.

1. **The URL.** The public site leaves `data-science-link.github.io/perspectiverse/`. `base` stays `/`, which is already what local dev uses. Old bookmarks break unless Pages is left up as a one-page pointer. That pointer is the recommended overlap, and it is reversible.
2. **How an edition goes live.** The Pages overlay step goes away. The pipeline, after the same publish guard that protects `data.json` today, uploads the public snapshot to R2 at `editions/<date>/data.json` and copies it to `editions/latest/data.json`. The Worker serves `/data.json` from that object. A new edition no longer waits for a Pages rebuild. `workflow_run` in `pages.yml` can be removed once the R2 copy is what the site fetches. The corpus object `live_corpus.db` stays private and is not that file.
3. **What still deploys from GitHub.** Pushes to `main` still run Tests, Frontend, and Security Audit. Pages-the-product stops being the host. Cloudflare Pages builds `main` for HTML, CSS, and JS. Secrets for mail and chat are Worker secrets, not `VITE_` variables. The pipeline's GitHub Actions secrets (`OPENAI_API_KEY`, `R2_*`, and the rest listed in `.factory/DOCS.md`) stay where they are.
4. **The domain.** A custom domain is required for SPF, DKIM, and DMARC anyway. Putting the site on it means the digest links and the From domain match.
5. **Cost.** The $5 Workers Paid plan covers the Worker, Pages Functions, and the 3,000 included emails. Static assets are not billed as requests. R2 storage of the public JSON is cents inside the existing R2 free tier (10 GB-month, already recorded in `pipeline/costs.py`). D1 on Workers Paid includes 5 GB and the row quotas on the [D1 pricing page](https://developers.cloudflare.com/d1/platform/pricing/) (read 2026-10-18). A subscriber list at 10,000 rows is inside that.

**Alternative: stay on GitHub Pages and call the Worker on a subdomain.** The solar system URL does not change. `pages.yml` stays. The form and the chat panel call `https://edge.<domain>` with CORS limited to the github.io origin. This still needs the Worker, the domain, and the DNS records, because Pages itself still cannot send mail or hold the key. It keeps two origins, a CORS allowlist, and the `workflow_run` deploy dance. It is the smaller first step if Michael wants mail and chat before he is willing to move the site. The recommendation is still to move, because the From domain and the site domain should be the same, and the edition should publish by an R2 upload the pipeline already knows how to do.

**Alternative: Vercel Functions.** [Vercel fluid compute pricing](https://vercel.com/docs/functions/usage-and-pricing), read 2026-10-18. Hobby includes 1 million invocations a month. The docs' Pro example bills invocations at $0.60 per million, plus Active CPU and provisioned memory (Washington, D.C. region: $0.128 per CPU-hour and $0.0106 per GB-hour). The corpus is in R2, not in Vercel storage. A function there would be a second platform next to Cloudflare, with its own secret store, still needing a mail vendor. Rejected.

**Alternative: a small VPS.** A $5 box can run both APIs. It also means we patch the OS, terminate TLS, and keep a long-lived copy of the R2 keys. The Worker bills CPU only while the request runs and is the platform the R2 bucket already sits on.

## Secrets, test plan, and cost

### Secrets

Worker secrets, set in the Cloudflare account, never in git, never in a `VITE_` variable, never printed in a Worker log:

| Secret | Role |
| --- | --- |
| `EMAIL_ENCRYPTION_KEY` | AES-256-GCM key for addresses |
| `EMAIL_LOOKUP_PEPPER` | HMAC pepper for lookup |
| `UNSUBSCRIBE_SIGNING_KEY` | Footer and one-click tokens |
| `TURNSTILE_SECRET` | Signup bot check |
| `POSTAL_ADDRESS` | Footer. Empty means the sender stays `off` |
| `TEST_RECIPIENT` | The only inbox `test` mode may mail |
| `ADMIN_TOKEN` | Spend and send-count route |
| `EMAIL_SIGNUP_ENABLED` | `0` or `1`. Ships `0` |
| `EMAIL_SEND_ENABLED` | `off`, `test`, or `on`. Ships `off` |

Chat secrets are listed in the chat spec. They live on this same Worker. The pipeline's DeepInfra key is not one of them.

Rotation: a new `EMAIL_ENCRYPTION_KEY` gets a new `key_version`. The sender re-encrypts a row lazily when it decrypts with the old version. Pepper rotation is a one-time rewrite of `email_hmac` and is a deliberate maintenance job, not a cron.

The pipeline's GitHub Actions logs must never receive these values. The daily job does not get a binding to the subscriber database.

### Test plan

CI uses a local fake of the mail API and a local D1 (or a SQLite stand-in). No test sends mail to a real domain. No test uses a live address list.

- Pending → confirmed → unsubscribed, including a second confirm link killing the first.
- Pending rows older than 48 hours are deleted and the link then fails.
- The success body is byte-identical for an unknown address, a confirmed address, and a pending address.
- A filled honeypot and a failed Turnstile write zero rows and return that same body.
- The sixth subscribe from one IP in an hour returns 429.
- An unsubscribe token for row A does not change row B.
- RFC 8058 POST and the human GET both clear a confirmed row before the response, and the ciphertext is gone.
- A send batch that races an unsubscribe does not call the mail API for that row.
- A second cron slot on the same edition sends zero new messages.
- `test` mode sends one message to `TEST_RECIPIENT` and none to the table.
- `off` sends nothing. An empty `POSTAL_ADDRESS` cannot be set to `test` or `on`.
- Render a fixture `digest` and compare the text to the fields `assemble_email` actually writes (subject, name, percent, arguments, disagreement).
- A log assertion: the address, the token, and the ciphertext do not appear in the captured logs.

Before `on`: Michael receives the test edition, checks the footer address, the unsubscribe link, and that SPF, DKIM, and DMARC pass on that received message. That check is a human step, recorded on the build PR. It is not a unit test.

### Cost

At the recommended weekly cadence, Cloudflare Email Sending on the Workers Paid plan:

| Subscribers | Monthly bill for host + mail |
| ---: | ---: |
| 100 | $5 |
| 1,000 | $5.47 |
| 10,000 | $19.12 |

Chat model spend is a separate $50 cap and is not in this table. The pipeline's $1 a day is also separate. D1 and KV at this size stay inside the included Workers Paid quotas. R2 writes for the public edition object are Class A operations at $4.50 per million ([R2 pricing](https://developers.cloudflare.com/r2/pricing/), the same page `pipeline/costs.py` already cites), one write per successful night, well inside the 1 million Class A free tier.

There is no paid call in building this spec, and the build that follows this spec does not send to the list inside CI.

## Open questions for Michael

1. **Cadence.** Weekly on Monday after the pipeline (recommended). After every nightly edition. Or he clicks send each week.
2. **Where the site lives.** Move to Cloudflare Pages with this Worker (recommended). Or keep GitHub Pages and put only the API on the Worker.
3. **The domain.** Which domain, and does its DNS move to the Cloudflare zone? Mail cannot go out as `github.io`.
4. **Postal address.** He supplies a street address stored as a secret. Or he uses a mail-receiving service's street address. The footer cannot ship with only "Austin, Texas."
5. **After unsubscribe.** Footer keeps a suppression hash and offers a second "delete my record" link (recommended). Or the footer deletes the hash too.
6. **Who else may read addresses.** Only the Worker and Michael (recommended). Or a second person is added to the Cloudflare account on purpose.
7. **Approval after the first test.** One yes in the factory room turns weekly sending on (recommended). Or he approves every edition.
8. **What the letter contains.** The main ten planets, which is all `assemble_email` writes today (recommended). Or the newspaper-section planets too.
