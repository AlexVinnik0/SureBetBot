import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from surebetbot.core.models import Bookmaker, Event, Market, Outcome, ScrapingResult, SportType, MarketType
from surebetbot.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class SportsbetScraper(BaseScraper):
    """Scraper for Sportsbet.com.au bookmaker."""

    def __init__(self):
        """Initialize the Sportsbet scraper."""
        bookmaker = Bookmaker(
            id="sportsbet",
            name="Sportsbet",
            base_url="https://www.sportsbet.com.au"
        )
        super().__init__(bookmaker)
        self.name = "Sportsbet"
        self.base_url = "https://www.sportsbet.com.au"
        self.soccer_url = f"{self.base_url}/soccer"
        
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        
        # Create directory for debug screenshots
        self.debug_dir = "debug_screenshots"
        os.makedirs(self.debug_dir, exist_ok=True)
        
        logger.info(f"Initialized {self.name} scraper")

    def get_sport_paths(self) -> Dict[SportType, str]:
        """
        Get the path part of URLs for each sport type.
        
        Returns:
            A dictionary mapping sport types to URL paths
        """
        return {
            SportType.SOCCER: "/soccer",
            SportType.BASKETBALL: "/basketball",
            SportType.TENNIS: "/tennis",
            SportType.CRICKET: "/cricket",
            SportType.NRL: "/rugby-league",
            SportType.RUGBY: "/rugby-union",
            SportType.AFL: "/australian-rules",
            SportType.HORSE_RACING: "/horse-racing",
        }

    async def scrape(self, sport_types: Optional[List[SportType]] = None) -> ScrapingResult:
        """
        Scrape the bookmaker website for events and their odds.
        
        Args:
            sport_types: Optional list of sport types to scrape for. If None, scrape Soccer.
            
        Returns:
            A ScrapingResult containing the scraped events and metadata
        """
        if sport_types is None:
            sport_types = [SportType.SOCCER]
        
        all_events = []
        
        # Initialize browser if not already done
        if not self._browser or not self._context:
            await self.initialize()
        
        try:
            for sport_type in sport_types:
                logger.info(f"Scraping {sport_type.value} events from {self.name}")
                events = await self.scrape_sport(sport_type)
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

    async def scrape_event(self, event_url: str) -> Optional[Event]:
        """
        Scrape details for a specific event.
        
        Args:
            event_url: URL of the event to scrape
            
        Returns:
            An Event object if successful, None otherwise
        """
        return await self.scrape_url(event_url)

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

    async def _navigate_to_soccer(self, page: Page) -> bool:
        """
        Navigate to the soccer section.
        
        Args:
            page: Playwright page object
            
        Returns:
            True if navigation was successful, False otherwise
        """
        try:
            logger.info(f"Navigating to {self.soccer_url}")
            await page.goto(self.soccer_url, wait_until="domcontentloaded", timeout=30000)
            
            # Save screenshot
            await self._save_screenshot(page, "soccer")
            
            # Get page title to verify
            title = await page.title()
            logger.info(f"Page title: {title}")
            
            # Check if we need to handle cookie consent
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
            
            # Wait for page to stabilize
            await page.wait_for_timeout(2000)
            
            return True
        
        except Exception as e:
            logger.error(f"Error navigating to soccer: {str(e)}")
            return False

    async def _get_soccer_competitions(self, page: Page) -> List[Dict[str, str]]:
        """
        Get all soccer competitions available.
        
        Args:
            page: Playwright page object
            
        Returns:
            List of dictionaries with competition info
        """
        competitions = []
        
        try:
            logger.info("Looking for soccer competitions...")
            
            # Try different selectors for competitions
            competition_selectors = [
                ".competition-container",
                "[data-automation-id*='competition']",
                ".classified-list"
            ]
            
            for selector in competition_selectors:
                comp_elements = await page.locator(selector).all()
                if comp_elements:
                    logger.info(f"Found {len(comp_elements)} competitions with selector: {selector}")
                    
                    for comp in comp_elements:
                        try:
                            # Try to get competition name
                            comp_name_element = await comp.locator("h2, h3, .competition-name").first
                            comp_name = await comp_name_element.inner_text() if comp_name_element else "Unknown"
                            
                            # Try to find link to competition page
                            comp_link_element = await comp.locator("a").first
                            comp_link = await comp_link_element.get_attribute("href") if comp_link_element else None
                            
                            if comp_link:
                                competitions.append({
                                    "name": comp_name,
                                    "url": comp_link if comp_link.startswith("http") else f"{self.base_url}{comp_link}"
                                })
                        
                        except Exception as e:
                            logger.warning(f"Error parsing competition: {str(e)}")
                    
                    # If we found competitions, no need to try other selectors
                    if competitions:
                        break
            
            # If no competitions found, fall back to general approach looking for event links
            if not competitions:
                logger.warning("No soccer competitions found, falling back to general approach")
                
                # Try different selectors for events
                event_selectors = [
                    ".event-card a",
                    "[data-automation-id*='event'] a"
                ]
                
                for selector in event_selectors:
                    try:
                        logger.info(f"Trying selector: {selector}")
                        event_links = await page.locator(selector).all()
                        
                        if event_links:
                            logger.info(f"Found {len(event_links)} links with selector: {selector}")
                            
                            # Process only first 10 links to avoid overloading
                            max_links = min(len(event_links), 10)
                            
                            for i in range(max_links):
                                try:
                                    href = await event_links[i].get_attribute("href")
                                    if href:
                                        url = href if href.startswith("http") else f"{self.base_url}{href}"
                                        competitions.append({
                                            "name": "General Soccer",
                                            "url": url
                                        })
                                except Exception as e:
                                    logger.warning(f"Error getting href from event link: {str(e)}")
                            
                            break
                    except Exception as e:
                        logger.warning(f"Error with event selector {selector}: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error getting soccer competitions: {str(e)}")
        
        logger.info(f"Found {len(competitions)} competitions/events")
        return competitions

    async def _parse_event_page(self, page: Page, url: str) -> Optional[Event]:
        """
        Parse an event page to extract odds and other info.
        
        Args:
            page: Playwright page object
            url: URL of the event page
            
        Returns:
            Event object if successful, None otherwise
        """
        try:
            logger.info(f"Navigating to event: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            
            # Get page title
            title = await page.title()
            logger.info(f"Event page title: {title}")
            
            # Take screenshot
            event_name_for_file = re.sub(r'[^\w\-_]', '_', title[:30])
            await self._save_screenshot(page, f"event_{event_name_for_file}")
            
            # Wait for content to load
            await page.wait_for_timeout(1000)
            
            # Get event name from title
            event_name = title.split(" Betting Odds")[0] if " Betting Odds" in title else title
            # Parse "Race X Location" pattern
            match = re.search(r"Race \d+ (.+?)(?:\s|$)", event_name)
            if match:
                event_name = match.group(1)
            logger.info(f"Extracted event name: {event_name}")
            
            # Extract team names from title
            home_team = event_name
            away_team = ""
            
            # Get competition from URL
            competition_parts = url.split("/")
            if len(competition_parts) >= 2:
                competition_name = competition_parts[-2].replace("-", " ").title()
            else:
                competition_name = "Unknown"
            logger.info(f"Extracted competition: {competition_name}")
            
            # Get start time - for now just use current time
            start_time = datetime.now()
            
            # Get markets - simplified approach
            markets = []
            
            # Extract markets using JavaScript evaluation
            try:
                # First, get all available elements for debugging
                page_info = await page.evaluate("""
                    () => {
                        const info = {
                            title: document.title,
                            bodyText: document.body.textContent.substring(0, 500),
                            selectors: {}
                        };
                        
                        // Check common selectors
                        const selectors = [
                            '[data-automation-id*="market"]',
                            '.market-container',
                            '.market-group',
                            '[data-automation-id*="outcome"]',
                            '.outcome-button',
                            '.price-button'
                        ];
                        
                        selectors.forEach(selector => {
                            const elements = document.querySelectorAll(selector);
                            info.selectors[selector] = elements.length;
                        });
                        
                        // Get basic structure
                        const mainElements = Array.from(document.body.children)
                            .map(el => ({
                                tag: el.tagName,
                                id: el.id,
                                className: el.className,
                                childCount: el.children.length
                            }));
                        
                        info.structure = mainElements;
                        
                        return info;
                    }
                """)
                
                logger.info(f"Page structure info: {json.dumps(page_info, indent=2)}")
                
                # Try to get market data with more generic selectors
                market_data = await page.evaluate("""
                    () => {
                        const markets = [];
                        // Find any element that might be a market
                        // First try specific selectors
                        let marketElements = document.querySelectorAll('[data-automation-id*="market"], .market-container, .market-group, .betting-option');
                        
                        console.log("Found " + marketElements.length + " potential market elements");
                        
                        // If nothing found, try a broader approach (look for anything with odds/prices)
                        if (marketElements.length === 0) {
                            const priceElements = document.querySelectorAll('[data-automation-id*="price"], .price-text, .odds-text');
                            console.log("Found " + priceElements.length + " price elements");
                            
                            // Look for parent containers of price elements
                            const marketContainers = new Set();
                            priceElements.forEach(el => {
                                // Go up 3 levels to find potential market container
                                let parent = el.parentElement;
                                for (let i = 0; i < 3 && parent; i++) {
                                    if (parent.children.length > 2) {
                                        marketContainers.add(parent);
                                        break;
                                    }
                                    parent = parent.parentElement;
                                }
                            });
                            
                            marketElements = Array.from(marketContainers);
                            console.log("Found " + marketElements.length + " potential market containers from prices");
                        }
                        
                        // Process market elements
                        for (const market of marketElements) {
                            try {
                                // Try to find market name - look at nearby headings or labels
                                let marketName = "Unknown Market";
                                const nameEls = market.querySelectorAll('h1, h2, h3, h4, h5, [data-automation-id*="name"], [data-automation-id*="title"], .market-name');
                                if (nameEls.length > 0) {
                                    marketName = nameEls[0].textContent.trim();
                                } else {
                                    // Try to infer market type based on patterns of odds (especially for sports betting)
                                    // We'll determine common market types after scanning outcomes
                                }
                                
                                // Get outcomes - look for elements with price information
                                const outcomes = [];
                                // First try specific outcome selectors
                                let outcomeElements = market.querySelectorAll('[data-automation-id*="outcome"], .outcome-button, .price-button, .betting-option');
                                
                                // If nothing found, try a more general approach - find elements with price text
                                if (outcomeElements.length === 0) {
                                    outcomeElements = market.querySelectorAll('[data-automation-id*="price"], .price-text, .odds-text');
                                    // For each price element, go up one level to get the container
                                    outcomeElements = Array.from(outcomeElements).map(el => el.parentElement);
                                }
                                
                                for (const outcome of outcomeElements) {
                                    try {
                                        // Find name element
                                        let name = "Unknown";
                                        const nameEls = outcome.querySelectorAll('[data-automation-id*="name"], .outcome-name, .selection-name, span:not(.price-text):not(.odds-text)');
                                        if (nameEls.length > 0) {
                                            name = nameEls[0].textContent.trim();
                                        } else {
                                            // If no name element found, create name based on index
                                            // For horse racing, it's often just Runner 1, Runner 2, etc.
                                            name = "Selection " + (outcomes.length + 1);
                                        }
                                        
                                        // Find price element
                                        let price = null;
                                        const priceEls = outcome.querySelectorAll('[data-automation-id*="price"], .price-text, .odds-text');
                                        if (priceEls.length > 0) {
                                            const priceText = priceEls[0].textContent.trim().replace('$', '');
                                            price = parseFloat(priceText);
                                        }
                                        
                                        if (price !== null && !isNaN(price) && price > 1.0) {
                                            outcomes.push({
                                                name: name,
                                                odds: price
                                            });
                                        }
                                    } catch (e) {
                                        console.error('Error parsing outcome:', e);
                                    }
                                }
                                
                                if (outcomes.length > 0) {
                                    markets.push({
                                        name: marketName,
                                        outcomes: outcomes
                                    });
                                }
                            } catch (e) {
                                console.error('Error parsing market:', e);
                            }
                        }
                        
                        return markets;
                    }
                """)
                
                # Process the market data into our models
                for i, market_dict in enumerate(market_data):
                    market_name = market_dict.get("name", f"Market {i+1}")
                    market_type = MarketType.OTHER
                    
                    # Create outcomes
                    outcomes = []
                    for outcome_dict in market_dict.get("outcomes", []):
                        outcome_name = outcome_dict.get("name", "Unknown")
                        odds = outcome_dict.get("odds", 0.0)
                        outcomes.append(Outcome(name=outcome_name, odds=odds))
                    
                    # Try to determine market type based on outcome count/pattern
                    if len(outcomes) == 2:
                        # Could be Win/Draw/Win or Head-to-Head
                        market_type = MarketType.MONEYLINE
                        if market_name == "Unknown Market":
                            market_name = "Head to Head"
                    elif len(outcomes) == 3:
                        # Likely 1X2 market (Win/Draw/Win)
                        market_type = MarketType.WIN
                        if market_name == "Unknown Market":
                            market_name = "Match Result"
                    elif "over" in market_name.lower() or "under" in market_name.lower():
                        market_type = MarketType.TOTAL_OVER_UNDER
                    elif "handicap" in market_name.lower() or "spread" in market_name.lower():
                        market_type = MarketType.HANDICAP
                    
                    # For horse racing, use specialized market types
                    elif any(term in market_name.lower() for term in ["place"]):
                        market_type = MarketType.PLACE
                    elif any(term in market_name.lower() for term in ["each way", "e/w"]):
                        market_type = MarketType.EACH_WAY
                    elif any(term in market_name.lower() for term in ["quinella", "quin"]):
                        market_type = MarketType.QUINELLA
                    elif any(term in market_name.lower() for term in ["exacta", "forecast"]):
                        market_type = MarketType.EXACTA
                    elif any(term in market_name.lower() for term in ["trifecta", "tricast"]):
                        market_type = MarketType.TRIFECTA
                    # This should be after the other horse racing market checks
                    elif any(term in market_name.lower() for term in ["win"]) or (market_name == "Unknown Market" and event_name and any(term in event_name.lower() for term in ["race", "racing"])):
                        market_name = "Win"
                        market_type = MarketType.WIN
                    
                    # Add market if it has outcomes
                    if outcomes:
                        market_id = f"{market_name.lower().replace(' ', '_')}_{i}"
                        markets.append(Market(
                            id=market_id,
                            type=market_type,
                            name=market_name,
                            outcomes=outcomes
                        ))
                        logger.info(f"Added market: {market_name} with {len(outcomes)} outcomes")
            
        except Exception as e:
            logger.error(f"Error extracting markets with JavaScript: {str(e)}")
        
        if not markets:
            logger.warning(f"No markets found for event: {url}")
            return None
        
        # Create unique ID for the event
        event_id = f"sportsbet_{url.split('/')[-1]}"
        
        # Determine the sport type from the URL
        sport_type = SportType.SOCCER  # Default sport type
        if "horse-racing" in url:
            sport_type = SportType.HORSE_RACING
        elif "harness-racing" in url:
            sport_type = SportType.HORSE_RACING  # Use horse racing as a fallback
        elif "greyhound" in url:
            sport_type = SportType.OTHER
        elif "basketball" in url:
            sport_type = SportType.BASKETBALL
        elif "tennis" in url:
            sport_type = SportType.TENNIS
        elif "cricket" in url:
            sport_type = SportType.CRICKET
        elif "rugby" in url:
            sport_type = SportType.RUGBY
        elif "afl" in url or "australian-rules" in url:
            sport_type = SportType.AFL
        
        # Create and return the event
        return Event(
            id=event_id,
            sport=sport_type,
            home_team=home_team,
            away_team=away_team,
            competition=competition_name,
            start_time=start_time,
            markets=markets,
            bookmaker=self.bookmaker,
            url=url
        )
    
    except Exception as e:
        logger.error(f"Error parsing event page: {str(e)}")
        return None

    async def scrape_sport(self, sport: SportType) -> List[Event]:
        """
        Scrape events for the specified sport.
        
        Args:
            sport: The sport to scrape
            
        Returns:
            A list of events
        """
        events = []
        
        if not self._context:
            logger.error("Scraper not initialized")
            return []
        
        try:
            # Create a new page
            page = await self._context.new_page()
            
            # Special handling for horse racing
            if sport == SportType.HORSE_RACING:
                events = await self._scrape_horse_racing(page)
                await page.close()
                return events
            
            # Navigate to soccer page
            success = await self._navigate_to_soccer(page)
            if not success:
                logger.error("Failed to navigate to soccer page")
                await page.close()
                return []
            
            # Get soccer competitions/events
            competitions = await self._get_soccer_competitions(page)
            
            # Process a limited number of event links
            max_events = min(len(competitions), 10)
            logger.info(f"Processing {max_events} event links")
            
            for i in range(max_events):
                event_url = competitions[i]["url"]
                event = await self._parse_event_page(page, event_url)
                
                if event:
                    events.append(event)
                    # Save debug info (but not the full event object)
                    debug_file = os.path.join(self.debug_dir, f"event_{event.id}.json")
                    with open(debug_file, "w") as f:
                        # Create a simplified dict representation for debugging
                        event_debug = {
                            "id": event.id,
                            "sport": event.sport.name,
                            "home_team": event.home_team,
                            "away_team": event.away_team,
                            "competition": event.competition,
                            "url": event.url,
                            "market_count": len(event.markets)
                        }
                        json.dump(event_debug, f, indent=2, default=str)
                
                # Small delay between requests
                await asyncio.sleep(1)
            
            # Close the page
            await page.close()
        
        except Exception as e:
            logger.error(f"Error scraping {sport.name}: {str(e)}")
        
        logger.info(f"Found {len(events)} {sport.name.lower()} events")
        return events

    async def _scrape_horse_racing(self, page: Page) -> List[Event]:
        """
        Specifically scrape horse racing events, clicking into individual races
        to get detailed information.
        
        Args:
            page: The Playwright page
            
        Returns:
            List of horse racing events
        """
        events = []
        horse_racing_url = f"{self.base_url}/horse-racing"
        
        try:
            # Navigate to horse racing page
            logger.info(f"Navigating to horse racing: {horse_racing_url}")
            await page.goto(horse_racing_url, wait_until="domcontentloaded", timeout=30000)
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
                            meeting_name_element = await meeting.locator("h2, h3, .meeting-name").first
                            meeting_name = await meeting_name_element.inner_text() if meeting_name_element else "Unknown Meeting"
                            
                            # Get all race links from this meeting
                            race_elements = await meeting.locator("a").all()
                            
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
                    race_elements = await page.locator(selector).all()
                    if race_elements and len(race_elements) > 0:
                        logger.info(f"Found {len(race_elements)} race links with selector: {selector}")
                        
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
            await page.goto(race_url, wait_until="domcontentloaded", timeout=30000)
            
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
                    const raceNumberMatch = data.raceName.match(/Race (\d+)/i);
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

    async def scrape_url(self, url: str) -> Optional[Event]:
        """
        Scrape a specific event URL.
        
        Args:
            url: The URL to scrape
            
        Returns:
            The event if found, None otherwise
        """
        if not self._context:
            logger.error("Scraper not initialized")
            return None
        
        try:
            # Create a new page
            page = await self._context.new_page()
            
            # Parse the event page
            event = await self._parse_event_page(page, url)
            
            # Close the page
            await page.close()
            
            return event
        
        except Exception as e:
            logger.error(f"Error scraping URL {url}: {str(e)}")
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
            
        # Call parent cleanup method
        await super().cleanup() 