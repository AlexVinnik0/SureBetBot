#!/usr/bin/env python
"""
Command-line tool to run the Sportsbet horse racing scraper.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime

from surebetbot.core.models import SportType
from surebetbot.scrapers.sportsbet_horse_racing import SportsbetHorseRacingScraper

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("sportsbet_horse_racing_cmd")


def save_events_to_json(events, output_dir="output"):
    """Save events to a JSON file for later analysis."""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sportsbet_horse_racing_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    # Create serializable dictionaries from the Event objects
    events_data = []
    for event in events:
        markets_data = []
        for market in event.markets:
            outcomes_data = []
            for outcome in market.outcomes:
                outcomes_data.append({
                    "name": outcome.name,
                    "odds": outcome.odds
                })
            
            markets_data.append({
                "id": market.id,
                "name": market.name,
                "type": market.type.name,
                "outcomes": outcomes_data
            })
        
        events_data.append({
            "id": event.id,
            "sport": event.sport.name,
            "home_team": event.home_team,
            "away_team": event.away_team,
            "competition": event.competition,
            "start_time": str(event.start_time),
            "url": event.url,
            "markets": markets_data
        })
    
    with open(filepath, "w") as f:
        json.dump(events_data, f, indent=2)
    
    logger.info(f"Saved {len(events)} events to {filepath}")
    return filepath


async def main():
    """Run the main application."""
    logger.info("Starting Sportsbet horse racing scraper")
    
    # Initialize the specialized horse racing scraper
    scraper = SportsbetHorseRacingScraper()
    
    try:
        # Initialize the browser
        await scraper.initialize()
        
        # Scrape horse racing events
        logger.info("Scraping horse racing events")
        result = await scraper.scrape()
        events = result.events
        
        # Display and save results
        if events:
            logger.info(f"Found {len(events)} horse racing events")
            
            # Display summary of each event
            for i, event in enumerate(events):
                logger.info(f"Event {i+1}: {event.home_team} - {len(event.markets)} markets")
                
                # Display markets and odds
                for market in event.markets:
                    logger.info(f"  Market: {market.name} ({market.type.name}) - {len(market.outcomes)} outcomes")
                    
                    # Display a few outcomes as examples
                    for j, outcome in enumerate(market.outcomes[:3]):  # Show only first 3 for brevity
                        logger.info(f"    {outcome.name}: {outcome.odds}")
                    
                    if len(market.outcomes) > 3:
                        logger.info(f"    ... and {len(market.outcomes) - 3} more outcomes")
            
            # Save events to file
            save_events_to_json(events)
        else:
            logger.warning("No horse racing events found")
    
    except Exception as e:
        logger.error(f"Error scraping horse racing events: {str(e)}")
    
    finally:
        # Close the scraper
        await scraper.cleanup()
    
    logger.info("Sportsbet horse racing scraper completed")


if __name__ == "__main__":
    asyncio.run(main()) 