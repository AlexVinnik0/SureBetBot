#!/usr/bin/env python
"""
Command-line tool to run the Sportsbet scraper and display results.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List

from surebetbot.core.models import Event, SportType
from surebetbot.scrapers.sportsbet_scraper import SportsbetScraper

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("sportsbet_scraper_cmd")


def format_event(event: Event) -> str:
    """
    Format an event for display.
    
    Args:
        event: The event to format
        
    Returns:
        Formatted event string
    """
    lines = []
    
    lines.append(f"\n{'=' * 80}")
    lines.append(f"EVENT: {event.home_team} vs {event.away_team}")
    lines.append(f"{'=' * 80}")
    
    lines.append(f"Competition: {event.competition_name}")
    lines.append(f"Start time: {event.start_time}")
    lines.append(f"URL: {event.url}")
    lines.append("")
    
    for i, market in enumerate(event.markets):
        lines.append(f"MARKET #{i+1}: {market.name}")
        lines.append(f"{'-' * 60}")
        
        for outcome in market.outcomes:
            lines.append(f"  {outcome.name}: {outcome.odds:.2f}")
        
        lines.append("")
    
    return "\n".join(lines)


def save_events(events: List[Event], output_dir: str) -> str:
    """
    Save events to a JSON file.
    
    Args:
        events: List of events to save
        output_dir: Directory to save to
        
    Returns:
        Path to the saved file
    """
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sportsbet_events_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, "w") as f:
        json.dump(
            [event.dict() for event in events],
            f,
            indent=2,
            default=str,
        )
    
    return filepath


async def main():
    """Run the main application."""
    logger.info("Starting Sportsbet scraper")
    
    # Initialize the scraper
    scraper = SportsbetScraper()
    await scraper.initialize()
    
    try:
        # Scrape soccer events
        logger.info("Scraping soccer events")
        events = await scraper.scrape_sport(SportType.SOCCER)
        
        # Display events
        if events:
            logger.info(f"Found {len(events)} soccer events")
            
            # Print formatted events
            for event in events:
                print(format_event(event))
            
            # Save events to file
            output_file = save_events(events, "output")
            logger.info(f"Events saved to {output_file}")
        else:
            logger.warning("No events found")
    
    finally:
        # Close the scraper
        await scraper.close()
    
    logger.info("Sportsbet scraper completed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.exception(f"An error occurred: {e}")
        sys.exit(1) 