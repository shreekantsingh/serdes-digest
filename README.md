# 📡 SerDes Daily Paper Digest

Sends a rich HTML email every morning with the latest **SerDes / high-speed
transceiver** papers from **arXiv** and **IEEE Xplore**.

**Runs on GitHub Actions. Delivers to your inbox. No SMTP. No passwords.**
You only need: your email address + one free API key from Resend.

---

## What the email looks like

```
┌─────────────────────────────────────────────────────────────┐
│  📡 SerDes Daily Digest          Wednesday, 28 May 2025     │
│  🔍 SerDes high speed PAM4              📄 18 papers        │
├─────────────────────────────────────────────────────────────┤
│  📚 arXiv Papers                               [12 found]   │
├─────────────────────────────────────────────────────────────┤
│  A 112-Gb/s PAM-4 SerDes in 5nm CMOS                       │
│  👤 R.Kumar et al.  📅 2025-05-12  cs.AR   [arXiv]         │
│  We present a 112-Gb/s PAM-4 transceiver with 7-tap DFE... │
├─────────────────────────────────────────────────────────────┤
│  📡 IEEE Xplore Papers                         [6 found]    │
├─────────────────────────────────────────────────────────────┤
│  0.5-pJ/b 224-Gb/s Transmitter in 3nm CMOS                 │
│  👤 H.Park et al.   📅 2025  ISSCC 2025   [IEEE]           │
│  A 224 Gb/s PAM-4 transmitter with 6-tap FIR...            │
└─────────────────────────────────────────────────────────────┘
```

---

## One-time setup (~10 minutes)

### Step 1 — Get a free Resend API key

1. Go to **[resend.com](https://resend.com)** → Sign up (just your email, no credit card)
2. Dashboard → **API Keys** → **Create API Key**
3. Copy the key — looks like `re_xxxxxxxxxxxxxxxx`

> Free tier: **100 emails/day**, **3,000/month** — more than enough.

---

### Step 2 — Create the GitHub repo

1. Go to **[github.com/new](https://github.com/new)**
2. Name it `serdes-digest`
3. Visibility: **Public** or Private (both work — no GitHub Pages needed)
4. Click **Create repository**

---

### Step 3 — Push this code

```bash
git clone https://github.com/YOUR_USERNAME/serdes-digest.git
cd serdes-digest

# Copy these files into the folder:
#   generate_report.py
#   requirements.txt
#   README.md
#   .github/workflows/serdes.yml   ← keep the folder structure

git add .
git commit -m "initial commit"
git push origin main
```

---

### Step 4 — Add your email and API key to GitHub

Go to your repo → **Settings** tab

**Your email address** (not a secret — just a variable):
```
Settings → Secrets and variables → Actions → Variables tab → New repository variable
  Name:  DIGEST_EMAIL
  Value: your.email@gmail.com
```

**Resend API key** (this is a secret):
```
Settings → Secrets and variables → Actions → Secrets tab → New repository secret
  Name:  RESEND_API_KEY
  Value: re_xxxxxxxxxxxxxxxx
```

---

### Step 5 — (Optional) IEEE Xplore API key

Without this, only arXiv papers are included. To add IEEE papers:

1. Go to **[developer.ieee.org](https://developer.ieee.org/member/register)** → Register free
2. Create an app → copy the API key
3. Add as GitHub Secret:
   ```
   Name:  IEEE_API_KEY
   Value: your_ieee_key_here
   ```

---

### Step 6 — Test it right now

Go to your repo → **Actions** tab → **SerDes Daily Digest** → **Run workflow** → **Run workflow**

Check your inbox in ~30 seconds.

---

## Customisation

### Change the search query

```
Settings → Secrets and variables → Actions → Variables → New repository variable
  Name:  SEARCH_QUERY
  Value: 56G SerDes CDR equalization CMOS 5nm
```

**Useful queries:**
```
SerDes 112G PAM4 equalization
high speed CDR clock data recovery CMOS
coherent optical transceiver DSP ASIC
Ultra Ethernet RoCE RDMA AI training fabric
CMOS transmitter receiver 3nm 5nm FinFET
```

### Change delivery time

Edit `.github/workflows/serdes.yml` line 6 — cron is in UTC (IST = UTC + 5:30):

| Desired IST time | Cron value        |
|-----------------|-------------------|
| 7:00 AM IST     | `30 1 * * *`      |
| 8:00 AM IST     | `30 2 * * *`      |
| 9:00 AM IST     | `30 3 * * *`  ← default |
| 6:00 PM IST     | `30 12 * * *`     |

### Weekdays only (skip weekends)

```yaml
- cron: '30 3 * * 1-5'   # Mon–Fri only
```

### Change number of papers

Edit `MAX_RESULTS = 12` in `generate_report.py`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No email received | Check spam folder; verify DIGEST_EMAIL variable is set correctly |
| `401 Unauthorized` from Resend | RESEND_API_KEY secret is wrong or expired — regenerate at resend.com |
| IEEE section empty | Add `IEEE_API_KEY` secret |
| arXiv section empty | Temporary arXiv rate limit — will self-recover next run |
| Want to use your own domain as sender | Verify domain in Resend dashboard → change `FROM_EMAIL` in workflow |

---

## File structure

```
serdes-digest/
├── generate_report.py          # Fetches papers, builds HTML, sends email
├── requirements.txt            # Python deps: just requests
├── README.md
└── .github/
    └── workflows/
        └── serdes.yml          # GitHub Actions — daily cron + manual trigger
```

---

## How it works (no magic)

```
09:00 IST every day
      │
      ▼
GitHub Action spins up (free Ubuntu VM, ~30 seconds total)
      │
      ├── fetch_arxiv()  →  export.arxiv.org/api  (free, no key)
      ├── fetch_ieee()   →  ieeexploreapi.ieee.org (free key)
      │
      ▼
build_email_html()  →  rich HTML email body
      │
      ▼
POST https://api.resend.com/emails
      │
      ▼
📬 Arrives in your inbox
```

**Cost: $0. Credentials stored: 1 API key (Resend). Maintenance: none.**
