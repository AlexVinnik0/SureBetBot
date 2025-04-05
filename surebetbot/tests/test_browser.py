import asyncio
import os

from playwright.async_api import async_playwright

async def test_browser():
    """
    Test if bookmaker websites are accessible and check for geo-blocking.
    """
    print("Starting browser test for bookmaker websites...")
    
    # Create directory for screenshots
    debug_dir = "debug_navigation"
    os.makedirs(debug_dir, exist_ok=True)
    
    # List of bookmakers to test
    bookmakers = [
        {
            "name": "Sportsbet", 
            "base_url": "https://www.sportsbet.com.au", 
            "soccer_paths": ["/soccer", "/sports/soccer", "/sport/soccer"]
        },
        {
            "name": "Ladbrokes", 
            "base_url": "https://www.ladbrokes.com.au", 
            "soccer_paths": ["/sports/soccer", "/soccer"]
        },
        {
            "name": "Neds", 
            "base_url": "https://www.neds.com.au", 
            "soccer_paths": ["/sports/soccer", "/soccer"]
        },
        {
            "name": "TAB", 
            "base_url": "https://www.tab.com.au", 
            "soccer_paths": ["/sports/soccer", "/soccer"]
        },
        {
            "name": "Unibet", 
            "base_url": "https://www.unibet.com.au", 
            "soccer_paths": ["/betting/sports/soccer", "/sports/soccer"]
        }
    ]
    
    async with async_playwright() as p:
        # Try with different browser types
        for browser_type_name, browser_type in [
            ("Chromium", p.chromium), 
            ("Firefox", p.firefox),
            ("Webkit", p.webkit)
        ]:
            print(f"\nTesting with {browser_type_name} browser")
            
            # Launch browser
            browser = await browser_type.launch(headless=True)
            
            # Test each bookmaker
            for bookmaker in bookmakers:
                name = bookmaker["name"]
                base_url = bookmaker["base_url"]
                
                print(f"\nTesting {name} ({base_url}):")
                
                # Create a new page
                page = await browser.new_page()
                
                # Try to access main page
                try:
                    print(f"  Accessing main page...")
                    
                    # Set a longer timeout for main page
                    await page.goto(base_url, timeout=20000)
                    
                    # Take screenshot
                    screenshot_path = os.path.join(debug_dir, f"{name.lower()}_{browser_type_name.lower()}_main.png")
                    await page.screenshot(path=screenshot_path)
                    print(f"  Screenshot saved to {os.path.abspath(screenshot_path)}")
                    
                    # Get page title
                    title = await page.title()
                    print(f"  Page title: {title}")
                    
                    # Check for geo-blocking or access issues by looking for common keywords
                    page_content = await page.content()
                    page_text = await page.evaluate('() => document.body.innerText')
                    
                    is_blocked = False
                    blocking_keywords = [
                        "access denied", "geo-restricted", "not available", 
                        "restricted", "not accessible", "blocked",
                        "sorry, we cannot accept", "unavailable in your region"
                    ]
                    
                    for keyword in blocking_keywords:
                        if keyword in page_content.lower() or keyword in page_text.lower():
                            print(f"  WARNING: Detected possible geo-blocking: '{keyword}'")
                            is_blocked = True
                    
                    if not is_blocked:
                        print("  Main page loaded successfully!")
                        
                        # Try the soccer paths
                        for path in bookmaker["soccer_paths"]:
                            soccer_url = f"{base_url}{path}"
                            
                            try:
                                print(f"\n  Trying soccer path: {path}")
                                
                                # Create a new page for this path
                                soccer_page = await browser.new_page()
                                
                                # Navigate to the soccer page
                                await soccer_page.goto(soccer_url, timeout=15000)
                                
                                # Take screenshot
                                screenshot_path = os.path.join(
                                    debug_dir, 
                                    f"{name.lower()}_{browser_type_name.lower()}_soccer_{path.replace('/', '_')}.png"
                                )
                                await soccer_page.screenshot(path=screenshot_path)
                                
                                # Get page title
                                title = await soccer_page.title()
                                print(f"    Soccer page title: {title}")
                                
                                # Check if we successfully reached a soccer page
                                if "soccer" in title.lower() or "football" in title.lower():
                                    print("    SUCCESS: This appears to be a soccer page!")
                                    
                                    # Try to find events or matches
                                    for selector in [
                                        ".event-card", 
                                        ".match", 
                                        "[data-automation-id*='event']",
                                        ".competition-container"
                                    ]:
                                        elements = await soccer_page.query_selector_all(selector)
                                        if elements and len(elements) > 0:
                                            print(f"    Found {len(elements)} potential matches with selector: {selector}")
                                            break
                                    
                                    # Get common link patterns
                                    print("    Analyzing links on soccer page:")
                                    links = await soccer_page.query_selector_all("a")
                                    
                                    match_links = []
                                    for link in links[:20]:  # Only check first 20 links
                                        try:
                                            href = await link.get_attribute("href") or ""
                                            text = await link.text_content() or ""
                                            
                                            if href and ("match" in href or "event" in href or "game" in href):
                                                match_links.append({"href": href, "text": text})
                                        except Exception:
                                            pass
                                    
                                    if match_links:
                                        print(f"    Found {len(match_links)} potential match links")
                                        for i, link in enumerate(match_links[:3]):  # Show first 3
                                            print(f"    - Match {i+1}: {link['text']} -> {link['href']}")
                                    else:
                                        print("    No match links found on this page")
                                else:
                                    page_text = await soccer_page.evaluate('() => document.body.innerText')
                                    print(f"    This doesn't appear to be a soccer page: {page_text[:100]}...")
                                
                                # Close soccer page
                                await soccer_page.close()
                            except Exception as e:
                                print(f"    Error accessing soccer path {path}: {str(e)}")
                                try:
                                    await soccer_page.close()
                                except Exception:
                                    pass
                
                except Exception as e:
                    print(f"  Error accessing {name}: {str(e)}")
                
                # Close main page
                await page.close()
            
            # Close browser
            await browser.close()
    
    print("\nBrowser test completed")

if __name__ == "__main__":
    asyncio.run(test_browser()) 