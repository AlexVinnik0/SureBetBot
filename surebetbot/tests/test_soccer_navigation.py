import asyncio
import os
import logging
from datetime import datetime

from playwright.async_api import async_playwright

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("soccer_nav_test")

async def test_soccer_navigation():
    """
    Test specifically navigating to Soccer via Sports menu to handle the pattern Sports > Soccer.
    """
    logger.info("Starting soccer navigation test for bookmaker websites...")
    
    # Create directory for screenshots
    debug_dir = "debug_soccer_nav"
    os.makedirs(debug_dir, exist_ok=True)
    
    # List of bookmakers to test
    bookmakers = [
        {
            "name": "Sportsbet", 
            "base_url": "https://www.sportsbet.com.au",
            "sports_menu_selectors": [
                ".sports-menu", 
                ".main-nav",
                "nav",
                "[data-automation-id*='sports']"
            ],
            "soccer_link_selectors": [
                "a[href*='/soccer']",
                "a[href*='/sports/soccer']",
                "a:has-text('Soccer')",
                "a:has-text('Football')"
            ]
        },
        {
            "name": "TAB", 
            "base_url": "https://www.tab.com.au",
            "sports_menu_selectors": [
                ".sports-navigation", 
                "nav",
                ".main-menu",
                ".menu-container"
            ],
            "soccer_link_selectors": [
                "a[href*='/soccer']",
                "a[href*='/sports/soccer']",
                "a:has-text('Soccer')",
                "a:has-text('Football')"
            ]
        },
        {
            "name": "Ladbrokes", 
            "base_url": "https://www.ladbrokes.com.au",
            "sports_menu_selectors": [
                ".sports-menu", 
                "nav",
                ".main-nav",
                ".sports-navigation"
            ],
            "soccer_link_selectors": [
                "a[href*='/soccer']",
                "a[href*='/sports/soccer']",
                "a:has-text('Soccer')",
                "a:has-text('Football')"
            ]
        }
    ]
    
    async with async_playwright() as p:
        # Try with Firefox first as it seemed to work better in previous tests
        browser_type = p.firefox
        
        logger.info("Testing with Firefox browser")
        
        # Launch browser
        browser = await browser_type.launch(headless=False)  # Use headless=False to see browser UI
        
        # Test each bookmaker
        for bookmaker in bookmakers:
            name = bookmaker["name"]
            base_url = bookmaker["base_url"]
            
            logger.info(f"\nTesting {name} ({base_url}):")
            
            # Create a new context with a longer timeout
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            context.set_default_timeout(30000)  # 30 seconds
            
            # Create a new page
            page = await context.new_page()
            
            try:
                logger.info(f"Accessing main page...")
                
                # Navigate to the main page
                await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
                
                # Take screenshot of the main page
                screenshot_path = os.path.join(debug_dir, f"{name.lower()}_main.png")
                await page.screenshot(path=screenshot_path)
                logger.info(f"Main page screenshot saved to {screenshot_path}")
                
                # Get page title
                title = await page.title()
                logger.info(f"Main page title: {title}")
                
                # Wait for page to stabilize
                await page.wait_for_timeout(3000)
                
                # Check for cookie consent or overlays that might block navigation
                for consent_selector in [
                    "button:has-text('Accept')", 
                    "button:has-text('Agree')",
                    "button:has-text('Accept All')",
                    "[aria-label='Accept cookies']",
                    ".cookie-consent button"
                ]:
                    try:
                        if await page.locator(consent_selector).count() > 0:
                            logger.info(f"Accepting cookies with selector: {consent_selector}")
                            await page.click(consent_selector)
                            await page.wait_for_timeout(1000)
                            break
                    except Exception:
                        pass
                
                # Step 1: Find and click on Sports in the navigation
                found_sports_menu = False
                for menu_selector in bookmaker["sports_menu_selectors"]:
                    try:
                        logger.info(f"Looking for sports menu with selector: {menu_selector}")
                        if await page.locator(menu_selector).count() > 0:
                            logger.info(f"Found sports menu with selector: {menu_selector}")
                            
                            # Take screenshot of sports menu
                            screenshot_path = os.path.join(debug_dir, f"{name.lower()}_sports_menu.png")
                            await page.screenshot(path=screenshot_path)
                            
                            found_sports_menu = True
                            
                            # Try to find a direct link to sports or specifically to soccer
                            found_soccer = False
                            for soccer_selector in bookmaker["soccer_link_selectors"]:
                                try:
                                    logger.info(f"Looking for soccer link with selector: {soccer_selector}")
                                    soccer_links = await page.locator(soccer_selector).all()
                                    
                                    if soccer_links:
                                        logger.info(f"Found {len(soccer_links)} soccer links with selector: {soccer_selector}")
                                        
                                        # Click the first soccer link
                                        await soccer_links[0].click()
                                        logger.info("Clicked on soccer link")
                                        
                                        # Wait for navigation to complete
                                        await page.wait_for_timeout(5000)
                                        
                                        # Take screenshot of soccer page
                                        screenshot_path = os.path.join(debug_dir, f"{name.lower()}_soccer.png")
                                        await page.screenshot(path=screenshot_path)
                                        
                                        # Get page title
                                        soccer_title = await page.title()
                                        logger.info(f"Soccer page title: {soccer_title}")
                                        
                                        if "soccer" in soccer_title.lower() or "football" in soccer_title.lower():
                                            logger.info("Successfully navigated to Soccer page!")
                                        else:
                                            logger.info(f"Navigation successful but title doesn't contain soccer/football: {soccer_title}")
                                        
                                        # Check for competitions and matches
                                        for comp_selector in [
                                            ".competition-container", 
                                            ".match-container",
                                            "[data-automation-id*='competition']",
                                            "[data-automation-id*='event']",
                                            ".event-card"
                                        ]:
                                            competitions = await page.locator(comp_selector).all()
                                            if competitions:
                                                logger.info(f"Found {len(competitions)} competitions/matches with selector: {comp_selector}")
                                        
                                        # Count all links on the page with "match" or "event" in href
                                        match_links = await page.locator("a[href*='match'], a[href*='event']").all()
                                        logger.info(f"Found {len(match_links)} potential match links on soccer page")
                                        
                                        found_soccer = True
                                        break
                                except Exception as e:
                                    logger.warning(f"Error clicking soccer link: {str(e)}")
                            
                            if not found_soccer:
                                logger.warning("Could not find or click on soccer link")
                            
                            break
                    except Exception as e:
                        logger.warning(f"Error with sports menu selector {menu_selector}: {str(e)}")
                
                if not found_sports_menu:
                    logger.warning("Could not find sports menu")
                    
                    # Alternative approach: try to directly navigate to /soccer or /sports/soccer
                    logger.info("Trying direct navigation to soccer page")
                    for soccer_path in ["/soccer", "/sports/soccer", "/sport/soccer"]:
                        try:
                            soccer_url = f"{base_url}{soccer_path}"
                            logger.info(f"Navigating to: {soccer_url}")
                            
                            await page.goto(soccer_url, wait_until="domcontentloaded", timeout=20000)
                            
                            # Take screenshot of direct navigation
                            screenshot_path = os.path.join(debug_dir, f"{name.lower()}_direct_soccer.png")
                            await page.screenshot(path=screenshot_path)
                            
                            # Get page title
                            direct_title = await page.title()
                            logger.info(f"Direct soccer navigation title: {direct_title}")
                            
                            if "soccer" in direct_title.lower() or "football" in direct_title.lower():
                                logger.info("Successfully navigated directly to Soccer page!")
                                break
                        except Exception as e:
                            logger.warning(f"Error with direct navigation to {soccer_path}: {str(e)}")
            
            except Exception as e:
                logger.error(f"Error testing {name}: {str(e)}")
            
            finally:
                # Close context
                await context.close()
        
        # Close browser
        await browser.close()
    
    logger.info("Soccer navigation test completed")

if __name__ == "__main__":
    asyncio.run(test_soccer_navigation()) 