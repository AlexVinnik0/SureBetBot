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
    
    # Format the event header differently based on sport type
    if event.sport == SportType.HORSE_RACING:
        lines.append(f"EVENT: {event.home_team} ({event.competition})")
    else:
        if event.away_team:
            lines.append(f"EVENT: {event.home_team} vs {event.away_team}")
        else:
            lines.append(f"EVENT: {event.home_team}")
    
    lines.append(f"{'=' * 80}")
    
    lines.append(f"Sport: {event.sport.name}")
    lines.append(f"Competition: {event.competition}")
    lines.append(f"Start time: {event.start_time}")
    lines.append(f"URL: {event.url}")
    lines.append("")
    
    for i, market in enumerate(event.markets):
        lines.append(f"MARKET #{i+1}: {market.name} (Type: {market.type.name})")
        lines.append(f"{'-' * 60}")
        
        for j, outcome in enumerate(market.outcomes):
            outcome_name = outcome.name
            # If the outcome name is the same as the odds, use a better name
            if outcome_name == str(outcome.odds):
                if event.sport == SportType.HORSE_RACING:
                    outcome_name = f"Runner {j+1}"
                else:
                    outcome_name = f"Selection {j+1}"
            lines.append(f"  {outcome_name}: {outcome.odds:.2f}")
        
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
    
    # Convert Event objects to dictionaries
    events_data = []
    for event in events:
        # Create a dictionary representation of the event
        event_dict = {
            "id": event.id,
            "sport": event.sport.name,
            "home_team": event.home_team,
            "away_team": event.away_team,
            "competition": event.competition,
            "start_time": str(event.start_time),
            "url": event.url,
            "bookmaker": {
                "id": event.bookmaker.id,
                "name": event.bookmaker.name,
                "base_url": event.bookmaker.base_url
            },
            "markets": []
        }
        
        # Add markets data
        for market in event.markets:
            market_dict = {
                "id": market.id,
                "name": market.name,
                "type": market.type.name,
                "outcomes": []
            }
            
            # Add outcomes data
            for outcome in market.outcomes:
                market_dict["outcomes"].append({
                    "name": outcome.name,
                    "odds": outcome.odds
                })
            
            event_dict["markets"].append(market_dict)
        
        events_data.append(event_dict)
    
    with open(filepath, "w") as f:
        json.dump(
            events_data,
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
        await scraper.cleanup()
    
    logger.info("Sportsbet scraper completed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.exception(f"An error occurred: {e}")
        sys.exit(1) 