#!/usr/bin/env python3
"""
Twitter scraper and analyzer for cryptocurrency sentiment analysis.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError
import re
import numpy as np
from collections import defaultdict
import time
from dotenv import load_dotenv
import random

# Import the Gemini analyzer using absolute import instead of relative import
from gemini_analyzer import analyze_sentiment_with_gemini

# Load environment variables from .env file
load_dotenv()

# Get the script's directory for relative file paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)

# Configure logging
logger = logging.getLogger(__name__)

# Path to Twitter cookies file
COOKIES_FILE = os.path.join(DATA_DIR, "twitter_cookies.json")
# Path to hedra data file
HEDRA_DATA_FILE = os.path.join(DATA_DIR, "tokens_structured.json")
# Path to output Twitter data file
TWITTER_DATA_FILE = os.path.join(DATA_DIR, "twitter_coin_data.json")
# Path to analysis output file
ANALYSIS_OUTPUT_FILE = os.path.join(DATA_DIR, "coin_investment_analysis.json")

def load_helix_data():
    """
    Load coin data from tokens_structured.json
    
    Returns:
        dict: Loaded coin data or None if error
    """
    try:
        with open(HEDRA_DATA_FILE, 'r', encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading tokens_structured.json: {e}")
        return None

def extract_coin_symbols(helix_data):
    """
    Extract coin symbols from helix data
    
    Args:
        helix_data (dict): The loaded helix/token data
        
    Returns:
        list: Extracted coin symbols
    """
    coins = []
    if not helix_data:
        return coins
    
    for item in helix_data:
        if 'symbol' in item:
            # Extract the coin part before /INJ
            symbol = item['symbol'].split('/')[0]
            coins.append(symbol)
    
    logger.info(f"Extracted {len(coins)} coin symbols from helix data")
    return coins

def normalize_cookies(cookies):
    """
    Normalize cookie format for Playwright
    Specifically fixes the sameSite attribute to be one of: "Strict", "Lax", or "None"
    
    Args:
        cookies (list): List of cookie objects
        
    Returns:
        list: Normalized cookie objects compatible with Playwright
    """
    normalized_cookies = []
    
    for cookie in cookies:
        # Create a copy of the cookie to modify
        normalized_cookie = cookie.copy()
        
        # Fix sameSite attribute if it exists
        if 'sameSite' in normalized_cookie:
            same_site = normalized_cookie['sameSite']
            # Handle None values
            if same_site is None:
                normalized_cookie['sameSite'] = 'Lax'  # Use Lax as default
            else:
                # Map common values to the correct formats
                same_site_lower = str(same_site).lower()
                if same_site_lower in ['no_restriction', 'none']:
                    normalized_cookie['sameSite'] = 'None'
                elif same_site_lower in ['lax']:
                    normalized_cookie['sameSite'] = 'Lax'
                elif same_site_lower in ['strict']:
                    normalized_cookie['sameSite'] = 'Strict'
                else:
                    # Default to Lax if unknown
                    normalized_cookie['sameSite'] = 'Lax'
        
        # Some cookies from browsers may have these fields that Playwright doesn't accept
        for field in ['hostOnly', 'session', 'storeId']:
            if field in normalized_cookie:
                del normalized_cookie[field]
                
        # Add the normalized cookie
        normalized_cookies.append(normalized_cookie)
    
    return normalized_cookies

async def load_cookies(context):
    """
    Load cookies from the cookies file
    
    Args:
        context: Playwright browser context
        
    Returns:
        bool: True if cookies were loaded successfully, False otherwise
    """
    try:
        with open(COOKIES_FILE, 'r') as f:
            original_cookies = json.load(f)
        
        # Normalize cookies to match Playwright's expected format
        normalized_cookies = normalize_cookies(original_cookies)
        
        logger.info(f"Normalizing {len(original_cookies)} cookies for Playwright compatibility")
        
        # Add normalized cookies to the browser context
        await context.add_cookies(normalized_cookies)
        logger.info(f"Successfully loaded {len(normalized_cookies)} cookies")
        return True
    except Exception as e:
        logger.error(f"Error loading cookies: {e}")
        logger.error("You may need to refresh your Twitter cookies or provide them in the correct format")
        return False

async def search_twitter_for_coin(page, coin_symbol):
    """
    Search Twitter for a specific coin symbol
    
    Args:
        page: Playwright page object
        coin_symbol (str): The cryptocurrency symbol to search for
        
    Returns:
        list: List of tweet objects
    """
    search_url = f"https://twitter.com/search?q=%24{coin_symbol}%20OR%20{coin_symbol}%20crypto&src=typed_query&f=live"
    
    try:
        logger.info(f"Searching Twitter for {coin_symbol}")
        
        # Navigate to search URL with extended timeout
        await page.goto(search_url, timeout=120000)  # Increase timeout to 2 minutes
        
        # Wait for DOM content loaded instead of networkidle (less strict)
        try:
            await page.wait_for_load_state('domcontentloaded', timeout=30000)
        except Exception as e:
            logger.warning(f"Page load state timeout for {coin_symbol}, continuing anyway: {e}")
        
        # Sleep a moment to allow page to stabilize
        await asyncio.sleep(3)
        
        # Wait for tweets to load with more resilient approach
        try:
            # Try to find any tweet elements
            tweet_selector = 'article[data-testid="tweet"]'
            has_tweets = await page.query_selector(tweet_selector) is not None
            
            # If initial check doesn't find tweets, wait for them to appear
            if not has_tweets:
                logger.info(f"Waiting for tweets to load for {coin_symbol}...")
                await page.wait_for_selector(tweet_selector, timeout=20000)
        except Exception as e:
            logger.warning(f"No tweets found for {coin_symbol}: {e}")
            return []
        
        # Scroll to load more tweets with error handling
        for i in range(3):
            try:
                await page.evaluate('window.scrollBy(0, 1000)')
                await asyncio.sleep(2)  # Give more time for content to load
            except Exception as e:
                logger.warning(f"Error scrolling for {coin_symbol} (scroll #{i+1}): {e}")
                # Continue despite scroll errors
        
        # Extract tweets with improved error handling
        try:
            tweets = await page.evaluate("""
            () => {
                const tweets = [];
                const tweetElements = document.querySelectorAll('article[data-testid="tweet"]');
                
                if (!tweetElements || tweetElements.length === 0) {
                    return tweets; // Return empty array if no tweets
                }
                
                tweetElements.forEach(tweet => {
                    try {
                        // Username and handle
                        const userElement = tweet.querySelector('div[data-testid="User-Name"]');
                        const username = userElement ? userElement.querySelector('span:first-child')?.textContent : null;
                        const handleElement = userElement ? userElement.querySelector('span:nth-child(2)')?.textContent : null;
                        
                        // Tweet text
                        const textElement = tweet.querySelector('div[data-testid="tweetText"]');
                        const text = textElement ? textElement.textContent : null;
                        
                        // Time
                        const timeElement = tweet.querySelector('time');
                        const timestamp = timeElement ? timeElement.getAttribute('datetime') : null;
                        
                        // Engagement metrics
                        const replyElement = tweet.querySelector('div[data-testid="reply"]');
                        const replyCount = replyElement ? replyElement.textContent : '0';
                        
                        const retweetElement = tweet.querySelector('div[data-testid="retweet"]');
                        const retweetCount = retweetElement ? retweetElement.textContent : '0';
                        
                        const likeElement = tweet.querySelector('div[data-testid="like"]');
                        const likeCount = likeElement ? likeElement.textContent : '0';
                        
                        // URL
                        const linkElement = tweet.querySelector('a[href*="/status/"]');
                        const url = linkElement ? 'https://twitter.com' + linkElement.getAttribute('href') : null;
                        
                        // Only add tweet if we have at least text or username
                        if (text || username) {
                            tweets.push({
                                username: username || "Unknown",
                                handle: handleElement || "",
                                text: text || "(No text)",
                                timestamp: timestamp || "",
                                reply_count: parseEngagementCount(replyCount),
                                retweet_count: parseEngagementCount(retweetCount),
                                like_count: parseEngagementCount(likeCount),
                                url: url || ""
                            });
                        }
                    } catch (error) {
                        console.error('Error parsing tweet:', error);
                    }
                });
                
                function parseEngagementCount(countText) {
                    if (!countText) return 0;
                    countText = countText.trim();
                    if (countText === '') return 0;
                    
                    try {
                        if (countText.includes('K')) {
                            return parseInt(parseFloat(countText.replace('K', '')) * 1000);
                        } else if (countText.includes('M')) {
                            return parseInt(parseFloat(countText.replace('M', '')) * 1000000);
                        } else {
                            return parseInt(countText);
                        }
                    } catch (e) {
                        return 0;
                    }
                }
                
                return tweets;
            }
            """)
        except Exception as e:
            logger.error(f"Error extracting tweets for {coin_symbol}: {e}")
            return []
        
        # Add metadata to tweets
        for tweet in tweets:
            tweet['coin_symbol'] = coin_symbol
            tweet['discovery_time'] = datetime.now().isoformat()
        
        logger.info(f"Found {len(tweets)} tweets for {coin_symbol}")
        return tweets
    
    except Exception as e:
        logger.error(f"Error searching Twitter for {coin_symbol}: {e}")
        return []

def analyze_coin_data(helix_data, twitter_data):
    """
    Analyze coin data from helix and Twitter to find top investment opportunities
    
    Args:
        helix_data (dict): The loaded helix/token data
        twitter_data (dict): The scraped Twitter data
        
    Returns:
        list: Sorted list of top coins based on investment score
    """
    coin_analysis = {}
    helix_coins_map = {}
    
    # Create a map of coin symbols to helix data
    for item in helix_data:
        symbol = item['symbol'].split('/')[0]
        price_str = item['price']
        
        # Handle price formatting issues
        try:
            # Remove commas and any other non-numeric characters except decimal points
            clean_price = re.sub(r'[^\d.]', '', price_str)
            price = float(clean_price) if clean_price else 0.0
        except (ValueError, TypeError):
            price = 0.0
        
        change_str = item['change_24h']
        
        # Convert change_24h to float robustly
        if isinstance(change_str, str):
            change = float(change_str.strip('%')) if change_str != 'N/A' else 0.0
        elif isinstance(change_str, (int, float)):
            change = float(change_str)
        else:
            change = 0.0
        
        helix_coins_map[symbol] = {
            'price': price,
            'change_24h': change
        }
    
    logger.info(f"Created helix_coins_map with {len(helix_coins_map)} coins")
    
    # Process Twitter data - extract coin tweets and their analysis
    coin_tweets = {}
    coin_analysis_data = {}
    
    # Debug print of twitter_data keys
    logger.info(f"Twitter data keys: {list(twitter_data.keys())[:20]}...")
    
    for key, value in twitter_data.items():
        if key.endswith('_analysis'):
            # This is an analysis entry - extract the coin symbol
            coin_symbol = key.replace('_analysis', '')
            coin_analysis_data[coin_symbol] = value
            logger.info(f"Found analysis for {coin_symbol}: {value.keys()}")
        elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict) and 'coin_symbol' in value[0]:
            # This is a tweet list
            coin_symbol = value[0]['coin_symbol']
            coin_tweets[coin_symbol] = value
            logger.info(f"Found {len(value)} tweets for {coin_symbol}")
    
    logger.info(f"Extracted data for {len(coin_tweets)} coins with tweets and {len(coin_analysis_data)} coins with analysis")
    
    # Now we can analyze each coin that has both tweets and analysis
    analyzed_coins = []
    
    for coin_symbol, tweets in coin_tweets.items():
        logger.info(f"Analyzing {coin_symbol} with {len(tweets)} tweets")
        
        # Skip if we don't have analysis data
        if coin_symbol not in coin_analysis_data:
            logger.info(f"Skipping {coin_symbol}: no analysis data")
            continue
            
        # Skip if coin not in helix data (for price information)
        if coin_symbol not in helix_coins_map:
            logger.info(f"Skipping {coin_symbol}: not found in helix_coins_map")
            continue
            
        # Get price and change data
        price = helix_coins_map[coin_symbol]['price']
        change = helix_coins_map[coin_symbol]['change_24h']
        
        # Get sentiment and analysis from Gemini
        analysis = coin_analysis_data[coin_symbol]
        
        sentiment_score = analysis.get('sentiment_score', 0)
        investment_analysis = analysis.get('investment_analysis', 'No analysis available')
        key_factors = analysis.get('key_factors', [])
        
        # Calculate investment score (simple example - customize for your needs)
        # Here we're weighing sentiment heavily and also considering price change
        investment_score = (sentiment_score * 0.7) + (change / 100 * 0.3)
        
        logger.info(f"{coin_symbol}: price=${price}, change={change}%, sentiment={sentiment_score}, investment_score={investment_score:.2f}")
        
        # Add to analyzed coins
        analyzed_coins.append({
            'symbol': coin_symbol,
            'price': price,
            'change_24h': change,
            'num_tweets': len(tweets),
            'sentiment_score': sentiment_score,
            'investment_score': investment_score,
            'investment_analysis': investment_analysis,
            'key_factors': key_factors
        })
    
    # Sort coins by investment score (descending)
    analyzed_coins.sort(key=lambda x: x.get('investment_score', 0), reverse=True)
    
    # Get top N coins (adjust this number as needed)
    top_n = 10
    top_coins = analyzed_coins[:top_n] if len(analyzed_coins) > top_n else analyzed_coins
    
    logger.info(f"Analysis complete. Found {len(analyzed_coins)} analyzed coins")
    logger.info(f"Top {len(top_coins)} coins: {[c['symbol'] for c in top_coins]}")
    
    return top_coins

async def scrape_twitter_for_coins():
    """
    Scrape Twitter for the coin data from the loaded coins list
    
    Returns:
        bool: True if scraping was successful
    """
    start_time = time.time()
    
    helix_data = load_helix_data()
    if not helix_data:
        logger.error("No helix data found. Please run helix_scraper.py first.")
        return False
    
    coin_symbols = extract_coin_symbols(helix_data)
    if not coin_symbols:
        logger.error("No coin symbols found in helix data.")
        return False
    
    logger.info(f"Starting Twitter scraper for {len(coin_symbols)} coins")
    
    async with async_playwright() as p:
        browser_launch_options = {
            "headless": True,
            "timeout": 120000,  # 2 minute timeout for launch
            "args": [
                "--disable-web-security",
                "--disable-features=IsolateOrigins",
                "--disable-site-isolation-trials",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        }
        
        logger.info(f"Launching browser with options: {browser_launch_options}")
        browser = await p.chromium.launch(**browser_launch_options)
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        
        # Longer timeout for all operations (2 minutes)
        context.set_default_timeout(120000)
        
        # Load cookies
        cookies_loaded = await load_cookies(context)
        if not cookies_loaded:
            logger.error("Failed to load cookies. Please check the cookies file.")
            await browser.close()
            return False
        
        # Create a new page
        page = await context.new_page()
        
        # Initialize result storage
        twitter_data = {}
        processed_count = 0
        error_count = 0
        
        try:
            # Go to Twitter first to ensure we're properly logged in
            logger.info("Navigating to Twitter homepage")
            await page.goto("https://twitter.com/home", timeout=120000)
            
            # Wait for the page to load
            try:
                await page.wait_for_selector("article", timeout=30000)
                logger.info("Twitter homepage loaded successfully")
            except TimeoutError:
                logger.warning("Twitter timeline articles not found within timeout")
                logger.info("Continuing anyway, may not be logged in properly")
            
            # Pause to ensure page is fully loaded
            await asyncio.sleep(5)
            
            # Process each coin symbol
            for coin in coin_symbols:
                logger.info(f"Processing coin {coin} ({processed_count + 1}/{len(coin_symbols)})")
                
                try:
                    # Search Twitter for this coin
                    tweets = await search_twitter_for_coin(page, coin)
                    
                    if tweets:
                        logger.info(f"Found {len(tweets)} tweets for {coin}")
                        
                        # Store the tweets in our result
                        twitter_data[coin] = tweets
                        
                        # Analyze tweets with Gemini
                        tweets_text = "\n\n".join([t["text"] for t in tweets])
                        try:
                            # Only analyze if we have tweets
                            if tweets_text.strip():
                                # Apply rate limiting for API key usage
                                analysis = analyze_sentiment_with_gemini(tweets_text, coin)
                                
                                if analysis:
                                    logger.info(f"Analyzed {len(tweets)} tweets for {coin}")
                                    
                                    # Update the twitter data with the analysis
                                    twitter_data[coin] = [
                                        {**tweet, "analyzed": True}
                                        for tweet in twitter_data[coin]
                                    ]
                                    
                                    # Add analysis to the coin data
                                    twitter_data[f"{coin}_analysis"] = {
                                        "sentiment_score": analysis["sentiment_score"],
                                        "investment_analysis": analysis.get("investment_analysis", analysis.get("analysis", "No analysis")),
                                        "key_factors": analysis.get("key_factors", []),
                                    }
                                else:
                                    logger.warning(f"Failed to analyze tweets for {coin}")
                        except Exception as e:
                            logger.error(f"Error analyzing tweets for {coin}: {e}")
                    
                    processed_count += 1
                    
                    # Save progress incrementally
                    if processed_count % 5 == 0 or processed_count == len(coin_symbols):
                        with open(TWITTER_DATA_FILE, 'w') as f:
                            json.dump(twitter_data, f, indent=2)
                        logger.info(f"Saved data for {processed_count}/{len(coin_symbols)} coins processed so far")
                    
                    # Random delay between requests (2-5 seconds)
                    delay = random.uniform(2, 5)
                    logger.info(f"Waiting {delay:.2f} seconds before next request")
                    await asyncio.sleep(delay)
                    
                except Exception as e:
                    logger.error(f"Error processing coin {coin}: {e}")
                    error_count += 1
                    
                    # If we get too many errors, break out to avoid wasting time
                    if error_count > 10:
                        logger.error(f"Too many errors ({error_count}), stopping processing")
                        break
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
        finally:
            try:
                # Ensure browser is closed properly
                await browser.close()
                logger.info("Browser closed successfully")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
    
    # Analyze the data if we have tweets
    if twitter_data:
        logger.info("Starting coin analysis with Gemini API")
        top_coins = analyze_coin_data(helix_data, twitter_data)
        
        # Save analysis results
        analysis_result = {
            "top_investment_coins": top_coins,
            "analysis_timestamp": datetime.now().isoformat(),
            "total_coins_analyzed": len(coin_symbols),
            "total_tweets_analyzed": sum(len(tweets) for key, tweets in twitter_data.items() 
                                         if isinstance(tweets, list) and not key.endswith('_analysis'))
        }
        
        with open(ANALYSIS_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Analysis complete. Top {len(top_coins)} coins saved to {ANALYSIS_OUTPUT_FILE}")
        
        # Print top coins to console
        print("\n===== TOP COINS TO INVEST IN =====")
        for i, coin in enumerate(top_coins, 1):
            print(f"{i}. {coin['symbol']} - Price: ${coin['price']:.6f} - Change: {coin['change_24h']}%")
            print(f"   Score: {coin.get('investment_score', 0):.2f} | Sentiment: {coin.get('sentiment_score', 0):.2f}")
            print(f"   Analysis: {coin.get('investment_analysis', '')}")
            print(f"   Key factors: {', '.join(coin.get('key_factors', [])) if coin.get('key_factors') else 'None identified'}")
            print()
        print("=================================\n")
    
    return True

async def main():
    """
    Main entry point for the Twitter scraper
    """
    # Configure root logger if running as main script
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(SCRIPT_DIR, "twitter_scraper.log")),
                logging.StreamHandler()
            ]
        )
    
    logger.info("Starting Twitter coin scraper and analyzer with Gemini AI")
    await scrape_twitter_for_coins()

if __name__ == "__main__":
    asyncio.run(main())