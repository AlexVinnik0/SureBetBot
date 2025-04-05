# SureBetBot

A fully automated arbitrage betting system that scrapes odds from Australian bookmakers to identify risk-free betting opportunities (aka "sure bets") and notifies a Discord channel in real-time.

---

## 📄 Project Description

**SureBetBot** is a local Python-based project designed to:

- Scrape odds from multiple Australian bookmakers (e.g. Sportsbet, Ladbrokes, TAB)
- Detect arbitrage opportunities using the classic formula:
  
  ```
  1/Odds_A + 1/Odds_B < 1
  ```

- Calculate the ideal stake split for guaranteed profit
- Notify a private **Discord channel** when a sure bet is detected

> This project is currently CLI-based with no front-end. It runs locally with an optional scheduler.

---

## 🤖 Tech Stack

| Component | Technology |
|----------|-------------|
| Programming Language | Python 3.10+ |
| Web Scraping | `Playwright` or `Selenium`, `BeautifulSoup`, `requests` |
| Odds Aggregation | Local Australian bookies (via scraping) |
| Arbitrage Logic | Custom Python module |
| Notification System | `discord.py` (or `nextcord`) |
| Scheduler | `asyncio` or `APScheduler` (optional) |
| Data Storage (Optional) | `SQLite` or in-memory caching |

---

## 🌐 System Architecture

```
+------------------+
|  Cron / Async    |  (Runs every X minutes)
+--------+---------+
         |
         v
+--------+---------+
|  Bookie Scrapers |
|  (AU websites)   |
+--------+---------+
         |
         v
+------------------+
|  Arb Detector    |  (Runs formula + stake calc)
+--------+---------+
         |
         v
+------------------+
|  Discord Notifier|
+------------------+
```

---

## ✅ Features

- Scrapes multiple bookies concurrently
- Handles 2-way (and future 3-way) arbitrage detection
- Configurable minimum profit threshold
- Real-time alerts via Discord with event info, odds, and stake breakdown
- Modular architecture to add more bookies easily

---

## 🤝 Future Enhancements

- Add **SQLite-based history tracking** to avoid duplicate alerts
- Integrate with **Streamlit** or **Flask** for optional dashboard
- Add support for **sharp bookies**, **crypto bookies**, or brokers (e.g. BetInAsia)
- Track daily/monthly **profitability and ROI**
- Stake scaling logic based on bankroll and confidence

---

## ⚖️ Arbitrage Formula

A sure bet exists if:

```
(1 / odds_A) + (1 / odds_B) < 1
```

Example:
- Team A: 2.10 (Bookie A)
- Team B: 2.15 (Bookie B)

```
(1 / 2.10) + (1 / 2.15) = 0.4762 + 0.4651 = 0.9413 < 1

=> Sure bet exists!
```

Stake calculation is done automatically to split your bankroll between outcomes for a guaranteed profit.

---

## 🚫 Not Using

- No front-end framework (e.g. Angular, React) is used at this stage
- No cloud deployment or third-party hosting (runs fully local)
- No use of betting APIs or offshore bookies yet

---

## 🔹 How to Use (Basic Outline)

1. Activate your Python environment
2. Run the scraper or scheduler:

```bash
python run_surebetbot.py
```

3. Watch Discord channel for alerts

---

## 🔑 Notes

- This project assumes you are familiar with safe arbitrage practices and local betting laws
- Stake responsibly, rotate accounts, and monitor for bookmaker limitations
- VPN or offshore access will be considered in future enhancements and is not required for this version

---

## 🔧 Setup Files (optional structure)

```bash
surebetbot/
├── scrapers/
│   ├── sportsbet.py
│   ├── ladbrokes.py
├── data/
│   └── markets.json
├── core/
│   ├── arbitrage.py
│   ├── stake_calc.py
│   └── notify.py
├── logs/
├── run_surebetbot.py
├── config.yaml
└── README.md
```


