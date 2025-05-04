import asyncio
import json
import os
import re
from playwright.async_api import async_playwright, TimeoutError

async def extract_token_links_directly():
    """
    Opens the Sonefi memeLaunch page in headless browser and extracts token links directly 
    from the DOM using various methods to identify token elements.
    """
    print("Starting Playwright in headless mode...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        
        page = await context.new_page()
        
        # Create directory for data if it doesn't exist
        os.makedirs("data", exist_ok=True)
        
        print("Navigating to https://sonefi.xyz/#/memeLaunch")
        await page.goto("https://sonefi.xyz/#/memeLaunch", wait_until="domcontentloaded", timeout=60000)
        print("Initial page load complete")
        
        # Wait a bit for JavaScript to run
        await asyncio.sleep(5)
        
        # Take screenshot of initial state
        await page.screenshot(path="initial_state.png")
        print("Saved screenshot of initial state to initial_state.png")
        
        # Save the HTML for analysis
        html_content = await page.content()
        with open("data/page_html.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("Saved page HTML to data/page_html.html for inspection")
        
        # Scroll to load all tokens
        print("Scrolling to load all content...")
        for i in range(5):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            print(f"Scroll {i+1}/5 completed")
        
        # Take screenshot after scrolling
        await page.screenshot(path="after_scrolling.png")
        print("Saved screenshot after scrolling to after_scrolling.png")
        
        # First, analyze the page to find potential token elements using multiple selectors
        # Fix: Escape quotes within the JavaScript string
        potential_selectors = [
            '.market-list-item-new',
            'div[class*="market"]',
            'div[class*="item"]', 
            'div[class*="card"]',
            'div[class*="token"]',
            'div[class*="list-item"]',
            'div[role="button"]',
            'a[href*="/token/"]',
            'a[href*="/erc20token/"]'
        ]
        
        selector_counts = {}
        for selector in potential_selectors:
            # Fix: Properly escape the selector for JavaScript
            escaped_selector = selector.replace('"', '\\"')
            count = await page.evaluate(f'() => document.querySelectorAll("{escaped_selector}").length')
            selector_counts[selector] = count
            print(f"Selector '{selector}' matched {count} elements")
        
        # Identify the most promising selectors
        promising_selectors = [s for s, count in selector_counts.items() if count > 0]
        print(f"Promising selectors: {promising_selectors}")
        
        # Extract all elements with hex addresses in them
        elements_with_addresses = await page.evaluate('''
            () => {
                const result = [];
                const hexPattern = /0x[a-fA-F0-9]{40}/g;
                
                // Find all elements that might contain token addresses
                const allElements = document.querySelectorAll('*');
                for (const element of allElements) {
                    try {
                        // Check element text content
                        const text = element.textContent;
                        if (!text) continue;
                        const matches = text.match(hexPattern);
                        
                        if (matches) {
                            // Check if this is likely a token card/item
                            const isCard = element.className && element.className.includes && 
                                          (element.className.includes('card') || 
                                          element.className.includes('item') ||
                                          element.className.includes('token')) ||
                                          element.tagName === 'A' ||
                                          element.getAttribute('role') === 'button';
                            
                            if (isCard) {
                                result.push({
                                    address: matches[0],
                                    text: text.substring(0, 100),
                                    tagName: element.tagName,
                                    className: element.className,
                                    id: element.id,
                                    href: element.getAttribute('href'),
                                    isClickable: element.onclick != null || 
                                               element.tagName === 'A' || 
                                               element.getAttribute('role') === 'button'
                                });
                            }
                        }
                        
                        // Check for href attributes containing token addresses
                        const href = element.getAttribute('href');
                        if (href && (href.includes('/token/') || href.includes('/erc20token/'))) {
                            const parts = href.split('/');
                            const lastPart = parts[parts.length - 1];
                            if (lastPart.match(/^0x[a-fA-F0-9]{40}$/)) {
                                result.push({
                                    address: lastPart,
                                    text: element.textContent ? element.textContent.substring(0, 100) : '',
                                    tagName: element.tagName,
                                    className: element.className,
                                    id: element.id,
                                    href: href,
                                    isClickable: true
                                });
                            }
                        }
                        
                        // Check for data attributes containing token addresses
                        if (element.attributes) {
                            for (const attr of element.attributes) {
                                if (attr.name && attr.name.startsWith('data-') && 
                                    attr.value && attr.value.match(/^0x[a-fA-F0-9]{40}$/)) {
                                    result.push({
                                        address: attr.value,
                                        text: element.textContent ? element.textContent.substring(0, 100) : '',
                                        tagName: element.tagName,
                                        className: element.className,
                                        id: element.id,
                                        attrName: attr.name,
                                        href: element.getAttribute('href'),
                                        isClickable: element.onclick != null || 
                                                   element.tagName === 'A' || 
                                                   element.getAttribute('role') === 'button'
                                    });
                                }
                            }
                        }
                    } catch (error) {
                        console.error("Error processing element:", error);
                    }
                }
                
                // Remove duplicates based on address
                const uniqueAddresses = new Set();
                return result.filter(item => {
                    if (uniqueAddresses.has(item.address)) {
                        return false;
                    }
                    uniqueAddresses.add(item.address);
                    return true;
                });
            }
        ''')
        
        print(f"Found {len(elements_with_addresses)} elements containing token addresses")
        
        # Save the elements with addresses to a JSON file
        with open("data/elements_with_addresses.json", "w") as f:
            json.dump(elements_with_addresses, f, indent=2)
        print("Saved elements with addresses to data/elements_with_addresses.json")
        
        # Extract token URLs from the elements with addresses
        token_links = []
        for element in elements_with_addresses:
            address = element.get('address')
            if address:
                # Construct token URL from address
                token_url = f"https://sonefi.xyz/#/erc20token/{address}"
                if token_url not in token_links:
                    token_links.append(token_url)
        
        # If we didn't find any token links, try a more aggressive approach
        if not token_links:
            print("No token links found using primary method, trying alternative approach...")
            
            # Look for any clickable elements and capture their HTML
            clickable_elements = await page.evaluate('''
                () => {
                    const result = [];
                    try {
                        // Find all potentially clickable elements
                        const elements = Array.from(document.querySelectorAll('a, [onclick], [role="button"], div[class*="item"], div[class*="card"]'));
                        elements.forEach(el => {
                            try {
                                const outerHTML = el.outerHTML || '';
                                const innerHTML = el.innerHTML || '';
                                const textContent = el.textContent ? el.textContent.trim() : '';
                                
                                result.push({
                                    outerHTML: outerHTML.substring(0, 200) + (outerHTML.length > 200 ? '...' : ''),
                                    innerHTML: innerHTML.substring(0, 100) + (innerHTML.length > 100 ? '...' : ''),
                                    textContent: textContent.substring(0, 100) + (textContent.length > 100 ? '...' : ''),
                                    tagName: el.tagName,
                                    className: el.className,
                                    id: el.id,
                                    href: el.getAttribute('href'),
                                    style: el.getAttribute('style'),
                                    hasChildren: el.children ? el.children.length > 0 : false
                                });
                            } catch (innerError) {
                                console.error("Error processing element:", innerError);
                            }
                        });
                    } catch (error) {
                        console.error("Error in clickable elements extraction:", error);
                    }
                    return result;
                }
            ''')
            
            print(f"Found {len(clickable_elements)} potentially clickable elements")
            with open("data/clickable_elements.json", "w") as f:
                json.dump(clickable_elements, f, indent=2, default=str)
            
            # Try to extract addresses from the clickable elements
            hex_pattern = r'0x[a-fA-F0-9]{40}'
            
            for element in clickable_elements:
                html = element.get('outerHTML', '')
                matches = re.findall(hex_pattern, html)
                for match in matches:
                    token_url = f"https://sonefi.xyz/#/erc20token/{match}"
                    if token_url not in token_links:
                        token_links.append(token_url)
        
        # Save just the token URLs
        with open("data/token_links.json", "w") as f:
            json.dump(token_links, f, indent=2)
        print(f"Saved {len(token_links)} token links to data/token_links.json")
        
        # Take a screenshot of the final state
        await page.screenshot(path="extraction_complete.png")
        print("Final screenshot saved as extraction_complete.png")
        
        # Try a basic check - find any links on the page
        all_links = await page.evaluate('''
            () => {
                const links = [];
                try {
                    const anchors = document.querySelectorAll('a');
                    for (const anchor of anchors) {
                        if (anchor.href) {
                            links.push({
                                href: anchor.href,
                                text: anchor.textContent ? anchor.textContent.trim().substring(0, 50) : ''
                            });
                        }
                    }
                } catch (error) {
                    console.error("Error extracting links:", error);
                }
                return links;
            }
        ''')
        
        print(f"Found {len(all_links)} anchor tags on the page")
        with open("data/all_page_links.json", "w") as f:
            json.dump(all_links, f, indent=2)
        print("Saved all page links to data/all_page_links.json")
        
        await browser.close()
        print("Browser closed")
        
        return token_links

async def extract_token_links_by_clicking():
    """
    Opens the Sonefi memeLaunch page in headless browser and extracts token links by 
    clicking on each token element and capturing the resulting URL.
    """
    print("Starting Playwright in headless mode...")
    async with async_playwright() as p:
        # Launch a new browser with increased timeout
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        
        # Create a new page with increased timeout
        page = await context.new_page()
        page.set_default_navigation_timeout(60000)
        page.set_default_timeout(60000)
        
        # Create directory for data if it doesn't exist
        os.makedirs("data", exist_ok=True)
        
        print("Navigating to https://sonefi.xyz/#/memeLaunch")
        await page.goto("https://sonefi.xyz/#/memeLaunch", wait_until="domcontentloaded", timeout=60000)
        print("Initial page load complete")
        
        # Wait for JavaScript to run
        await asyncio.sleep(5)
        
        # Take screenshot of initial state
        await page.screenshot(path="initial_state.png")
        print("Saved initial state screenshot")
        
        # Scroll to load all tokens
        print("Scrolling to load all content...")
        for i in range(5):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            print(f"Scroll {i+1}/5 completed")
        
        # Take screenshot after scrolling
        await page.screenshot(path="after_scrolling.png")
        print("Saved after scrolling screenshot")
        
        # The selector that matched 48 elements, which is likely the token elements
        token_selector = '.market-list-item-new'
        
        # Count the elements again to confirm
        count = await page.evaluate(f'() => document.querySelectorAll("{token_selector}").length')
        print(f"Found {count} token elements with selector '{token_selector}'")
        
        # Get initial URL to check for navigation
        initial_url = page.url
        print(f"Initial URL: {initial_url}")
        
        # Create a new context for testing individual tokens
        test_context = await browser.new_context(viewport={"width": 1280, "height": 900})
        
        # Store token links
        token_links = []
        
        # Loop through each token element and try to click it
        for i in range(count):
            print(f"\nProcessing token {i+1}/{count}...")
            
            # Create a new page for each token to avoid navigation state issues
            test_page = await test_context.new_page()
            test_page.set_default_navigation_timeout(30000)
            
            # Navigate to the main page
            await test_page.goto("https://sonefi.xyz/#/memeLaunch", wait_until="domcontentloaded")
            
            # Wait a moment for the page to stabilize
            await asyncio.sleep(2)
            
            # Scroll to load all tokens
            for j in range(3):
                await test_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)
            
            # Take a screenshot to debug (only for the first few tokens)
            if i < 5:
                await test_page.screenshot(path=f"token_{i+1}_before_click.png")
                
            try:
                # First, get some information about the element before clicking
                element_info = await test_page.evaluate(f'''
                    () => {{
                        const elements = document.querySelectorAll('{token_selector}');
                        if ({i} >= elements.length) return null;
                        const element = elements[{i}];
                        
                        // Get the element text
                        const text = element.textContent.trim();
                        
                        // Get elements position
                        const rect = element.getBoundingClientRect();
                        
                        return {{
                            text: text,
                            position: {{
                                x: rect.x + rect.width/2,
                                y: rect.y + rect.height/2
                            }},
                            width: rect.width,
                            height: rect.height
                        }};
                    }}
                ''')
                
                if not element_info:
                    print(f"Could not find element {i+1}")
                    continue
                    
                print(f"Found token element with text: {element_info.get('text', '')[:30]}")
                
                # Scroll the element into view
                await test_page.evaluate(f'''
                    () => {{
                        const elements = document.querySelectorAll('{token_selector}');
                        if ({i} < elements.length) {{
                            elements[{i}].scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}
                        return true;
                    }}
                ''')
                
                # Wait for scrolling to complete
                await asyncio.sleep(1)
                
                # Try clicking the element with JavaScript first
                clicked = await test_page.evaluate(f'''
                    () => {{
                        try {{
                            const elements = document.querySelectorAll('{token_selector}');
                            if ({i} >= elements.length) return false;
                            elements[{i}].click();
                            return true;
                        }} catch (e) {{
                            console.error("Click error:", e);
                            return false;
                        }}
                    }}
                ''')
                
                if not clicked:
                    print(f"Could not click token {i+1} with JavaScript")
                    
                    # Try clicking using Playwright's built-in click 
                    # by position instead of by element reference
                    if element_info and 'position' in element_info:
                        x = element_info['position']['x']
                        y = element_info['position']['y']
                        print(f"Trying to click at position ({x}, {y})")
                        
                        await test_page.mouse.click(x, y)
                        print(f"Clicked at position ({x}, {y})")
                
                # Wait a moment for navigation to occur
                await asyncio.sleep(3)
                
                # Capture the new URL
                current_url = test_page.url
                
                # Check if navigation occurred
                if current_url != "https://sonefi.xyz/#/memeLaunch":
                    print(f"Navigation detected! New URL: {current_url}")
                    token_links.append(current_url)
                else:
                    print(f"No navigation detected for token {i+1}")
                
                # Take a screenshot after clicking (only for the first few tokens)
                if i < 5:
                    await test_page.screenshot(path=f"token_{i+1}_after_click.png")
                    
            except Exception as e:
                print(f"Error processing token {i+1}: {e}")
            
            # Close the test page
            await test_page.close()
            
        # Close the test context
        await test_context.close()
        
        # Save the token links to a file
        with open("data/token_links.json", "w") as f:
            json.dump(token_links, f, indent=2)
        print(f"\nSaved {len(token_links)} token links to data/token_links.json")
        
        # Close the browser
        await browser.close()
        print("Browser closed")
        
        return token_links

async def main():
    try:
        links = await extract_token_links_by_clicking()
        print("\nExtracted token links:")
        for link in links:
            print(link)
    except Exception as e:
        print(f"An error occurred in the main function: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())