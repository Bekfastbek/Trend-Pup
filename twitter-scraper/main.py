#!/usr/bin/env python3
"""
Main entry point for the Twitter scraper and cryptocurrency analyzer
Runs the SoneFi scraper every 10 minutes and the Twitter scraper with Gemini analysis every hour
"""

import asyncio
import os
import logging
import sys
import time
import signal
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

# Global flag for graceful shutdown
running = True

def signal_handler(sig, frame):
    """Handle Ctrl+C and other termination signals"""
    global running
    logger.info("Received termination signal. Shutting down gracefully...")
    running = False
    print("\nShutting down gracefully. Please wait...")

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

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

async def run_scheduled_tasks():
    """Run tasks according to schedule"""
    global running
    
    # Track when tasks were last run
    last_sonefi_run = 0
    last_twitter_run = 0
    
    # Time intervals in seconds
    sonefi_interval = 10 * 60  # 10 minutes
    twitter_interval = 60 * 60  # 1 hour
    
    logger.info("Starting scheduled tasks...")
    logger.info(f"SoneFi scraper will run every {sonefi_interval//60} minutes")
    logger.info(f"Twitter scraper and analysis will run every {twitter_interval//60} minutes")
    
    print(f"\n[INFO] Scheduler started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[INFO] SoneFi scraper will run every 10 minutes")
    print(f"[INFO] Twitter scraper + analysis will run every 60 minutes")
    print("[INFO] Press Ctrl+C to stop\n")
    
    # Run SoneFi scraper immediately on startup
    await update_sonefi_data()
    last_sonefi_run = time.time()
    
    try:
        while running:
            current_time = time.time()
            
            # Check if it's time to run the SoneFi scraper
            if current_time - last_sonefi_run >= sonefi_interval:
                logger.info("Running scheduled SoneFi token update...")
                await update_sonefi_data()
                last_sonefi_run = current_time
            
            # Check if it's time to run the Twitter scraper and analysis
            if current_time - last_twitter_run >= twitter_interval:
                logger.info("Running scheduled Twitter scraper and analysis...")
                await run_scraper()
                last_twitter_run = current_time
            
            # Sleep for a bit to avoid high CPU usage
            await asyncio.sleep(30)
            
    except Exception as e:
        logger.error(f"Error in scheduler: {e}", exc_info=True)
        print(f"\n[ERROR] Scheduler encountered an error: {e}")
    
    logger.info("Scheduler stopped")
    print("\n[INFO] Scheduler stopped")

async def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--update-data":
            # Update Sonefi token data only
            await update_sonefi_data()
        elif sys.argv[1] == "--full-run":
            # Run the complete Twitter scraper and analyzer once
            await run_scraper()
        elif sys.argv[1] == "--schedule":
            # Run in scheduled mode
            await run_scheduled_tasks()
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Available options:")
            print("  --update-data  : Update SoneFi token data only")
            print("  --full-run     : Run complete Twitter scraper and analysis once")
            print("  --schedule     : Run in scheduled mode (default)")
    else:
        # Default to scheduled mode
        await run_scheduled_tasks()

if __name__ == "__main__":
    asyncio.run(main())