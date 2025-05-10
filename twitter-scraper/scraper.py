import json
import time
import logging
import asyncio
import re
import os
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Set up paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
LOGS_DIR = os.path.join(DATA_DIR, "logs")

# Create logs directory if it doesn't exist
os.makedirs(LOGS_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=os.path.join(LOGS_DIR, 'sonefi_scraper.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Define the number of concurrent tasks
CONCURRENT_TASKS = 3

async def setup_browser():
    """Set up and return a configured Playwright browser instance"""
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        return playwright, browser
    except Exception as e:
        logging.error(f"Error setting up Playwright: {e}")
        return None, None

async def extract_token_data(browser, url, semaphore):
    """Extract text specifically from the token-market-info div"""
    page = None
    context = None
    
    async with semaphore:  # Use semaphore to limit concurrent requests
        try:
            logging.info(f"Processing URL: {url}")
            
            # Create a new browser context for this extraction
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            page = await context.new_page()
            
            # Navigate to the page with a longer timeout
            await page.goto(url, wait_until='networkidle', timeout=90000)
            
            # Wait longer for React app to fully render
            logging.info(f"Waiting for React content to load for {url}")
            await page.wait_for_timeout(15000)  # 15 seconds
            
            # Extract the token address from URL
            token_address = url.split('/')[-1]
            
            # Extract text directly from the div.token-market-info element shown in the screenshot
            token_info_text = await page.evaluate('''() => {
                // Target the exact element shown in the screenshot - a blue bar with token info
                const tokenMarketInfoDiv = document.querySelector('div.token-market-info') || 
                                          document.querySelector('[class*="token-market-info"]');
                    
                // If we can't find that specific element, look for something with similar style
                // Based on the screenshot, it's a blue bar with Price, Market Cap, etc.
                if (!tokenMarketInfoDiv) {
                    // Try to find the element based on its visual appearance or content
                    const allDivs = Array.from(document.querySelectorAll('div'));
                    const infoDiv = allDivs.find(div => {
                        const text = div.innerText || '';
                        return text.includes('Price') && 
                               text.includes('Market Cap') && 
                               text.includes('Virtual Liquidity') &&
                               text.includes('24H Volume');
                    });
                    
                    if (infoDiv) {
                        return infoDiv.innerText;
                    }
                } else {
                    return tokenMarketInfoDiv.innerText;
                }
                
                // If all else fails, return null
                return null;
            }''')
            
            # Extract the token name shown in the blue header area
            token_name = await page.evaluate('''() => {
                // Look for the token name element - typically a heading/title in the blue bar section
                // From the screenshot, we can see it looks like "KIFCOIN ($KIF)"
                const headingElements = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6, div.token-name, div[class*="-title"], div[class*="title-"], span[class*="title"]'));
                
                for (const element of headingElements) {
                    const text = element.innerText || '';
                    // If text contains format like "NAME ($SYMBOL)"
                    if (text.includes('(') && text.includes(')') && text.includes('$')) {
                        return text.trim();
                    }
                    // or just a token name with $ symbol (like $ETH)
                    else if (text.includes('$') && text.length < 30) {
                        return text.trim();
                    }
                }
                
                // Alternative approach - look for elements with larger font size in the token info area
                const largeTextElements = Array.from(document.querySelectorAll('div, span, p'))
                    .filter(el => {
                        const computedStyle = window.getComputedStyle(el);
                        const fontSize = parseInt(computedStyle.fontSize);
                        return fontSize > 16 && el.innerText && el.innerText.length < 50;
                    });
                    
                for (const element of largeTextElements) {
                    const text = element.innerText || '';
                    if ((text.includes('$') || text.includes('(') && text.includes(')'))) {
                        return text.trim();
                    }
                }
                
                // If still can't find, try a more general approach
                const allElements = Array.from(document.querySelectorAll('*'));
                const possibleNameElement = allElements.find(el => {
                    const text = el.innerText || '';
                    return text.includes('$') && text.length < 50 && 
                           !text.includes('Price') && !text.includes('Market Cap');
                });
                
                return possibleNameElement ? possibleNameElement.innerText.trim() : null;
            }''')
            
            # Create a token data object with the extracted text
            token_data = {
                "token_address": token_address,
                "url": url,
                "token_name": token_name or "Unknown Token",
                "token_info_text": token_info_text or "No token market info found"
            }
            
            # Format the token data
            formatted_token = format_token_data(token_data)
            
            logging.info(f"Successfully extracted and formatted token info for: {token_address}")
            return formatted_token
            
        except PlaywrightTimeoutError:
            logging.error(f"Timeout waiting for page to load: {url}")
            return {"url": url, "token_address": url.split('/')[-1], "token_name": "Unknown Token", "error": "Timeout waiting for page to load"}
        except Exception as e:
            logging.error(f"Error extracting data from {url}: {e}")
            return {"url": url, "token_address": url.split('/')[-1], "token_name": "Unknown Token", "error": str(e)}
        finally:
            # Clean up resources
            if page:
                await page.close()
            if context:
                await context.close()

def format_token_data(token_data):
    """Format raw token data into structured data"""
    # Start with the token address and URL
    formatted_token = {
        "token_address": token_data["token_address"],
        "url": token_data["url"]
    }
    
    # Process token name if available
    if "token_name" in token_data and token_data["token_name"]:
        formatted_token["token_name"] = token_data["token_name"]
        
        # Try to extract token symbol from name (format typically: "NAME ($SYMBOL)")
        try:
            if "(" in token_data["token_name"] and ")" in token_data["token_name"] and "$" in token_data["token_name"]:
                symbol_match = re.search(r'\(\$([^)]+)\)', token_data["token_name"])
                if symbol_match:
                    formatted_token["token_symbol"] = symbol_match.group(1)
            # Handle case where name is just $SYMBOL
            elif token_data["token_name"].startswith("$") and " " not in token_data["token_name"]:
                formatted_token["token_symbol"] = token_data["token_name"][1:]  # Remove $ prefix
        except Exception as e:
            logging.warning(f"Error extracting token symbol: {e}")
    
    # If there's no token_info_text or there was an error, return early
    if "token_info_text" not in token_data or token_data["token_info_text"] == "No token market info found":
        if "error" in token_data:
            formatted_token["error"] = token_data["error"]
        else:
            formatted_token["error"] = "No token info found"
        return formatted_token
    
    # Parse the token info text
    token_info_text = token_data["token_info_text"]
    lines = token_info_text.strip().split('\n')
    
    # Process each line to extract the data
    current_field = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
            
        # Check if this is a header line (field name)
        if line.startswith('Price '):
            current_field = 'price'
            # Extract percentage change
            match = re.search(r'Price\s+([+-]?\d+\.?\d*)%', line)
            if match:
                try:
                    formatted_token["price_change_percentage"] = float(match.group(1))
                except (ValueError, TypeError):
                    formatted_token["price_change_percentage"] = None
        elif line == 'Market Cap':
            current_field = 'market_cap'
        elif line == 'Virtual Liquidity':
            current_field = 'virtual_liquidity'
        elif line == '24H Volume':
            current_field = '24h_volume'
        elif line == 'Token Created':
            current_field = 'token_created'
        # This is a value line
        elif current_field == 'price' and (line.startswith('$') or line.startswith('0.')):
            # Handle price value
            if 'ASTR' in line:
                formatted_token["currency"] = "ASTR"
                line = line.replace('ASTR', '').strip()
            else:
                formatted_token["currency"] = "USD"
                line = line.replace('$', '').strip()
                
            # Store the original price string (for reference)
            formatted_token["price_string"] = line
            
            # Handle scientific notation with superscripts or subscripts
            # Map common Unicode super/subscripts to standard ASCII
            unicode_map = {
                '\u2070': '0', '\u00B9': '1', '\u00B2': '2', '\u00B3': '3', '\u2074': '4',
                '\u2075': '5', '\u2076': '6', '\u2077': '7', '\u2078': '8', '\u2079': '9',
                '\u2080': '0', '\u2081': '1', '\u2082': '2', '\u2083': '3', '\u2084': '4',
                '\u2085': '5', '\u2086': '6', '\u2087': '7', '\u2088': '8', '\u2089': '9',
                '\u208A': '+', '\u208B': '-', '\u207A': '+', '\u207B': '-',
                '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
                '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
                'ₓ': ''  # ₓ is a special subscript x that we can ignore
            }
            
            # Replace all Unicode super/subscripts with standard ASCII
            clean_line = line
            for unicode_char, ascii_char in unicode_map.items():
                clean_line = clean_line.replace(unicode_char, ascii_char)
            
            # Handle scientific notation (like "0.012707" where 5 is a subscript)
            if re.search(r'0\.0(\d+)', clean_line):
                try:
                    # Extract the relevant parts
                    match = re.search(r'0\.0(\d+)', clean_line)
                    if match:
                        digits = match.group(1)
                        # Calculate the proper float value (with correct decimal places)
                        price_value = float(f"0.0{digits}")
                        formatted_token["price_value"] = price_value
                    else:
                        formatted_token["price_value"] = float(clean_line)
                except (ValueError, TypeError):
                    formatted_token["price_value"] = clean_line
            else:
                # Try normal float conversion for non-scientific notation
                try:
                    formatted_token["price_value"] = float(clean_line)
                except (ValueError, TypeError):
                    formatted_token["price_value"] = clean_line
                
        elif current_field == 'market_cap':
            # Handle market cap
            if 'ASTR' in line:
                line = line.replace('ASTR', '').strip()
            else:
                line = line.replace('$', '').strip()
                
            # Remove commas
            line = line.replace(',', '')
            
            # Try to convert to float
            try:
                formatted_token["market_cap"] = float(line)
            except (ValueError, TypeError):
                formatted_token["market_cap"] = line
                
        elif current_field == 'virtual_liquidity':
            # Handle virtual liquidity
            if 'ASTR' in line:
                line = line.replace('ASTR', '').strip()
            else:
                line = line.replace('$', '').strip()
                
            # Remove commas
            line = line.replace(',', '')
            
            # Try to convert to float
            try:
                formatted_token["virtual_liquidity"] = float(line)
            except (ValueError, TypeError):
                formatted_token["virtual_liquidity"] = line
                
        elif current_field == '24h_volume':
            # Handle 24h volume
            if 'ASTR' in line:
                line = line.replace('ASTR', '').strip()
            else:
                line = line.replace('$', '').strip()
            
            # Handle special cases like "<$0.0001"
            if line.startswith('<'):
                line = line.replace('<', '')
                formatted_token["24h_volume_is_less_than"] = True
            else:
                formatted_token["24h_volume_is_less_than"] = False
                
            # Remove commas
            line = line.replace(',', '')
            
            # Try to convert to float
            try:
                formatted_token["24h_volume"] = float(line)
            except (ValueError, TypeError):
                formatted_token["24h_volume"] = line
                
        elif current_field == 'token_created' and i > 0:
            # Handle token created time
            if line == "--":
                formatted_token["token_created"] = None
                formatted_token["token_age_days"] = None
            else:
                formatted_token["token_created"] = line
                # Parse days, hours, minutes format
                try:
                    age_parts = line.split(':')
                    if len(age_parts) == 3:
                        days = int(age_parts[0].replace('D', ''))
                        hours = int(age_parts[1].replace('H', ''))
                        minutes = int(age_parts[2].replace('M', ''))
                        total_hours = days * 24 + hours + minutes / 60
                        formatted_token["token_age_days"] = round(total_hours / 24, 2)
                    else:
                        formatted_token["token_age_days"] = None
                except Exception:
                    formatted_token["token_age_days"] = None
    
    # Keep the original text for reference
    formatted_token["raw_text"] = token_info_text
    
    return formatted_token

async def scrape_sonefi_tokens_async():
    """
    Main async function to scrape token data from all URLs in data/sonefi_links.json using concurrent tasks
    """
    try:
        # Load URLs from the JSON file
        links_file = os.path.join(DATA_DIR, 'sonefi_links.json')
        with open(links_file, 'r') as f:
            urls = json.load(f)
        
        logging.info(f"Loaded {len(urls)} URLs from {links_file}")
        
        # Setup Playwright
        playwright, browser = await setup_browser()
        if not browser:
            logging.error("Failed to set up Playwright browser. Aborting.")
            return []
        
        # Create a semaphore to limit concurrency
        semaphore = asyncio.Semaphore(CONCURRENT_TASKS)
        
        # Create tasks for all URLs
        tasks = []
        for url in urls:
            tasks.append(extract_token_data(browser, url, semaphore))
        
        # Execute tasks concurrently and gather results
        logging.info(f"Starting concurrent scraping with {CONCURRENT_TASKS} workers")
        start_time = time.time()
        all_token_data = await asyncio.gather(*tasks)
        end_time = time.time()
        
        logging.info(f"Concurrent scraping completed in {end_time - start_time:.2f} seconds")
        
        # Close Playwright resources
        await browser.close()
        await playwright.stop()
        
        # Save the collected data to a JSON file
        output_file = os.path.join(DATA_DIR, 'sonefi_tokens.json')
        with open(output_file, 'w') as f:
            json.dump(all_token_data, f, indent=2)
        
        logging.info(f"Scraping completed. Formatted token info data saved to {output_file}")
        print(f"Scraping completed. Extracted and formatted token info for {len(all_token_data)} tokens in {end_time - start_time:.2f} seconds.")
        
        return all_token_data
        
    except Exception as e:
        logging.error(f"Error in scrape_sonefi_tokens_async: {e}")
        if 'browser' in locals() and browser:
            await browser.close()
        if 'playwright' in locals() and playwright:
            await playwright.stop()
        return []

async def scrape_sonefi_tokens():
    """
    Fixed wrapper function that can be called from an existing async context
    """
    return await scrape_sonefi_tokens_async()

# For direct script execution
if __name__ == "__main__":
    asyncio.run(scrape_sonefi_tokens_async())