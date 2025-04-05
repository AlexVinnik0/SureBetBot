"""
Sportsbet horse racing scraper module.

This module contains a specialized scraper for horse racing events
from Sportsbet.com.au bookmaker.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Union

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from surebetbot.core.models import Bookmaker, Event, Market, Outcome, ScrapingResult, SportType, MarketType
from surebetbot.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class SportsbetHorseRacingScraper(BaseScraper):
    """Specialized scraper for Sportsbet.com.au horse racing markets."""

    def __init__(self):
        """Initialize the Sportsbet horse racing scraper."""
        bookmaker = Bookmaker(
            id="sportsbet",
            name="Sportsbet",
            base_url="https://www.sportsbet.com.au"
        )
        super().__init__(bookmaker)
        self.name = "Sportsbet Horse Racing"
        self.base_url = "https://www.sportsbet.com.au"
        self.horse_racing_url = f"{self.base_url}/horse-racing"
        
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        
        # Create directory for debug screenshots
        self.debug_dir = "debug_screenshots"
        os.makedirs(self.debug_dir, exist_ok=True)
        
        logger.info(f"Initialized {self.name} scraper")

    async def scrape(self) -> ScrapingResult:
        """
        Scrape horse racing events from Sportsbet.
        
        Returns:
            A ScrapingResult containing the scraped events and metadata
        """
        all_events = []
        
        # Initialize browser if not already done
        if not self._browser or not self._context:
            await self.initialize()
        
        try:
            logger.info(f"Scraping horse racing events from {self.name}")
            events = await self._scrape_horse_racing()
            all_events.extend(events)
        
        except Exception as e:
            logger.error(f"Error scraping {self.name}: {str(e)}")
        
        finally:
            # Clean up resources
            await self.cleanup()
        
        return ScrapingResult(
            bookmaker=self.bookmaker,
            events=all_events,
            timestamp=datetime.now()
        )

    async def initialize(self) -> None:
        """Initialize the browser and context."""
        logger.info(f"Initializing {self.name} scraper")
        
        # Launch playwright and browser
        playwright = await async_playwright().start()
        
        # Use Firefox as it works better with Sportsbet
        self._browser = await playwright.firefox.launch(
            headless=False,  # Set to True in production
        )
        
        # Create a browser context with extended timeout
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/124.0",
        )
        self._context.set_default_timeout(30000)  # 30 seconds
        
        logger.info(f"{self.name} scraper initialized successfully")

    async def _save_screenshot(self, page: Page, name: str) -> str:
        """
        Save a screenshot for debugging purposes.
        
        Args:
            page: The page to screenshot
            name: Name of the screenshot file
            
        Returns:
            Path to the saved screenshot
        """
        clean_name = re.sub(r'[^\w\-_]', '_', name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sportsbet_{clean_name}_{timestamp}.png"
        path = os.path.join(self.debug_dir, filename)
        
        await page.screenshot(path=path)
        logger.info(f"Screenshot saved to {path}")
        
        return path

    async def _scrape_horse_racing(self) -> List[Event]:
        """
        Specifically scrape horse racing events, clicking into individual races
        to get detailed information.
        
        Returns:
            List of horse racing events
        """
        events = []
        
        try:
            # Create a new page
            page = await self._context.new_page()
            
            # Navigate to horse racing page
            logger.info(f"Navigating to horse racing: {self.horse_racing_url}")
            try:
                await page.goto(self.horse_racing_url, wait_until="domcontentloaded", timeout=60000)
                # Add additional waiting to ensure content is loaded
                await page.wait_for_load_state("load", timeout=30000)
            except Exception as e:
                logger.warning(f"Navigation timed out, but continuing: {e}")
                
            await self._save_screenshot(page, "horse_racing_main")
            
            # Handle cookie consent if needed
            for consent_selector in [
                "button:has-text('Accept')", 
                "button:has-text('Agree')",
                "button:has-text('Accept All')",
                "[aria-label='Accept cookies']",
                ".cookie-consent button"
            ]:
                try:
                    consent = page.locator(consent_selector)
                    if await consent.count() > 0:
                        logger.info(f"Accepting cookies with selector: {consent_selector}")
                        await consent.click()
                        await page.wait_for_timeout(1000)
                        break
                except Exception:
                    pass
            
            # Wait for page to load
            await page.wait_for_timeout(2000)
            
            # Find all race meetings
            race_meetings = []
            meeting_selectors = [
                ".meeting-item", 
                "[data-automation-id*='meeting']",
                ".race-meeting",
                ".classified-list > div"
            ]
            
            for selector in meeting_selectors:
                meeting_elements = await page.locator(selector).all()
                if meeting_elements and len(meeting_elements) > 0:
                    logger.info(f"Found {len(meeting_elements)} race meetings with selector: {selector}")
                    
                    for meeting in meeting_elements:
                        try:
                            # Try to get meeting name
                            meeting_name_locator = meeting.locator("h2, h3, .meeting-name")
                            has_meeting_name = await meeting_name_locator.count() > 0
                            meeting_name_element = meeting_name_locator.first() if has_meeting_name else None
                            meeting_name = await meeting_name_element.inner_text() if meeting_name_element else "Unknown Meeting"
                            
                            # Get all race links from this meeting
                            race_locator = meeting.locator("a")
                            race_elements = await race_locator.all()
                            
                            for race_element in race_elements:
                                try:
                                    race_href = await race_element.get_attribute("href")
                                    race_text = await race_element.inner_text()
                                    
                                    # Verify this is a race link (check for "Race" in text or URL format)
                                    if race_href and ("race" in race_href.lower() or "race" in race_text.lower()):
                                        race_url = race_href if race_href.startswith("http") else f"{self.base_url}{race_href}"
                                        race_meetings.append({
                                            "meeting": meeting_name,
                                            "race_name": race_text.strip(),
                                            "url": race_url
                                        })
                                except Exception as e:
                                    logger.warning(f"Error parsing race link: {str(e)}")
                        except Exception as e:
                            logger.warning(f"Error parsing meeting: {str(e)}")
                    
                    # If we found meetings, no need to try other selectors
                    if race_meetings:
                        break
            
            # If we didn't find race meetings with specific selectors, try a more general approach
            if not race_meetings:
                logger.info("No race meetings found with specific selectors, trying general race links")
                race_link_selectors = [
                    "a[href*='race']",
                    "a[href*='horse-racing']",
                    ".race-card a",
                    "[data-automation-id*='race'] a"
                ]
                
                for selector in race_link_selectors:
                    race_link_locator = page.locator(selector)
                    race_link_count = await race_link_locator.count()
                    
                    if race_link_count > 0:
                        logger.info(f"Found {race_link_count} race links with selector: {selector}")
                        race_elements = await race_link_locator.all()
                        
                        for race_element in race_elements:
                            try:
                                race_href = await race_element.get_attribute("href")
                                race_text = await race_element.inner_text()
                                
                                if race_href:
                                    race_url = race_href if race_href.startswith("http") else f"{self.base_url}{race_href}"
                                    
                                    # Extract meeting name from URL if possible
                                    url_parts = race_url.split("/")
                                    meeting_name = "Unknown Meeting"
                                    for part in url_parts:
                                        if part and part not in ["horse-racing", "race"] and not part.startswith("race-"):
                                            meeting_name = part.replace("-", " ").title()
                                            break
                                    
                                    race_meetings.append({
                                        "meeting": meeting_name,
                                        "race_name": race_text.strip(),
                                        "url": race_url
                                    })
                            except Exception as e:
                                logger.warning(f"Error parsing general race link: {str(e)}")
                        
                        # If we found race links, no need to try other selectors
                        if race_meetings:
                            break
            
            logger.info(f"Found {len(race_meetings)} total races")
            
            # Limit the number of races to process to avoid overloading
            max_races = min(len(race_meetings), 10)
            
            # Process each race by navigating to its page
            for i in range(max_races):
                race = race_meetings[i]
                race_url = race["url"]
                
                logger.info(f"Processing race {i+1}/{max_races}: {race['race_name']} at {race['meeting']}")
                event = await self._parse_horse_race(page, race_url, race["meeting"], race["race_name"])
                
                if event:
                    events.append(event)
                    
                    # Save debug info
                    debug_file = os.path.join(self.debug_dir, f"race_{event.id}.json")
                    with open(debug_file, "w") as f:
                        # Create a simplified dict representation for debugging
                        event_debug = {
                            "id": event.id,
                            "name": event.home_team,
                            "meeting": event.competition,
                            "url": event.url,
                            "market_count": len(event.markets)
                        }
                        json.dump(event_debug, f, indent=2, default=str)
                
                # Small delay between requests
                await asyncio.sleep(1)
            
            # Close the page
            await page.close()
        
        except Exception as e:
            logger.error(f"Error scraping horse racing: {str(e)}")
        
        logger.info(f"Found {len(events)} horse racing events")
        return events

    async def _parse_horse_race(self, page: Page, race_url: str, meeting_name: str, race_name: str) -> Optional[Event]:
        """
        Parse a specific horse race page to extract runners and markets.
        
        Args:
            page: The Playwright page
            race_url: URL of the race
            meeting_name: Name of the race meeting
            race_name: Name of the race
            
        Returns:
            Event object if successful, None otherwise
        """
        try:
            logger.info(f"Navigating to race: {race_url}")
            try:
                await page.goto(race_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                logger.warning(f"Navigation timed out, but continuing: {e}")
            
            # Wait for page to load
            await page.wait_for_timeout(2000)
            
            # Take screenshot for debugging
            race_name_file = re.sub(r'[^\w\-_]', '_', race_name[:30])
            await self._save_screenshot(page, f"race_{race_name_file}")
            
            # Extract detailed race information using JavaScript
            race_data = await page.evaluate("""
                () => {
                    const data = {
                        raceName: document.title.split(" - ")[0] || document.title,
                        raceNumber: null,
                        raceTime: null,
                        venue: null,
                        runnerCount: 0,
                        runners: [],
                        markets: []
                    };
                    
                    // Try to get race number from title or content
                    const raceNumberMatch = data.raceName.match(/Race (\\d+)/i);
                    if (raceNumberMatch) {
                        data.raceNumber = raceNumberMatch[1];
                    }
                    
                    // Try to extract venue from URL or page content
                    const pathParts = window.location.pathname.split('/');
                    for (const part of pathParts) {
                        if (part && !['horse-racing', 'race'].includes(part) && !part.startsWith('race-')) {
                            data.venue = part.replace(/-/g, ' ').replace(/\\b\\w/g, c => c.toUpperCase());
                            break;
                        }
                    }
                    
                    // Try to get race time
                    const timeElements = document.querySelectorAll('[data-automation-id*="time"], .race-time, time');
                    if (timeElements.length > 0) {
                        data.raceTime = timeElements[0].textContent.trim();
                    }
                    
                    // Extract runners - find the table or list of runners
                    const runnerElements = document.querySelectorAll('[data-automation-id*="runner"], .runner-row, .runner-item, .betting-option-table tr');
                    data.runnerCount = runnerElements.length;
                    
                    runnerElements.forEach((runner, index) => {
                        try {
                            const runnerData = {
                                number: index + 1,
                                name: "Unknown Runner",
                                jockey: null,
                                trainer: null,
                                barrier: null,
                                weight: null,
                                silkUrl: null,
                                odds: {}
                            };
                            
                            // Extract runner number if available
                            const numberElements = runner.querySelectorAll('[data-automation-id*="number"], .runner-number');
                            if (numberElements.length > 0) {
                                const numberText = numberElements[0].textContent.trim();
                                const numberMatch = numberText.match(/\\d+/);
                                if (numberMatch) {
                                    runnerData.number = parseInt(numberMatch[0]);
                                }
                            }
                            
                            // Extract runner name
                            const nameElements = runner.querySelectorAll('[data-automation-id*="name"], .runner-name, .horse-name');
                            if (nameElements.length > 0) {
                                runnerData.name = nameElements[0].textContent.trim();
                            }
                            
                            // Extract jockey if available
                            const jockeyElements = runner.querySelectorAll('[data-automation-id*="jockey"], .jockey-name');
                            if (jockeyElements.length > 0) {
                                runnerData.jockey = jockeyElements[0].textContent.trim();
                            }
                            
                            // Extract trainer if available
                            const trainerElements = runner.querySelectorAll('[data-automation-id*="trainer"], .trainer-name');
                            if (trainerElements.length > 0) {
                                runnerData.trainer = trainerElements[0].textContent.trim();
                            }
                            
                            // Extract barrier if available
                            const barrierElements = runner.querySelectorAll('[data-automation-id*="barrier"], .barrier');
                            if (barrierElements.length > 0) {
                                const barrierText = barrierElements[0].textContent.trim();
                                const barrierMatch = barrierText.match(/\\d+/);
                                if (barrierMatch) {
                                    runnerData.barrier = parseInt(barrierMatch[0]);
                                }
                            }
                            
                            // Extract weight if available
                            const weightElements = runner.querySelectorAll('[data-automation-id*="weight"], .weight');
                            if (weightElements.length > 0) {
                                runnerData.weight = weightElements[0].textContent.trim();
                            }
                            
                            // Try to find silk/colors image
                            const silkElements = runner.querySelectorAll('img[src*="silk"], img[src*="color"], .silk-image');
                            if (silkElements.length > 0) {
                                runnerData.silkUrl = silkElements[0].src;
                            }
                            
                            // Extract Win odds
                            const winOddsElements = runner.querySelectorAll('[data-automation-id*="win-price"], [data-automation-id*="fixed-price"], .win-price, .fixed-price, .price-button');
                            if (winOddsElements.length > 0) {
                                const priceText = winOddsElements[0].textContent.trim().replace('$', '');
                                const price = parseFloat(priceText);
                                if (!isNaN(price) && price > 1.0) {
                                    runnerData.odds.win = price;
                                }
                            }
                            
                            // Extract Place odds if available
                            const placeOddsElements = runner.querySelectorAll('[data-automation-id*="place-price"], .place-price');
                            if (placeOddsElements.length > 0) {
                                const priceText = placeOddsElements[0].textContent.trim().replace('$', '');
                                const price = parseFloat(priceText);
                                if (!isNaN(price) && price > 1.0) {
                                    runnerData.odds.place = price;
                                }
                            }
                            
                            data.runners.push(runnerData);
                        } catch (e) {
                            console.error('Error parsing runner:', e);
                        }
                    });
                    
                    // Try to identify different market types
                    const marketTypes = ['Win', 'Place', 'Each Way', 'Quinella', 'Exacta', 'Trifecta'];
                    const marketContainers = document.querySelectorAll('[data-automation-id*="market"], .market-container, .market-group, .tab-content, .betting-category');
                    
                    if (marketContainers.length === 0) {
                        // If we didn't find specific market containers, look for market tabs
                        const marketTabs = document.querySelectorAll('.tab, .tab-item, [role="tab"]');
                        marketTabs.forEach(tab => {
                            const tabText = tab.textContent.trim();
                            // Check if this tab corresponds to a known market type
                            const matchedMarket = marketTypes.find(marketType => 
                                tabText.toLowerCase().includes(marketType.toLowerCase()));
                            
                            if (matchedMarket) {
                                data.markets.push({
                                    name: matchedMarket,
                                    available: true
                                });
                            }
                        });
                    } else {
                        // Process market containers
                        marketContainers.forEach(container => {
                            try {
                                // Get market name
                                let marketName = "Unknown";
                                const nameEls = container.querySelectorAll('h2, h3, h4, .market-name, .market-title');
                                if (nameEls.length > 0) {
                                    marketName = nameEls[0].textContent.trim();
                                }
                                
                                // Check if this is a known market type
                                const matchedMarket = marketTypes.find(marketType => 
                                    marketName.toLowerCase().includes(marketType.toLowerCase()));
                                
                                if (matchedMarket) {
                                    data.markets.push({
                                        name: matchedMarket,
                                        available: true
                                    });
                                } else if (marketName && marketName !== "Unknown") {
                                    // Add any other market we found
                                    data.markets.push({
                                        name: marketName,
                                        available: true
                                    });
                                }
                            } catch (e) {
                                console.error('Error parsing market container:', e);
                            }
                        });
                    }
                    
                    // If we didn't find any markets, add win market based on odds
                    if (data.markets.length === 0 && data.runners.some(r => r.odds.win)) {
                        data.markets.push({
                            name: 'Win',
                            available: true
                        });
                    }
                    
                    // Add place market if we found place odds
                    if (!data.markets.some(m => m.name === 'Place') && 
                        data.runners.some(r => r.odds.place)) {
                        data.markets.push({
                            name: 'Place',
                            available: true
                        });
                    }
                    
                    return data;
                }
            """)
            
            logger.info(f"Extracted race data: {json.dumps(race_data, indent=2)}")
            
            # Create markets based on the data we extracted
            markets = []
            
            # Process runners and create markets
            runners = race_data.get("runners", [])
            
            # Create Win market if we have win odds
            win_outcomes = []
            for runner in runners:
                win_odds = runner.get("odds", {}).get("win")
                if win_odds and win_odds > 1.0:
                    runner_name = runner.get("name", f"Runner {runner.get('number', '?')}")
                    runner_number = runner.get("number", "")
                    
                    # Format the outcome name to include number and name
                    outcome_name = f"{runner_number}. {runner_name}"
                    if runner.get("jockey"):
                        outcome_name += f" ({runner.get('jockey')})"
                    
                    win_outcomes.append(Outcome(name=outcome_name, odds=win_odds))
            
            if win_outcomes:
                win_market = Market(
                    id="win",
                    type=MarketType.WIN,
                    name="Win",
                    outcomes=win_outcomes
                )
                markets.append(win_market)
            
            # Create Place market if we have place odds
            place_outcomes = []
            for runner in runners:
                place_odds = runner.get("odds", {}).get("place")
                if place_odds and place_odds > 1.0:
                    runner_name = runner.get("name", f"Runner {runner.get('number', '?')}")
                    runner_number = runner.get("number", "")
                    
                    # Format the outcome name to include number and name
                    outcome_name = f"{runner_number}. {runner_name}"
                    if runner.get("jockey"):
                        outcome_name += f" ({runner.get('jockey')})"
                    
                    place_outcomes.append(Outcome(name=outcome_name, odds=place_odds))
            
            if place_outcomes:
                place_market = Market(
                    id="place",
                    type=MarketType.PLACE,
                    name="Place",
                    outcomes=place_outcomes
                )
                markets.append(place_market)
            
            # Check if we have both win and place markets for Each Way
            if win_outcomes and place_outcomes:
                # Create a separate Each Way market (for display only - not used in calculations)
                each_way_market = Market(
                    id="each_way",
                    type=MarketType.EACH_WAY,
                    name="Each Way",
                    outcomes=win_outcomes  # Use win odds (place component calculated separately)
                )
                markets.append(each_way_market)
            
            # Create an event ID from URL
            event_id = f"sportsbet_{race_url.split('/')[-1]}"
            
            # Clean up race name
            if race_data.get("raceName"):
                race_name = race_data.get("raceName")
            
            # Use race number in name if available
            if race_data.get("raceNumber"):
                race_name = f"Race {race_data.get('raceNumber')} - {race_name}"
            
            # Create the event
            event = Event(
                id=event_id,
                sport=SportType.HORSE_RACING,
                home_team=race_name,
                away_team="",  # No away team in horse racing
                competition=meeting_name,
                start_time=datetime.now(),  # Use current time as fallback
                markets=markets,
                bookmaker=self.bookmaker,
                url=race_url
            )
            
            return event
        
        except Exception as e:
            logger.error(f"Error parsing horse race: {str(e)}")
            return None

    async def cleanup(self) -> None:
        """Close the browser and clean up resources."""
        logger.info(f"Closing {self.name} scraper")
        
        if self._context:
            await self._context.close()
            self._context = None
        
        if self._browser:
            await self._browser.close()
            self._browser = None
            
        # Call parent cleanup method if necessary
        await super().cleanup()

    def get_sport_paths(self) -> Dict[SportType, str]:
        """
        Get the path part of URLs for each sport type.
        
        Returns:
            A dictionary mapping sport types to URL paths
        """
        return {
            SportType.HORSE_RACING: "/horse-racing",
        }
    
    async def scrape_event(self, event_url: str) -> Optional[Event]:
        """
        Scrape a specific horse racing event.
        
        Args:
            event_url: The URL of the event to scrape
            
        Returns:
            Event object if successful, None otherwise
        """
        if not self._context:
            await self.initialize()
        
        try:
            page = await self._context.new_page()
            race_name = "Unknown Race"
            meeting_name = "Unknown Meeting"
            
            # Extract meeting name and race name from URL parts
            url_parts = event_url.split("/")
            for part in url_parts:
                if part and part not in ["horse-racing", "race"] and not part.startswith("race-"):
                    meeting_name = part.replace("-", " ").title()
            
            # Try to extract race number if present
            race_match = re.search(r"race-(\d+)", event_url)
            if race_match:
                race_name = f"Race {race_match.group(1)}"
            
            event = await self._parse_horse_race(page, event_url, meeting_name, race_name)
            await page.close()
            return event
        
        except Exception as e:
            logger.error(f"Error scraping event {event_url}: {str(e)}")
            return None
    
    async def scrape_sport(self, sport_type: SportType) -> List[Event]:
        """
        Scrape events for a specific sport type (only supports horse racing).
        
        Args:
            sport_type: The sport type to scrape
            
        Returns:
            List of events
        """
        if sport_type != SportType.HORSE_RACING:
            logger.warning(f"This scraper only supports horse racing, but {sport_type.name} was requested")
            return []
        
        result = await self.scrape()
        return result.events 