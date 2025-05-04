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

# Load environment variables from .env file
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Define data directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)

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
        
        Format your response as JSON only, with the following structure:
        {{
            "sentiment_score": [score as a float],
            "investment_analysis": "[brief analysis]",
            "key_factors": ["factor1", "factor2", ...]
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
                        return {"sentiment_score": sentiment_score, "analysis": "Partial analysis only"}
                except Exception:
                    pass
                    
            return {"sentiment_score": 0, "analysis": "Failed to parse analysis"}
    
    except Exception as e:
        logger.error(f"Error calling Gemini API for {coin_symbol}: {e}")
        return {"sentiment_score": 0, "analysis": f"API error: {str(e)}"}