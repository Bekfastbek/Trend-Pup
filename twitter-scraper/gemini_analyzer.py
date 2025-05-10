#!/usr/bin/env python3
"""
Gemini AI sentiment analysis module for cryptocurrency tweets.
"""
import json
import logging
import os
import re
import random
import google.generativeai as genai
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "logs", "crypto_analysis.log"))
    ]
)
logger = logging.getLogger(__name__)

# Define data directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "logs"), exist_ok=True)

# Path to Twitter data file
TWITTER_DATA_FILE = os.path.join(DATA_DIR, "twitter_coin_data.json")
# Path to SoneFi tokens file
SONEFI_TOKENS_FILE = os.path.join(DATA_DIR, "sonefi_tokens.json")
# Path to analysis output file
ANALYSIS_OUTPUT_FILE = os.path.join(DATA_DIR, "coin_investment_analysis.json")

# Get Gemini API keys from environment variables
GEMINI_API_KEYS = [
    os.getenv("GEMINI_API_KEY"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3")
]

# Filter out None or empty API keys
GEMINI_API_KEYS = [key for key in GEMINI_API_KEYS if key]

# Validate API keys
if not GEMINI_API_KEYS:
    logger.error("No valid Gemini API keys found in environment variables")
else:
    logger.info(f"Found {len(GEMINI_API_KEYS)} Gemini API keys")

def analyze_sentiment_with_gemini(tweets_text, coin_symbol):
    """
    Analyze tweet sentiment using Google's Gemini API
    Returns a dict with sentiment score and investment analysis
    
    Args:
        tweets_text (str): The concatenated text of tweets to analyze
        coin_symbol (str): The cryptocurrency symbol being analyzed
        
    Returns:
        dict: Analysis results containing sentiment_score, investment_analysis, and key_factors
    """
    if not tweets_text:
        logger.warning(f"No tweets to analyze for {coin_symbol}")
        return {"sentiment_score": 0, "analysis": "No data available"}
    
    # Rotate through available API keys to avoid rate limits
    api_key = random.choice(GEMINI_API_KEYS)
    genai.configure(api_key=api_key)
    
    try:
        # Configure the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Create the prompt for Gemini
        prompt = f"""
        Analyze the following tweets about the cryptocurrency {coin_symbol} for investment sentiment.
        
        Tweets:
        {tweets_text}
        
        Please provide:
        1. A sentiment score from -1.0 (extremely negative) to 1.0 (extremely positive)
        2. A brief analysis of why this cryptocurrency might be a good or bad investment based on these tweets
        3. Key factors mentioned in the tweets that could affect the price
        4. Risk assessment on a scale of 0-10 (where 0 is lowest risk and 10 is highest risk)
        5. Growth potential on a scale of 0-10 (where 0 is lowest potential and 10 is highest potential)
        
        Format your response as JSON only, with the following structure:
        {{
            "sentiment_score": [score as a float],
            "investment_analysis": "[brief analysis]",
            "key_factors": ["factor1", "factor2", ...],
            "risk_rating": [risk as an integer 0-10],
            "potential_rating": [potential as an integer 0-10]
        }}
        """
        
        # Generate the response
        response = model.generate_content(prompt)
        
        # Parse the response as JSON
        response_text = response.text
        # Extract JSON if surrounded by markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        try:
            result = json.loads(response_text)
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing Gemini response as JSON: {e}")
            logger.error(f"Response was: {response_text}")
            
            # Fallback to simple sentiment extraction
            if isinstance(response_text, str) and "sentiment_score" in response_text:
                try:
                    # Try to extract just the sentiment score with regex
                    match = re.search(r'"sentiment_score"\s*:\s*([-+]?\d*\.\d+|\d+)', response_text)
                    if match:
                        sentiment_score = float(match.group(1))
                        return {
                            "sentiment_score": sentiment_score, 
                            "analysis": "Partial analysis only",
                            "risk_rating": 5,  # Default middle value
                            "potential_rating": 5  # Default middle value
                        }
                except Exception:
                    pass
                    
            return {
                "sentiment_score": 0, 
                "analysis": "Failed to parse analysis",
                "risk_rating": 5,  # Default middle value
                "potential_rating": 5  # Default middle value
            }
    
    except Exception as e:
        logger.error(f"Error calling Gemini API for {coin_symbol}: {e}")
        return {
            "sentiment_score": 0, 
            "analysis": f"API error: {str(e)}",
            "risk_rating": 5,  # Default middle value
            "potential_rating": 5  # Default middle value
        }

def load_twitter_data():
    """
    Load the Twitter data from the JSON file
    
    Returns:
        dict: The loaded Twitter data or an empty dict if error
    """
    try:
        with open(TWITTER_DATA_FILE, 'r', encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading Twitter data: {e}")
        return {}

def load_sonefi_tokens():
    """
    Load token data from sonefi_tokens.json
    
    Returns:
        list: Loaded SoneFi token data or empty list if error
    """
    try:
        with open(SONEFI_TOKENS_FILE, 'r', encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading sonefi_tokens.json: {e}")
        return []

def create_token_metrics_map(sonefi_tokens):
    """
    Create a map of token symbols to their metrics from SoneFi data
    
    Args:
        sonefi_tokens (list): List of SoneFi token data
        
    Returns:
        dict: Map of token symbols to their metrics
    """
    token_metrics = {}
    
    for token in sonefi_tokens:
        if "token_symbol" not in token:
            continue
            
        symbol = token["token_symbol"]
        token_metrics[symbol] = {
            "price_value": token.get("price_value", 0),
            "market_cap": token.get("market_cap", 0),
            "virtual_liquidity": token.get("virtual_liquidity", 0),
            "volume_24h": token.get("24h_volume", 0),
            "price_change_percentage": token.get("price_change_percentage", 0),
            "token_age_days": token.get("token_age_days", 0),
        }
    
    logger.info(f"Created token metrics map with {len(token_metrics)} tokens")
    return token_metrics

def calculate_fundamental_metrics(token_metrics, symbol):
    """
    Calculate fundamental risk and potential metrics based on token data
    
    Args:
        token_metrics (dict): Map of token symbols to their metrics
        symbol (str): The token symbol to analyze
        
    Returns:
        tuple: (risk_score, potential_score) as floats from 0-10
    """
    # Default values if we can't find the token in our metrics
    if symbol not in token_metrics:
        return 5.0, 5.0
    
    metrics = token_metrics[symbol]
    
    # Get token metrics with safe defaults
    market_cap = metrics.get("market_cap", 0)
    liquidity = metrics.get("virtual_liquidity", 0)
    volume_24h = metrics.get("volume_24h", 0)
    price_change = metrics.get("price_change_percentage", 0)
    token_age = metrics.get("token_age_days", 0)
    
    # Risk calculation (lower is better)
    # Very new tokens, low liquidity, and extreme price changes increase risk
    risk_score = 5.0
    
    # Age factor (newer = riskier)
    if token_age < 3:
        risk_score += 3  # Very new tokens are high risk
    elif token_age < 7:
        risk_score += 2  # Week-old tokens are risky
    elif token_age < 30:
        risk_score += 1  # Month-old tokens are somewhat risky
    
    # Liquidity factor (lower liquidity = higher risk)
    if liquidity < 1000:
        risk_score += 3
    elif liquidity < 5000:
        risk_score += 1.5
    
    # Market cap factor (lower market cap = higher risk)
    if market_cap < 1000:
        risk_score += 2
    elif market_cap < 10000:
        risk_score += 1
    
    # Extreme price change factor
    if abs(price_change) > 20:
        risk_score += 1.5
    
    # Potential calculation
    potential_score = 5.0
    
    # Small market cap has higher growth potential
    if market_cap < 10000:
        potential_score += 2
    elif market_cap < 100000:
        potential_score += 1
    
    # Price movement indicates momentum
    if price_change > 5:
        potential_score += 1
    elif price_change > 15:
        potential_score += 1.5
    
    # Higher volume relative to market cap indicates interest
    volume_to_mcap = (volume_24h / market_cap) * 100 if market_cap > 0 else 0
    if volume_to_mcap > 5:
        potential_score += 2
    elif volume_to_mcap > 1:
        potential_score += 1
        
    # Normalize scores to 0-10 range
    risk_score = max(0, min(10, risk_score))
    potential_score = max(0, min(10, potential_score))
    
    return risk_score, potential_score

def analyze_coin_data(twitter_data, sonefi_tokens):
    """
    Process and analyze the Twitter data for all coins
    
    Args:
        twitter_data (dict): Twitter data organized by coin symbol
        sonefi_tokens (list): SoneFi token data
        
    Returns:
        dict: Analysis results for each coin and top coins recommendation
    """
    if not twitter_data:
        logger.error("No Twitter data to analyze")
        return {"top_coins": [], "coin_analysis": {}}
    
    # Create token metrics map from SoneFi data
    token_metrics = create_token_metrics_map(sonefi_tokens)
    
    analyzed_coins = {}
    coins_with_tweets = [coin for coin in twitter_data.keys() if isinstance(twitter_data[coin], list)]
    
    logger.info(f"Analyzing tweets for {len(coins_with_tweets)} coins")
    
    for coin_symbol in coins_with_tweets:
        tweets = twitter_data[coin_symbol]
        if not tweets:
            logger.warning(f"No tweets found for {coin_symbol}")
            continue
        
        logger.info(f"Analyzing {len(tweets)} tweets for {coin_symbol}")
        
        # Concatenate all tweet texts
        tweets_text = "\n---\n".join([tweet.get('text', '') for tweet in tweets if tweet.get('text')])
        
        # Skip if no text to analyze
        if not tweets_text.strip():
            logger.warning(f"No tweet text to analyze for {coin_symbol}")
            continue
            
        # Calculate fundamental metrics from SoneFi data
        fundamental_risk, fundamental_potential = calculate_fundamental_metrics(token_metrics, coin_symbol)
        
        # Analyze sentiment with Gemini
        analysis = analyze_sentiment_with_gemini(tweets_text, coin_symbol)
        
        # If token exists in SoneFi data, blend AI sentiment with fundamental metrics
        if coin_symbol in token_metrics:
            # Get AI ratings, use defaults if not present
            ai_risk = analysis.get("risk_rating", 5)
            ai_potential = analysis.get("potential_rating", 5)
            
            # Blend fundamental and AI ratings (60% fundamental, 40% AI)
            final_risk = (fundamental_risk * 0.6) + (ai_risk * 0.4)
            final_potential = (fundamental_potential * 0.6) + (ai_potential * 0.4)
            
            # Update the analysis with blended ratings
            analysis["risk_rating"] = round(final_risk, 1)
            analysis["potential_rating"] = round(final_potential, 1)
            
            # Add fundamental data
            analysis["fundamental_metrics"] = token_metrics[coin_symbol]
        
        # Store the analysis
        analyzed_coins[coin_symbol] = {
            "analysis": analysis,
            "tweet_count": len(tweets),
            "last_analyzed": datetime.now().isoformat()
        }
        
        logger.info(f"Analysis complete for {coin_symbol} with sentiment score: {analysis.get('sentiment_score', 0)} "
                  f"risk: {analysis.get('risk_rating', 'N/A')} potential: {analysis.get('potential_rating', 'N/A')}")
    
    # Sort coins by a combined score of high potential and low risk
    # Formula: potential_rating - (risk_rating * 0.5) + sentiment_score
    sorted_coins = sorted(
        [{"symbol": symbol, **data} for symbol, data in analyzed_coins.items()],
        key=lambda x: (
            float(x.get("analysis", {}).get("potential_rating", 5)) - 
            (float(x.get("analysis", {}).get("risk_rating", 5)) * 0.5) + 
            float(x.get("analysis", {}).get("sentiment_score", 0))
        ),
        reverse=True
    )
    
    # Get top coins (up to 10)
    top_coins = sorted_coins[:10]
    top_coin_symbols = [coin["symbol"] for coin in top_coins]
    
    logger.info(f"Top {len(top_coin_symbols)} coins: {top_coin_symbols}")
    
    # Prepare the final analysis data
    analysis_data = {
        "top_coins": top_coin_symbols,
        "coin_analysis": analyzed_coins,
        "analysis_timestamp": datetime.now().isoformat()
    }
    
    return analysis_data

def save_analysis_data(analysis_data):
    """
    Save the analysis data to a JSON file
    
    Args:
        analysis_data (dict): The analysis data to save
    """
    try:
        with open(ANALYSIS_OUTPUT_FILE, 'w', encoding="utf-8") as f:
            json.dump(analysis_data, f, indent=2)
        logger.info(f"Analysis data saved to {ANALYSIS_OUTPUT_FILE}")
    except Exception as e:
        logger.error(f"Error saving analysis data: {e}")

def main():
    """
    Main function to load Twitter data and analyze it with Gemini
    """
    logger.info("Starting Gemini sentiment analysis for cryptocurrency tweets")
    
    # Verify we have API keys
    if not GEMINI_API_KEYS:
        logger.error("No Gemini API keys provided. Please add them to your environment variables.")
        return
    
    # Load Twitter data
    twitter_data = load_twitter_data()
    if not twitter_data:
        logger.error("No Twitter data found. Please run twitter.py first.")
        return
    
    # Load SoneFi token data
    sonefi_tokens = load_sonefi_tokens()
    if not sonefi_tokens:
        logger.warning("No SoneFi token data found. Will rely solely on sentiment analysis.")
    
    # Analyze the Twitter data with SoneFi token data
    analysis_data = analyze_coin_data(twitter_data, sonefi_tokens)
    
    # Save the analysis data
    save_analysis_data(analysis_data)
    
    # Print summary to console
    print("\n===== TOP COINS TO INVEST IN =====")
    for i, coin in enumerate(analysis_data.get("top_coins", []), 1):
        coin_analysis = analysis_data.get("coin_analysis", {}).get(coin, {}).get("analysis", {})
        sentiment = coin_analysis.get("sentiment_score", 0)
        risk = coin_analysis.get("risk_rating", "N/A")
        potential = coin_analysis.get("potential_rating", "N/A")
        investment_analysis = coin_analysis.get("investment_analysis", "No analysis available")
        
        print(f"{i}. {coin} (Sentiment: {sentiment:.2f}, Risk: {risk}, Potential: {potential})")
        print(f"   {investment_analysis[:100]}...")
    print("=================================\n")

if __name__ == "__main__":
    main()