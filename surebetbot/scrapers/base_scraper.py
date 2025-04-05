from abc import ABC, abstractmethod
from datetime import datetime
import logging
from typing import Dict, List, Optional, Union

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from surebetbot.core.models import Bookmaker, Event, ScrapingResult, SportType


class BaseScraper(ABC):
    """
    Base abstract class for all bookmaker scrapers.
    Defines the common interface and utility methods that all scrapers should implement.
    """
    
    def __init__(self, bookmaker: Bookmaker):
        """
        Initialize the scraper with a bookmaker.
        
        Args:
            bookmaker: The bookmaker this scraper is for
        """
        self.bookmaker = bookmaker
        self.logger = logging.getLogger(f"scraper.{bookmaker.name.lower()}")
        self.session = None
        self.browser = None
        self.context = None
        self.page = None
    
    async def initialize(self) -> None:
        """
        Initialize resources needed for scraping.
        """
        self.session = aiohttp.ClientSession()
        
        # Set up playwright if needed
        if self.uses_browser():
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36"
            )
            self.page = await self.context.new_page()
    
    async def cleanup(self) -> None:
        """
        Clean up resources after scraping.
        """
        if self.session and not self.session.closed:
            await self.session.close()
        
        if self.page:
            await self.page.close()
        
        if self.context:
            await self.context.close()
        
        if self.browser:
            await self.browser.close()
    
    def uses_browser(self) -> bool:
        """
        Whether this scraper uses a browser for scraping.
        Override in subclasses if needed.
        
        Returns:
            True if the scraper uses a browser, False if it uses direct HTTP requests
        """
        return False
    
    @abstractmethod
    async def scrape(self, sport_types: Optional[List[SportType]] = None) -> ScrapingResult:
        """
        Scrape the bookmaker website for events and their odds.
        
        Args:
            sport_types: Optional list of sport types to scrape for. If None, scrape all available sports.
            
        Returns:
            A ScrapingResult containing the scraped events and metadata
        """
        pass
    
    @abstractmethod
    async def scrape_sport(self, sport_type: SportType) -> List[Event]:
        """
        Scrape events for a specific sport.
        
        Args:
            sport_type: The sport type to scrape
            
        Returns:
            A list of events for the specified sport
        """
        pass
    
    @abstractmethod
    async def scrape_event(self, event_url: str) -> Optional[Event]:
        """
        Scrape details for a specific event.
        
        Args:
            event_url: URL of the event to scrape
            
        Returns:
            An Event object if successful, None otherwise
        """
        pass
    
    async def make_request(self, url: str, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
        """
        Make an HTTP request to the specified URL.
        
        Args:
            url: The URL to request
            headers: Optional headers to include in the request
            
        Returns:
            The response text if successful, None otherwise
        """
        if not headers:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36"
            }
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.text()
                self.logger.warning(f"Request to {url} failed with status {response.status}")
                return None
        except Exception as e:
            self.logger.error(f"Error making request to {url}: {str(e)}")
            return None
    
    def parse_html(self, html: str) -> BeautifulSoup:
        """
        Parse HTML into a BeautifulSoup object.
        
        Args:
            html: HTML text to parse
            
        Returns:
            A BeautifulSoup object
        """
        return BeautifulSoup(html, "html.parser")
    
    def get_sport_url(self, sport_type: SportType) -> str:
        """
        Get the URL for a specific sport.
        
        Args:
            sport_type: The sport type
            
        Returns:
            The URL for the sport
        """
        sport_paths = self.get_sport_paths()
        return f"{self.bookmaker.base_url}{sport_paths.get(sport_type, '')}"
    
    @abstractmethod
    def get_sport_paths(self) -> Dict[SportType, str]:
        """
        Get the path part of URLs for each sport type.
        
        Returns:
            A dictionary mapping sport types to URL paths
        """
        pass
    
    def normalize_team_name(self, name: str) -> str:
        """
        Normalize a team name to ensure consistent matching across bookmakers.
        
        Args:
            name: The team name to normalize
            
        Returns:
            Normalized team name
        """
        return name.strip().lower().replace(" fc", "").replace("fc ", "")
    
    def extract_odds(self, text: str) -> Optional[float]:
        """
        Extract odds from text, handling different formats.
        
        Args:
            text: Text containing odds
            
        Returns:
            Odds as a float if successful, None otherwise
        """
        try:
            # Remove any non-digit characters except for decimal point
            clean_text = ''.join(c for c in text if c.isdigit() or c == '.')
            return float(clean_text)
        except (ValueError, TypeError):
            self.logger.warning(f"Failed to extract odds from text: {text}")
            return None