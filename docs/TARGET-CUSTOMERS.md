# Target customers and first outreach test

Written 2026-11-12. Supersedes the personas in `MARKETING.md` §1, which predate the flat
$65/month price. The market figures below are rough estimates; check them in customer
conversations before relying on them.

---

## 1. Why the spend floor is Rs. 250,000

$65 ≈ Rs. 18,000 a month (at 276 PKR/USD). The report pays for itself only if it finds
more than that in waste.

| Monthly ad spend | Fee as % of spend |
|---|---|
| Rs. 100,000 | 18% |
| Rs. 250,000 | 7% |
| Rs. 500,000 | 3.6% |
| Rs. 1,500,000 | 1.2% |

The synthetic demo account shows ~14% waste, and published SMB estimates sit around 25%.
Below Rs. 250k the fee eats most of any likely saving, and segments rarely have enough
conversions to clear the significance thresholds. The site now says
"Rs. 250,000–1,500,000 a month".

---

## 2. Segments, ranked

### 1 — Primary: owner-run D2C e-commerce brands

- **Who:** clothing and lawn, skincare, fragrance, supplements, home goods. They have their own
  Shopify or WooCommerce store, and the founder or one in-house person runs the ads.
- **Spend:** Rs. 250k–1.5M a month, rising sharply before Eid, Ramzan, 11.11 and lawn launches.
- **Pain:** they know their overall cost per order, but not which placement, age group or
  hour is dragging it up.
- **Pool:** about 25,000 active Shopify stores are based in Pakistan, but ~98% make under
  $100 a month. The realistic pool is a few hundred to low thousands, so outreach should be
  targeted, not broadcast.
- **Hard qualifier:** the Meta pixel records purchases. Brands that sell through DMs with cash
  on delivery and no pixel are out.

### 2 — Channel: freelance media buyers and small agencies

- **Who:** freelancers and 2–10 person shops managing Meta and Google ads for 5–15 clients at
  Rs. 30–60k a month each.
- **Offer:** the Agency plan, $149/month for up to 10 advertisers' accounts. That's about $15
  per client and pays for itself with one retained client.
- **Value to them:** a rigorous PDF to bring to each client's monthly review. Present it as
  *their* finding.
- **Why it matters:** one relationship can bring several advertisers.

### 3 — Secondary: lead-gen service businesses

- **Who:** clinics (dental, skin, IVF), real estate, schools and academies, and
  study-abroad and immigration consultants. They spend Rs. 200k+ a month on Lead Ads.
- **Angle:** time-of-day waste ("you pay full price for your worst hours").
- **Caveat:** a freelancer usually runs their ads, so they are mostly reached through
  segment 2.

### Not now

- Advertisers under Rs. 150k/month
- Sellers who rely on DMs or WhatsApp with no conversion tracking
- Brands with in-house marketing teams
- International SMBs: Madgicx (~$45+) and Birch ($49–99) connect to the account and automate
  changes, which beats a $65 CSV audit for that market

---

## 3. The outreach test (D2C brands)

**Goal:** find out whether segment 1 will hand over an export and pay. Run it 4–6 weeks before a
sale season (Ramzan / Eid / 11.11), not during it.

### Build the list (1–2 hours)

1. Open the [Meta Ad Library](https://www.facebook.com/ads/library/). Set country to
   Pakistan and ad category to "All ads", then search category words (`lawn`, `skincare`,
   `perfume`, `unstitched`, `supplements`).
2. Keep advertisers with **15+ active ads**, a **website link** in the ads (a sign of a
   store and likely pixel), and **no big-brand name** (skip anyone with a known in-house
   team).
3. Record 40 candidates in the tracker (below). Note one specific ad per brand to mention in
   the DM.

### Message (20 a week, Instagram DM or the WhatsApp number on the page)

> Assalam-o-alaikum — I saw your [specific collection] ads running this week. I've built a
> tool that takes a Meta ads export and shows your cost per order by placement, age group
> and time of day, so you can see which slices are dragging the average up. No access to
> your ad account needed; it's one CSV. Would you like me to run it on last month's data
> for free? If it finds nothing, I'll tell you that too.

Rules: personalise the first line, never promise a saving percentage, and send the data
agreement (`DATA-AGREEMENT.md`) before they ask.

### Tracker columns

| Brand | Category | Active ads | Website | Ad referenced | Messaged | Replied | Export received | Report sent | Waste found (Rs.) | Paid? | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|

### What the result means

Target over 4 weeks: **40 messaged → 6+ replies → 3+ exports → 1+ paying**.

| Outcome | Reading |
|---|---|
| Few replies (under 3 of 40) | The opening message or the segment is wrong. Rewrite the first line before changing the segment |
| Replies, but no exports | Trust problem. Lead with the data agreement and offer to anonymise campaign names |
| Exports, but no conversions column | The pixel qualifier is too loose. Check the website for a pixel (e.g. Meta Pixel Helper) before messaging |
| Reports land, nobody pays | Price or value problem. Record the waste found against each brand's spend |
| 1+ paying | Repeat with the next category, and ask every brand for one introduction |

Freelancers (segment 2) run in parallel through university seniors. Pitch the Agency plan and
ask each one to run it on a single client account first.
