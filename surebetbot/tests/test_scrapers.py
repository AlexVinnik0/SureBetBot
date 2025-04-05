import asyncio
import json
import logging
from datetime import datetime
import os

from surebetbot.core.models import Bookmaker, SportType
from surebetbot.scrapers.sportsbet import SportsbetScraper

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("scraper_test")

# Helper function to serialize datetime objects for JSON
def json_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

async def test_sportsbet_scraper():
    """
    Test the Sportsbet scraper by scraping soccer events.
    """
    # Create output directory for results
    os.makedirs("scraper_test_results", exist_ok=True)
    
    # Create a bookmaker instance
    sportsbet = Bookmaker(
        id="sportsbet",
        name="Sportsbet",
        base_url="https://www.sportsbet.com.au",
        logo_url=None,
        commission=0.0,
        min_stake=1.0,
        max_stake=None
    )
    
    logger.info("Creating SportsbetScraper instance")
    
    # Create and initialize the scraper
    scraper = SportsbetScraper(sportsbet)
    
    logger.info("Starting scraping process")
    
    # Scrape a specific sport for testing purposes
    try:
        # Use soccer as it's likely to have events
        sport_type = SportType.SOCCER
        logger.info(f"Scraping {sport_type.name}")
        
        result = await scraper.scrape([sport_type])
        
        # Print scraping success status
        logger.info(f"Scraping successful: {result.success}")
        
        if not result.success:
            logger.error(f"Error: {result.error_message}")
            return
        
        logger.info(f"Found {len(result.events)} events")
        
        # Print the first event as a sample
        if result.events:
            event = result.events[0]
            logger.info("\nSample Event:")
            logger.info(f"- ID: {event.id}")
            logger.info(f"- Teams: {event.home_team} vs {event.away_team}")
            logger.info(f"- Competition: {event.competition}")
            logger.info(f"- Start time: {event.start_time}")
            logger.info(f"- URL: {event.url}")
            logger.info(f"- Markets: {len(event.markets)}")
            
            # Print first market as a sample
            if event.markets:
                market = event.markets[0]
                logger.info("\nSample Market:")
                logger.info(f"- Name: {market.name}")
                logger.info(f"- Type: {market.type}")
                logger.info(f"- Outcomes:")
                for outcome in market.outcomes:
                    logger.info(f"  * {outcome.name}: {outcome.odds}")
        
        # Save all results to a JSON file for detailed inspection
        output_file = "scraper_test_results/sportsbet_scrape_results.json"
        with open(output_file, 'w') as f:
            json.dump({
                'bookmaker': sportsbet.name,
                'timestamp': datetime.now().isoformat(),
                'events': [
                    {
                        'id': event.id,
                        'home_team': event.home_team,
                        'away_team': event.away_team,
                        'competition': event.competition,
                        'start_time': event.start_time.isoformat(),
                        'url': event.url,
                        'markets': [
                            {
                                'name': market.name,
                                'type': market.type.name,
                                'outcomes': [
                                    {'name': outcome.name, 'odds': outcome.odds}
                                    for outcome in market.outcomes
                                ]
                            }
                            for market in event.markets
                        ]
                    }
                    for event in result.events
                ]
            }, f, indent=2, default=json_serializer)
        
        logger.info(f"\nDetailed results saved to {output_file}")
        
    except Exception as e:
        logger.exception(f"Error in test_sportsbet_scraper: {str(e)}")
    finally:
        # Ensure cleanup happens
        await scraper.cleanup()

if __name__ == "__main__":
    logger.info("Starting scraper test")
    asyncio.run(test_sportsbet_scraper())
    logger.info("Scraper test completed")
