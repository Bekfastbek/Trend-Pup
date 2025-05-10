#!/usr/bin/env python3
"""
Main entry point for the Twitter scraper and cryptocurrency analyzer
"""

import asyncio
import os
import logging
import sys
from datetime import datetime

# Set up logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "crypto_analysis.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def print_header():
    """Print a header for the application"""
    print("\n" + "="*60)
    print(" SONEFI CRYPTO TWITTER ANALYZER ".center(60, "="))
    print(" Powered by Gemini AI ".center(60, "="))
    print("="*60)
    print(f" Run started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ".center(60, "-"))
    print("="*60 + "\n")

async def run_scraper():
    """Run the Twitter scraper and analyzer"""
    try:
        # Import here to avoid circular imports
        from twitter import scrape_twitter_for_coins
        from scraper import scrape_sonefi_tokens
        import shutil  # For file copying
        
        print_header()
        logger.info("Starting Sonefi Twitter scraper and analyzer")
        
        # Step 1: Scrape token data from SoneFi
        logger.info("Step 1: Scraping token data from SoneFi...")
        await scrape_sonefi_tokens()
        logger.info("SoneFi token scraping complete")
        
        # Step 2: Run the Twitter scraper and analyzer
        logger.info("Step 2: Scraping Twitter and analyzing tokens...")
        await scrape_twitter_for_coins()
        
        logger.info("Scraping and analysis complete")
        
        # Step 3: Copy output files to the frontend directory
        logger.info("Step 3: Copying data files to frontend directory...")
        frontend_data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                      "frontend", "public", "data")
        
        if not os.path.exists(frontend_data_dir):
            os.makedirs(frontend_data_dir, exist_ok=True)
            logger.info(f"Created directory: {frontend_data_dir}")
        
        # Files to copy
        files_to_copy = [
            "sonefi_tokens.json",
            "coin_investment_analysis.json"
        ]
        
        for filename in files_to_copy:
            src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", filename)
            dest_path = os.path.join(frontend_data_dir, filename)
            
            try:
                if os.path.exists(src_path):
                    shutil.copy2(src_path, dest_path)
                    logger.info(f"Copied {src_path} to {dest_path}")
                else:
                    logger.warning(f"Source file not found: {src_path}")
            except Exception as e:
                logger.error(f"Error copying file {filename}: {e}")
        
        print("\n" + "="*60)
        print(" Analysis complete! ".center(60, "="))
        print(" Data copied to frontend directory ".center(60, "-"))
        print("="*60 + "\n")
    except Exception as e:
        logger.error(f"Error running scraper: {e}", exc_info=True)
        print("\n[ERROR] An error occurred while running the scraper. Check the logs for details.")
        return False
    
    return True

async def update_sonefi_data():
    """Update Sonefi token data by running the scraper"""
    try:
        # Import here to avoid circular imports
        from scraper import scrape_sonefi_tokens_async
        import shutil  # For file copying
        
        print("\n" + "="*60)
        print(" UPDATING SONEFI TOKEN DATA ".center(60, "="))
        print("="*60 + "\n")
        
        logger.info("Starting Sonefi token scraper")
        
        # Run the scraper
        result = await scrape_sonefi_tokens_async()
        
        if result:
            logger.info(f"Successfully scraped {len(result)} Sonefi tokens")
            
            # Copy updated data to frontend directory
            logger.info("Copying updated data to frontend directory...")
            frontend_data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                          "frontend", "public", "data")
            
            if not os.path.exists(frontend_data_dir):
                os.makedirs(frontend_data_dir, exist_ok=True)
                logger.info(f"Created directory: {frontend_data_dir}")
            
            src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sonefi_tokens.json")
            dest_path = os.path.join(frontend_data_dir, "sonefi_tokens.json")
            
            try:
                if os.path.exists(src_path):
                    shutil.copy2(src_path, dest_path)
                    logger.info(f"Copied {src_path} to {dest_path}")
                else:
                    logger.warning(f"Source file not found: {src_path}")
            except Exception as e:
                logger.error(f"Error copying file: {e}")
            
            print(f"\n[SUCCESS] Updated data for {len(result)} Sonefi tokens!")
            print(f"[INFO] Data copied to frontend directory")
        else:
            logger.error("Failed to scrape Sonefi tokens")
            print("\n[ERROR] Failed to update Sonefi token data. Check the logs for details.")
            return False
            
    except Exception as e:
        logger.error(f"Error updating Sonefi data: {e}", exc_info=True)
        print("\n[ERROR] An error occurred while updating Sonefi data. Check the logs for details.")
        return False
        
    return True

async def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == "--update-data":
        # Update Sonefi token data
        await update_sonefi_data()
    else:
        # Run the Twitter scraper and analyzer
        await run_scraper()

if __name__ == "__main__":
    asyncio.run(main())