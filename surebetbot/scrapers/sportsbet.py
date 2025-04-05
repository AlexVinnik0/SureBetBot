from datetime import datetime
from typing import Dict, List, Optional
import os

from surebetbot.core.models import Bookmaker, Event, Market, MarketType, Outcome, ScrapingResult, SportType
from surebetbot.scrapers.base_scraper import BaseScraper


class SportsbetScraper(BaseScraper):
    """
    Scraper for Sportsbet Australia.
    """
    
    def uses_browser(self) -> bool:
        """
        Sportsbet requires a browser to render JavaScript content.
        """
        return True
    
    def get_sport_paths(self) -> Dict[SportType, str]:
        """
        Get the path part of URLs for each sport type.
        """
        return {
            SportType.SOCCER: "/soccer",
            SportType.BASKETBALL: "/basketball",
            SportType.TENNIS: "/tennis",
            SportType.RUGBY: "/rugby",
            SportType.AFL: "/australian-rules",
            SportType.NRL: "/rugby-league",
            SportType.CRICKET: "/cricket",
            SportType.HORSE_RACING: "/horse-racing",
            SportType.ESPORTS: "/esports",
        }
    
    async def scrape(self, sport_types: Optional[List[SportType]] = None) -> ScrapingResult:
        """
        Scrape events from Sportsbet for the given sport types.
        """
        try:
            # Initialize browser and HTTP session
            await self.initialize()
            
            # If no sport types specified, use all supported sports
            if not sport_types:
                sport_types = list(self.get_sport_paths().keys())
            
            # Collect events from all specified sports
            events = []
            for sport_type in sport_types:
                sport_events = await self.scrape_sport(sport_type)
                events.extend(sport_events)
            
            # Return successful result with all events
            return ScrapingResult(bookmaker=self.bookmaker, events=events, success=True)
        except Exception as e:
            # Log and return error if something goes wrong
            self.logger.error(f"Error scraping {self.bookmaker.name}: {str(e)}")
            return ScrapingResult(
                bookmaker=self.bookmaker,
                events=[],
                success=False,
                error_message=str(e)
            )
        finally:
            # Always clean up resources when done
            await self.cleanup()
    
    async def scrape_sport(self, sport_type: SportType) -> List[Event]:
        """
        Scrape events for a specific sport from Sportsbet.
        """
        events = []
        sport_url = self.get_sport_url(sport_type)
        
        # Navigate to the sport page with reduced timeout
        self.logger.info(f"Navigating to {sport_url}")
        try:
            # Use domcontentloaded instead of networkidle, since our test showed the site loads quickly
            await self.page.goto(sport_url, wait_until="domcontentloaded", timeout=10000)
            
            # Save a debug screenshot
            debug_dir = "debug_screenshots"
            os.makedirs(debug_dir, exist_ok=True)
            screenshot_path = os.path.join(debug_dir, f"sportsbet_{sport_type.name.lower()}.png")
            await self.page.screenshot(path=screenshot_path)
            self.logger.info(f"Screenshot saved to {os.path.abspath(screenshot_path)}")
            
            # Log the page title to help debug
            title = await self.page.title()
            self.logger.info(f"Page title: {title}")
            
            # Let the page finish loading JavaScript content
            await self.page.wait_for_timeout(2000)  # Wait 2 seconds for any JS to run
            
            # For soccer, we need to be more specific since the structure is different
            if sport_type == SportType.SOCCER:
                # Try to find competitions first
                self.logger.info("Looking for soccer competitions...")
                comp_selectors = [
                    ".competition-container", 
                    ".soccer-competition",
                    "[data-automation-id*='competition']",
                    ".competition-markets"
                ]
                
                competitions = []
                for selector in comp_selectors:
                    comps = await self.page.query_selector_all(selector)
                    if comps and len(comps) > 0:
                        self.logger.info(f"Found {len(comps)} soccer competitions with selector: {selector}")
                        competitions = comps
                        break
                
                # If we found competitions, process them to find matches
                if competitions:
                    for i, comp in enumerate(competitions[:5]):  # Limit to 5 competitions for testing
                        try:
                            # Try to get the competition name
                            comp_name = "Unknown Competition"
                            for name_selector in [".competition-name", "h2", ".header"]:
                                name_elem = await comp.query_selector(name_selector)
                                if name_elem:
                                    comp_name_text = await name_elem.text_content()
                                    if comp_name_text and len(comp_name_text.strip()) > 0:
                                        comp_name = comp_name_text.strip()
                                        break
                            
                            self.logger.info(f"Processing competition {i+1}: {comp_name}")
                            
                            # Get all match links within this competition
                            match_links = []
                            link_selectors = ["a", ".match-link", ".event-link", "[data-automation-id*='event'] a"]
                            
                            for link_selector in link_selectors:
                                links = await comp.query_selector_all(link_selector)
                                if links and len(links) > 0:
                                    # Filter for likely match links
                                    for link in links:
                                        href = await link.get_attribute("href")
                                        if href and any(pattern in href for pattern in ["/event/", "/sport/", "/match/", "/soccer/"]):
                                            match_links.append({
                                                "href": href,
                                                "competition": comp_name
                                            })
                            
                            self.logger.info(f"Found {len(match_links)} matches in {comp_name}")
                        except Exception as e:
                            self.logger.warning(f"Error processing competition {i+1}: {str(e)}")
                    
                    # Now process all match links we found
                    for i, match in enumerate(match_links[:10]):  # Limit to 10 matches for testing
                        try:
                            href = match["href"]
                            comp_name = match["competition"]
                            
                            # Make sure we have a full URL
                            if href.startswith("/"):
                                full_url = f"{self.bookmaker.base_url}{href}"
                            else:
                                full_url = href
                            
                            self.logger.info(f"Scraping match {i+1}/{min(10, len(match_links))}: {full_url} (Competition: {comp_name})")
                            
                            # Create a fresh page for each event to avoid context issues
                            event_page = await self.context.new_page()
                            try:
                                event = await self._scrape_event_with_page(event_page, full_url, comp_name)
                                if event:
                                    events.append(event)
                                    # If we've found at least 3 events, we'll stop here for testing purposes
                                    if len(events) >= 3:
                                        self.logger.info("Found 3 events, stopping scraping for testing purposes")
                                        break
                            finally:
                                await event_page.close()
                        except Exception as e:
                            self.logger.warning(f"Error processing match link: {str(e)}")
                else:
                    self.logger.warning("No soccer competitions found, falling back to general approach")
            
            # If we haven't found events or it's not soccer, use general approach
            if len(events) == 0:
                # Define possible event link selectors based on common patterns
                potential_selectors = [
                    ".event-card a",                  # Common event card pattern
                    "[data-automation-id*='event'] a", # Data attribute pattern
                    "a[href*='/event/']",             # URL pattern
                    "a[href*='/sport/']",             # Sport URL pattern
                    ".market-container a",            # Market container pattern
                    "a.event-link"                    # Direct class name
                ]
                
                # Try each selector
                event_links = []
                for selector in potential_selectors:
                    self.logger.info(f"Trying selector: {selector}")
                    links = await self.page.query_selector_all(selector)
                    if links and len(links) > 0:
                        self.logger.info(f"Found {len(links)} links with selector: {selector}")
                        
                        # Store the link URLs and hrefs
                        for link in links:
                            try:
                                href = await link.get_attribute("href")
                                if href:
                                    event_links.append(href)
                            except Exception:
                                pass
                        
                        if event_links:
                            break
                
                # If we didn't find any with our predefined selectors, try a more general approach
                if not event_links:
                    self.logger.info("No event links found with predefined selectors, trying a more general approach")
                    
                    # Get all links
                    all_links = await self.page.query_selector_all("a")
                    self.logger.info(f"Found {len(all_links)} links in total")
                    
                    # Filter links by href pattern suggesting they might be event links
                    for link in all_links:
                        try:
                            href = await link.get_attribute("href")
                            if href and any(pattern in href for pattern in ["/event/", "/sport/", "/match/", "/game/"]):
                                event_links.append(href)
                        except Exception:
                            pass
                    
                    self.logger.info(f"Found {len(event_links)} potential event links by href pattern")
                
                # Process event links
                self.logger.info(f"Processing {len(event_links)} event links")
                for i, href in enumerate(event_links[:10]):  # Limit to 10 events for testing
                    try:
                        # Make sure we have a full URL
                        if href.startswith("/"):
                            full_url = f"{self.bookmaker.base_url}{href}"
                        else:
                            full_url = href
                        
                        self.logger.info(f"Scraping event {i+1}/{min(10, len(event_links))}: {full_url}")
                        
                        # Create a fresh page for each event to avoid context issues
                        event_page = await self.context.new_page()
                        try:
                            event = await self._scrape_event_with_page(event_page, full_url)
                            if event:
                                events.append(event)
                                # If we've found at least 3 events, we'll stop here for testing purposes
                                if len(events) >= 3:
                                    self.logger.info(f"Found {len(events)} events, stopping scraping for testing purposes")
                                    break
                        finally:
                            await event_page.close()
                    except Exception as e:
                        self.logger.warning(f"Error processing event link: {str(e)}")
            
            return events
        except Exception as e:
            self.logger.error(f"Error scraping sport {sport_type.name}: {str(e)}")
            return []
    
    async def _scrape_event_with_page(self, page, event_url: str, competition_override: str = None) -> Optional[Event]:
        """
        Scrape a specific event using a dedicated page to avoid context issues.
        
        Args:
            page: The playwright page to use
            event_url: URL of the event to scrape
            competition_override: Optional competition name to use if found from the parent page
            
        Returns:
            An Event object if successful, None otherwise
        """
        try:
            # Navigate to the event page with reduced timeout
            self.logger.info(f"Navigating to event: {event_url}")
            
            # Use domcontentloaded instead of networkidle and shorter timeout
            await page.goto(event_url, wait_until="domcontentloaded", timeout=10000)
            
            # Take screenshot for debugging
            debug_dir = "debug_screenshots"
            os.makedirs(debug_dir, exist_ok=True)
            event_id = event_url.split("/")[-1]
            screenshot_path = os.path.join(debug_dir, f"sportsbet_event_{event_id}.png")
            await page.screenshot(path=screenshot_path)
            
            # Log the page title
            title = await page.title()
            self.logger.info(f"Event page title: {title}")
            
            # Let the page finish loading JavaScript content
            await page.wait_for_timeout(1000)  # Wait 1 second for any JS to run
            
            # Try various selectors for event name
            event_name = None
            name_selectors = [
                "h1",
                ".event-name",
                ".event-header",
                "[data-automation-id*='event-name']",
                ".event-title",
                ".match-name"
            ]
            
            for selector in name_selectors:
                element = await page.query_selector(selector)
                if element:
                    event_name = await element.text_content()
                    if event_name and len(event_name.strip()) > 0:
                        self.logger.info(f"Found event name with selector {selector}: {event_name}")
                        break
            
            if not event_name:
                self.logger.warning(f"Could not find event name for {event_url}")
                return None
            
            # Parse the event name to get teams
            teams = None
            for separator in [" v ", " vs ", " - ", "vs.", "v."]:
                if separator in event_name:
                    teams = event_name.split(separator)
                    if len(teams) == 2:
                        self.logger.info(f"Split teams using separator: '{separator}'")
                        break
            
            if not teams or len(teams) != 2:
                self.logger.warning(f"Could not parse teams from event name: {event_name}")
                # Use a fallback approach
                home_team = "Home Team"
                away_team = "Away Team"
            else:
                home_team, away_team = teams
            
            # Get competition - use override if provided
            competition = competition_override if competition_override else "Unknown"
            
            # If no override, try to find it on the page
            if not competition_override:
                comp_selectors = [
                    ".competition-name",
                    ".league-name",
                    ".tournament-name",
                    "[data-automation-id*='competition']",
                    ".event-subtitle"
                ]
                
                for selector in comp_selectors:
                    element = await page.query_selector(selector)
                    if element:
                        comp_text = await element.text_content()
                        if comp_text and len(comp_text.strip()) > 0:
                            competition = comp_text.strip()
                            self.logger.info(f"Found competition with selector {selector}: {competition}")
                            break
            
            # Get markets
            markets = []
            
            # Try different market container selectors
            market_container_selectors = [
                ".market-container",
                ".market-group",
                "[data-automation-id*='market']",
                ".betting-market"
            ]
            
            for container_selector in market_container_selectors:
                market_elements = await page.query_selector_all(container_selector)
                if market_elements and len(market_elements) > 0:
                    self.logger.info(f"Found {len(market_elements)} markets with selector: {container_selector}")
                    
                    for i, market_element in enumerate(market_elements):
                        try:
                            # Get market name
                            market_name = "Unknown Market"
                            for name_selector in [".market-name", ".market-header", "h3", "h4"]:
                                name_element = await market_element.query_selector(name_selector)
                                if name_element:
                                    market_name_text = await name_element.text_content()
                                    if market_name_text and len(market_name_text.strip()) > 0:
                                        market_name = market_name_text.strip()
                                        break
                            
                            # Determine market type
                            market_type = self._determine_market_type(market_name)
                            
                            # Get outcomes
                            outcomes = []
                            
                            # Try different selectors for outcomes
                            outcome_selectors = [
                                ".selection",
                                ".outcome",
                                ".market-option",
                                "[data-automation-id*='selection']"
                            ]
                            
                            for outcome_selector in outcome_selectors:
                                outcome_elements = await market_element.query_selector_all(outcome_selector)
                                if outcome_elements and len(outcome_elements) > 0:
                                    self.logger.info(f"Found {len(outcome_elements)} outcomes with selector: {outcome_selector}")
                                    
                                    for outcome_element in outcome_elements:
                                        # Get selection name
                                        selection_name = "Unknown"
                                        for sel_name_selector in [".selection-name", ".outcome-name", ".option-name"]:
                                            name_element = await outcome_element.query_selector(sel_name_selector)
                                            if name_element:
                                                sel_name_text = await name_element.text_content()
                                                if sel_name_text and len(sel_name_text.strip()) > 0:
                                                    selection_name = sel_name_text.strip()
                                                    break
                                        
                                        # Get odds
                                        odds = None
                                        for odds_selector in [".price", ".odds", ".decimal-odds", ".selection-price"]:
                                            odds_element = await outcome_element.query_selector(odds_selector)
                                            if odds_element:
                                                odds_text = await odds_element.text_content()
                                                odds = self.extract_odds(odds_text)
                                                if odds:
                                                    break
                                        
                                        if odds:
                                            outcomes.append(Outcome(name=selection_name, odds=odds))
                                    
                                    # If we found outcomes, we don't need to try other selectors
                                    if outcomes:
                                        break
                            
                            if outcomes:
                                market_id = f"{market_name.lower().replace(' ', '-').replace('/', '-')}"
                                markets.append(Market(
                                    id=market_id,
                                    type=market_type,
                                    name=market_name,
                                    outcomes=outcomes
                                ))
                        except Exception as e:
                            self.logger.warning(f"Error processing market {i+1}: {str(e)}")
                    
                    # If we found markets, we don't need to try other selectors
                    if markets:
                        break
            
            if not markets:
                self.logger.warning(f"No markets found for event: {event_url}")
                return None
            
            # Get the sport type from the URL
            sport_type = self._determine_sport_type(event_url)
            
            # Create a unique ID from the URL
            event_id = event_url.split("/")[-1]
            if not event_id:
                event_id = event_url.split("/")[-2]
            
            # Default start time to now if we can't find it
            start_time = datetime.now()
            
            # Create and return the Event object
            return Event(
                id=event_id,
                sport=sport_type,
                home_team=home_team.strip(),
                away_team=away_team.strip(),
                competition=competition,
                start_time=start_time,
                markets=markets,
                bookmaker=self.bookmaker,
                url=event_url
            )
        except Exception as e:
            self.logger.error(f"Error scraping event {event_url}: {str(e)}")
            return None

    async def scrape_event(self, event_url: str) -> Optional[Event]:
        """
        Scrape a specific event from Sportsbet.
        For compatibility, this creates a new page and delegates to _scrape_event_with_page.
        """
        event_page = await self.context.new_page()
        try:
            return await self._scrape_event_with_page(event_page, event_url)
        finally:
            await event_page.close()
    
    def _determine_market_type(self, market_name: str) -> MarketType:
        """
        Determine the market type from the market name.
        """
        market_name_lower = market_name.lower()
        
        if any(term in market_name_lower for term in ["winner", "win", "head to head", "h2h", "match result"]):
            return MarketType.WIN
        elif any(term in market_name_lower for term in ["handicap", "line", "spread"]):
            return MarketType.HANDICAP
        elif any(term in market_name_lower for term in ["over/under", "total", "o/u"]):
            return MarketType.TOTAL_OVER_UNDER
        elif "correct score" in market_name_lower:
            return MarketType.CORRECT_SCORE
        elif "player" in market_name_lower:
            return MarketType.PLAYER_PROPS
        else:
            return MarketType.OTHER
    
    def _determine_sport_type(self, url: str) -> SportType:
        """
        Determine the sport type from the URL.
        """
        url_lower = url.lower()
        
        if "soccer" in url_lower:
            return SportType.SOCCER
        elif "basketball" in url_lower:
            return SportType.BASKETBALL
        elif "tennis" in url_lower:
            return SportType.TENNIS
        elif "rugby-league" in url_lower:
            return SportType.NRL
        elif "rugby" in url_lower:
            return SportType.RUGBY
        elif "australian-rules" in url_lower:
            return SportType.AFL
        elif "cricket" in url_lower:
            return SportType.CRICKET
        elif "horse-racing" in url_lower:
            return SportType.HORSE_RACING
        elif "esports" in url_lower:
            return SportType.ESPORTS
        else:
            return SportType.OTHER
