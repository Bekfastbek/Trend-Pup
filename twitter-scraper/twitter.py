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

# Analysis functionality has been moved to gemini_analyzer.py
# Import removed since analysis is handled separately

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
# Path to token data file
TOKEN_DATA_FILE = os.path.join(DATA_DIR, "tokens_structured.json")
# Path to SoneFi tokens file
SONEFI_TOKENS_FILE = os.path.join(DATA_DIR, "sonefi_tokens.json")
# Path to output Twitter data file
TWITTER_DATA_FILE = os.path.join(DATA_DIR, "twitter_coin_data.json")
# Path to analysis output file
ANALYSIS_OUTPUT_FILE = os.path.join(DATA_DIR, "coin_investment_analysis.json")

def load_token_data():
    """
    Load coin data from tokens_structured.json
    
    Returns:
        dict: Loaded coin data or None if error
    """
    try:
        with open(TOKEN_DATA_FILE, 'r', encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading tokens_structured.json: {e}")
        return None

def load_sonefi_tokens():
    """
    Load token data from sonefi_tokens.json
    
    Returns:
        dict: Loaded SoneFi token data or None if error
    """
    try:
        with open(SONEFI_TOKENS_FILE, 'r', encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading sonefi_tokens.json: {e}")
        return None

def extract_sonefi_token_info(sonefi_tokens):
    """
    Extract token names and symbols from SoneFi tokens data
    
    Args:
        sonefi_tokens (list): The loaded SoneFi token data
        
    Returns:
        tuple: (list of token names, list of token symbols)
    """
    token_names = []
    token_symbols = []
    
    if not sonefi_tokens:
        logger.warning("No SoneFi tokens data to extract information from")
        return token_names, token_symbols
    
    for token in sonefi_tokens:
        # Skip entries with error or missing required fields
        if 'error' in token or 'token_name' not in token or 'token_symbol' not in token:
            continue
            
        if 'token_name' in token:
            token_names.append(token['token_name'])
        if 'token_symbol' in token:
            token_symbols.append(token['token_symbol'])
    
    logger.info(f"Extracted {len(token_names)} token names and {len(token_symbols)} token symbols from SoneFi tokens data")
    return token_names, token_symbols

def extract_coin_symbols(token_data):
    """
    Extract coin symbols from token data
    
    Args:
        token_data (dict): The loaded token data
        
    Returns:
        list: Extracted coin symbols
    """
    coins = []
    if not token_data:
        return coins
    
    for item in token_data:
        if 'symbol' in item:
            # Extract the coin part before /INJ
            symbol = item['symbol'].split('/')[0]
            coins.append(symbol)
    
    logger.info(f"Extracted {len(coins)} coin symbols from token data")
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

# Analysis functionality has been moved to gemini_analyzer.py

async def scrape_twitter_for_coins():
    """
    Scrape Twitter for the coin data from the loaded SoneFi tokens list
    
    Returns:
        bool: True if scraping was successful
    """
    start_time = time.time()
    
    # Load SoneFi tokens instead of tokens_structured.json
    sonefi_tokens = load_sonefi_tokens()
    if not sonefi_tokens:
        logger.error("No SoneFi token data found. Please check sonefi_tokens.json file.")
        return False
    
    # Extract token names and symbols
    _, coin_symbols = extract_sonefi_token_info(sonefi_tokens)
    if not coin_symbols:
        logger.error("No token symbols found in SoneFi token data.")
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
                        
                        # Store raw tweets without analysis - gemini_analyzer.py will be used separately
                        logger.info(f"Stored {len(tweets)} tweets for {coin}")
                        
                        # Mark these tweets as not analyzed yet
                        twitter_data[coin] = [
                            {**tweet, "analyzed": False}
                            for tweet in twitter_data[coin]
                        ]
                    
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
    
    # Just save the tweet data, no analysis (use gemini_analyzer.py separately)
    if twitter_data:
        logger.info(f"Twitter data collection complete. Found tweets for {len(twitter_data)} coins")
        logger.info(f"Twitter data saved to {TWITTER_DATA_FILE}")
        
        # Print summary to console
        print("\n===== TWITTER DATA COLLECTION SUMMARY =====")
        print(f"Collected tweets for {len(twitter_data)} coins")
        total_tweets = sum(len(tweets) for key, tweets in twitter_data.items() 
                          if isinstance(tweets, list) and not key.endswith('_analysis'))
        print(f"Total tweets collected: {total_tweets}")
        print(f"Data saved to: {TWITTER_DATA_FILE}")
        print("\nTo analyze this data, please run gemini_analyzer.py")
        print("===========================================\n")
    
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
    
    logger.info("Starting Twitter coin scraper and data collection")
    success = await scrape_twitter_for_coins()
    
    if success:
        print("\n===== TWITTER DATA COLLECTION COMPLETE =====")
        print("To analyze the collected data, please run:")
        print("python3 gemini_analyzer.py")
        print("===========================================\n")

if __name__ == "__main__":
    asyncio.run(main())