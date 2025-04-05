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

---

## 📋 Testing Australian Bookmaker Access

Due to geo-restrictions on Australian bookmaker sites, testing access is an important first step.

### Testing Scripts

All testing scripts are located in the `surebetbot/tests/` directory. To run tests, ensure you are in the project root directory.

#### 1. Soccer Navigation Test

This test specifically checks if we can navigate to the soccer section of bookmaker websites, simulating the "Sports > Soccer" navigation path.

```bash
python -m surebetbot.tests.test_soccer_navigation
```

This script:
- Tries to access the Sports menu on each bookmaker site
- Finds and clicks on Soccer links
- Captures screenshots at each step
- Reports if it found soccer events/competitions

#### 2. Scraper Tests

To test the full scraper functionality for Sportsbet:

```bash
python -m surebetbot.tests.test_scrapers
```

This runs the full scraping logic to extract events and odds, verifying that the scraper can handle the website's structure.

### Results & Recommendations

Based on our testing, we've found:

1. **Sportsbet:** Works reliably with Firefox browser when accessed from Australia
2. **TAB:** Has UI issues making soccer navigation difficult
3. **Ladbrokes:** Requires additional navigation approaches

**We recommend focusing on Sportsbet first** as the primary bookmaker for development and testing.

### Debug Screenshots

Screenshots from test runs are saved to:
- `debug_screenshots/` - For general scraper tests
- `debug_soccer_nav/` - For soccer navigation tests

These screenshots are useful for debugging navigation issues or scraper problems.

### Mock Data Testing

For development or when bookmaker sites are inaccessible, use the mock data module:

```bash
python -m surebetbot.cmd.mock_test --min-profit 1.0
```

This generates artificial data to test the arbitrage logic without needing actual website access.

---

## 📊 Sportsbet-Focused Scraping

Based on testing results, we've developed enhanced scrapers focused on Sportsbet, which has proven most reliable for Australian users.

### Running the Sportsbet Scraper

To scrape events from Sportsbet:

```bash
python -m surebetbot.cmd.scrape_sportsbet
```

This will:
1. Launch a browser
2. Navigate to Sportsbet
3. Extract available events, with best results for horse racing events
4. Identify various sport types based on URL patterns
5. Display the results in a readable format
6. Save the collected data to JSON files in the `output/` directory

While the scraper was initially designed for soccer events, it has been enhanced to better support horse racing events, which have shown more reliable results in testing. The scraper automatically detects the sport type based on the URL and formats the output accordingly.

### Features of the Enhanced Sportsbet Scraper:

- **Sport Type Detection**: Automatically identifies horse racing, harness racing, greyhound racing, and other sports
- **Customized Formatting**: Different output formats for racing events vs. team sports
- **Multiple Selector Strategies**: Falls back to alternative selectors if primary ones fail
- **Detailed Logging**: Comprehensive logging for troubleshooting
- **Debug Screenshots**: Captures webpage screenshots during scraping for visual debugging

### Debugging

Debug files are saved to:
- `debug_screenshots/`: Contains snapshots of website navigation
- `output/`: Contains extracted event data in JSON format

---


