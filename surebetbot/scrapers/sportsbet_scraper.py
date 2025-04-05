import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from surebetbot.core.models import Event, Market, Outcome, SportType
from surebetbot.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class SportsbetScraper(BaseScraper):
    """Scraper for Sportsbet.com.au bookmaker."""

    def __init__(self):
        """Initialize the Sportsbet scraper."""
        super().__init__()
        self.name = "Sportsbet"
        self.base_url = "https://www.sportsbet.com.au"
        self.soccer_url = f"{self.base_url}/soccer"
        
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        
        # Create directory for debug screenshots
        self.debug_dir = "debug_screenshots"
        os.makedirs(self.debug_dir, exist_ok=True)
        
        logger.info(f"Initialized {self.name} scraper")

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
            
            # Get event name
            event_name = ""
            event_name_selectors = ["h1", ".event-header__name", "[data-automation-id*='event-name']"]
            
            for selector in event_name_selectors:
                try:
                    name_element = page.locator(selector).first
                    if await name_element.count() > 0:
                        event_name = await name_element.inner_text()
                        logger.info(f"Found event name with selector {selector}: {event_name}")
                        break
                except Exception:
                    pass
            
            if not event_name:
                logger.warning(f"Could not find event name for: {url}")
                return None
            
            # Try to parse team names from event name
            home_team = ""
            away_team = ""
            
            # Common patterns for soccer matches: "Team A vs Team B" or "Team A v Team B"
            vs_match = re.search(r'(.+?)\s+(?:vs|v)\s+(.+?)(?:\s+-|\s+\||\s+$)', event_name, re.IGNORECASE)
            if vs_match:
                home_team = vs_match.group(1).strip()
                away_team = vs_match.group(2).strip()
                logger.info(f"Parsed teams: {home_team} vs {away_team}")
            else:
                logger.warning(f"Could not parse teams from event name: {event_name}")
            
            # Get competition name
            competition_name = ""
            competition_selectors = [".competition-name", ".event-header__competition", "[data-automation-id*='competition']"]
            
            for selector in competition_selectors:
                try:
                    comp_element = page.locator(selector).first
                    if await comp_element.count() > 0:
                        competition_name = await comp_element.inner_text()
                        break
                except Exception:
                    pass
            
            # If no competition name found, use part of the title
            if not competition_name and " - " in title:
                competition_name = title.split(" - ")[0]
            
            # Get event start time
            start_time = datetime.now()  # Default to now if we can't find actual time
            time_selectors = [
                ".event-header__start-time", 
                ".event-card__start-time", 
                "[data-automation-id*='start-time']",
                "time"
            ]
            
            for selector in time_selectors:
                try:
                    time_element = page.locator(selector).first
                    if await time_element.count() > 0:
                        time_text = await time_element.inner_text()
                        # We'd need to parse the time text, which can be complex
                        # For now, just log it and keep default time
                        logger.info(f"Found time text: {time_text}")
                        break
                except Exception:
                    pass
            
            # Find markets
            markets = []
            
            # Check for market containers
            market_selectors = ["[data-automation-id*='market']", ".market-container", ".betting-market"]
            
            for selector in market_selectors:
                try:
                    market_elements = await page.locator(selector).all()
                    if market_elements:
                        logger.info(f"Found {len(market_elements)} markets with selector: {selector}")
                        
                        for market_element in market_elements:
                            try:
                                # Get market name
                                market_name_element = await market_element.locator(".market-name, h3, [data-automation-id*='market-name']").first
                                market_name = await market_name_element.inner_text() if market_name_element else "Unknown Market"
                                
                                # Process outcomes
                                outcomes = []
                                outcome_elements = await market_element.locator(".outcome-button, .price-button, [data-automation-id*='outcome']").all()
                                
                                for outcome_element in outcome_elements:
                                    try:
                                        # Get outcome name
                                        name_element = await outcome_element.locator(".outcome-name, .selection-name").first
                                        outcome_name = await name_element.inner_text() if name_element else "Unknown"
                                        
                                        # Get odds
                                        odds_element = await outcome_element.locator(".price-text, .odds-text, [data-automation-id*='price']").first
                                        odds_text = await odds_element.inner_text() if odds_element else "0"
                                        
                                        # Clean and parse odds
                                        odds_text = odds_text.replace("$", "").strip()
                                        try:
                                            odds = float(odds_text)
                                            
                                            # Add outcome if odds are valid
                                            if odds > 1.0:
                                                outcomes.append(Outcome(name=outcome_name, odds=odds))
                                        except ValueError:
                                            logger.warning(f"Could not parse odds: {odds_text}")
                                    
                                    except Exception as e:
                                        logger.warning(f"Error parsing outcome: {str(e)}")
                                
                                # Add market if it has outcomes
                                if outcomes:
                                    markets.append(Market(name=market_name, outcomes=outcomes))
                            
                            except Exception as e:
                                logger.warning(f"Error parsing market: {str(e)}")
                        
                        # If we found markets, no need to try other selectors
                        if markets:
                            break
                
                except Exception as e:
                    logger.warning(f"Error with market selector {selector}: {str(e)}")
            
            if not markets:
                logger.warning(f"No markets found for event: {url}")
                return None
            
            # Create unique ID for the event
            event_id = f"sportsbet_{url.split('/')[-1]}"
            
            # Create and return the event
            return Event(
                id=event_id,
                bookmaker_id="sportsbet",
                bookmaker_name=self.name,
                sport=SportType.SOCCER,
                competition_name=competition_name,
                home_team=home_team,
                away_team=away_team,
                start_time=start_time,
                url=url,
                markets=markets
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
        if sport != SportType.SOCCER:
            logger.warning(f"Sport {sport.name} not supported by {self.name} scraper")
            return []
        
        events = []
        
        if not self._context:
            logger.error("Scraper not initialized")
            return []
        
        try:
            # Create a new page
            page = await self._context.new_page()
            
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
                    # Save to debug file
                    debug_file = os.path.join(self.debug_dir, f"event_{event.id}.json")
                    with open(debug_file, "w") as f:
                        json.dump(event.dict(), f, indent=2, default=str)
                
                # Small delay between requests
                await asyncio.sleep(1)
            
            # Close the page
            await page.close()
        
        except Exception as e:
            logger.error(f"Error scraping {sport.name}: {str(e)}")
        
        logger.info(f"Found {len(events)} soccer events")
        return events

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

    async def close(self) -> None:
        """Close the browser and clean up resources."""
        logger.info(f"Closing {self.name} scraper")
        
        if self._context:
            await self._context.close()
            self._context = None
        
        if self._browser:
            await self._browser.close()
            self._browser = None 