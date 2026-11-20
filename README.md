# Indian Stock Radar — Free Private Auto-Updating Website (GitHub + Cloudflare)

A 11-module Indian Stock Market (NSE) Daily Intraday & CNC Delivery dashboard that updates **twice every market day (08:45 AM IST & 03:45 PM IST)** using **GitHub Actions** and hosts **privately for free** on **Cloudflare Pages + Cloudflare Zero Trust Access**.

## Step-by-Step Setup (Free & Private)

### 1. Create a Private GitHub Repository
1. Go to [github.com/new](https://github.com/new).
2. Name the repository `indian-stock-radar` and select **Private**.
3. Upload all files from this folder (including `.github/workflows/daily-update.yml`, `scripts/update_market.py`, `watchlist.json`, `index.html`, `requirements.txt`).
4. Go to your repo **Settings → Actions → General → Workflow permissions**, select **Read and write permissions**, and click **Save**.
5. Go to **Actions → Update NSE Daily Trading & CNC Data → Run workflow** to test your first live NSE update immediately!

### 2. Deploy to Cloudflare Pages (Free for Private Repos)
1. Log in to [dash.cloudflare.com](https://dash.cloudflare.com).
2. Go to **Workers & Pages → Create → Pages → Connect to Git**.
3. Authorize GitHub and select your private `indian-stock-radar` repository.
4. Set **Framework preset** to `None` and **Build output directory** to `.` (or leave blank), then click **Save and Deploy**.
5. Every time GitHub Actions commits `data/daily_report.json` (at 08:45 AM & 03:45 PM IST), Cloudflare Pages automatically redeploys in ~15 seconds.

### 3. Make the Website 100% Private (Free Cloudflare Zero Trust Access)
1. In Cloudflare Dashboard, open **Zero Trust** (Free plan covers up to 50 users).
2. Go to **Access → Applications → Add an application → Self-hosted**.
3. Enter your `*.pages.dev` domain.
4. Add a Policy: **Allow → Emails → your-email@gmail.com** (using One-Time PIN login).
5. Now only you can open the site after entering the email OTP!
