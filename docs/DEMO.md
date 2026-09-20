# Demo script — Ad Spend Optimization

A 6–8 minute walkthrough. The story: **we find the money leaking out of a client's ad
account, prove it, and bill a share of what we recover.**

---

## Before they walk in (5 minutes)

```bash
# 1. Start the backend
cd backend
DATABASE_URL="sqlite:///./dev.db" SECRET_KEY="local-dev-secret-key-at-least-32-chars" ENV=dev \
  .venv/Scripts/uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2. Start the frontend (second terminal)
cd frontend && npm run dev
```

Then:

- Open **http://localhost:3000** and check it loads.
- **Two browser windows, not tabs** — one logged in as the client, one as the admin. Switching
  tabs mid-sentence is what makes demos feel clumsy; switching windows with Alt-Tab looks
  deliberate.
- Zoom the browser to ~110% so numbers are readable on a projector.
- Close DevTools. If you ever enabled "Emulate prefers-reduced-motion", turn it **off** — the
  hero animation is the opening image.
- Have `backend/tests/fixtures/sample_30d.csv` somewhere easy to drag from.

**Logins**

| Role | Email | Password |
|---|---|---|
| Client | `demo@example.com` | `demo-password-123` |
| Admin | `admin@example.com` | `demo-password-123` |

---

## The script

### 1. Open on the problem (30 seconds) — client window, `/dashboard`

Let the hero animation play before you say anything. Then:

> "This is a real month of ad data — 7,200 rows. Rs. 1,300,829 spent. The teal is money that
> produced conversions. The coral is waste, and it's **Rs. 188,093** — about 14% of the budget."

**The point:** the picture *is* the product. Most tools hand you a spreadsheet.

### 2. Show that it's not a black box (90 seconds) — scroll down

> "Here's where it went. Every segment, with its cost per conversion. This one — Audience
> Network — is flagged because its cost per conversion is far above the account average."

Click a recommendation to expand it.

> "And here's the reasoning in plain language, with the arithmetic: what it spent, what it cost
> per conversion, how that compares, and exactly how much to cut."

Click the dimension tabs (Placement / Age group / Time slot).

> "Same money, three ways of cutting it. Worth saying: we never add these up. The same wasted
> rupee shows up in all three views, so summing them would overstate waste three times over —
> we always report the largest single view."

**The point:** transparency and honesty are the differentiators. Say the last line out loud —
it is exactly the kind of detail a boss tests you on.

### 3. Download the PDF (20 seconds)

> "The client can hand this to their team or their agency."

Open it. Same numbers, plus a page explaining the method.

### 4. Switch to the admin window (2 minutes) — `/admin/runs`

> "Nothing reaches a client until I've checked it. This is the approval queue — I see the
> numbers before they do, so we never argue about a figure after the fact."

Then `/admin/invoices`:

> "Pricing is a small base fee plus a share of what we actually recovered — not a flat retainer."

Draft an invoice for Demo Retail Co (period: last month). Walk through the row:

> "Base fee, the recovered-waste figure I confirm myself, the performance fee, the total.
> Every one of these is logged" — open `/admin/audit` — "so if a client ever questions an
> invoice, I can show exactly who changed what and when."

**The point:** this is the part that makes the pricing model credible rather than a slogan.

### 5. The payment flow (90 seconds)

Issue the invoice. Switch to the client window → `/dashboard/billing`:

> "The client sees the invoice and exactly which account to pay into — JazzCash, Easypaisa or
> a bank transfer over Raast. No card gateway; this is how small businesses here actually pay."

Submit a payment with a made-up transaction ID.

> "Note what it says: *awaiting our check, not yet applied*. Submitting an ID is a claim, not a
> payment."

Back to the admin window → `/admin/payments` → Confirm.

> "Only I can mark money as received. Now it's paid."

**The point:** it's built for how Pakistani SMEs really pay, and it can't be gamed.

### 6. Close (30 seconds)

> "That's the full loop: upload, detect, approve, report, invoice, get paid. It runs on a
> stack that costs about $25 a month to host. What's left before a first paying client is the
> legal copy, our actual pricing numbers, and pointing it at the production database."

---

## Questions you'll probably get

**"How do we know the numbers are right?"**
Every figure is computed by one tested engine and re-checked by hand against the source data.
Each analysis stores a snapshot of the exact settings used, so any report can be reproduced
months later. And nothing reaches a client without my approval.

**"What if a client disputes an invoice?"**
The audit log records every approval and every fee confirmation with who did it and when.
The invoice's base fee is frozen when it's drafted, so it can't drift afterwards.

**"Can a client see another client's data?"**
No. It's enforced in the database query itself, not hidden in the interface, and it's tested
on every endpoint — another client's record returns "not found", so you can't even probe for it.

**"Why not just use Madgicx / Smartly?"**
They're priced and built for enterprise marketing teams. This is for a business spending
Rs. 100k–500k a month who currently guesses, or pays a freelancer a flat fee regardless of
results.

**"Is it live?"**
Not yet — it runs locally today. Going live is a deployment step, not more building: Supabase
for the database, Railway for the API, Vercel for the site. The runbook is written.

**"How long until we can sell it?"**
The software is done. What's outstanding is commercial, not technical: our pricing numbers,
the terms and privacy wording, and a first client's real export to test against.

---

## If the demo has to be over a video call

Same script — just share the browser window, not the whole screen (keeps your terminal and
notes private). Run both servers beforehand and do one dry run: the analysis takes a few
seconds and you want to know exactly how long the pause is before you're live.

## If your boss wants a link to click themselves

That needs a real deployment (Supabase + Railway + Vercel — the runbook in `README.md`
covers it, roughly an hour, about $25/month). Don't do this the night before. A laptop demo
is more reliable and you control the pace.

---

## If something breaks mid-demo

- **Page won't load** → check both terminals are still running; restart the frontend first.
- **Login fails** → the database may have been rebuilt; the passwords above are the current ones.
- **Analysis seems stuck** → it runs in the background and takes a few seconds; the run page
  polls automatically. Refresh once.
- **Worst case** → the client dashboard already has an approved report, so you can skip
  straight to step 1 and talk through it without uploading anything live.
