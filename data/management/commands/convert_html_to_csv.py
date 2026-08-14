import os
import re
import json
import pandas as pd
import logging
from django.core.management.base import BaseCommand
from data.models import Source #Stock50MA
from django.conf import settings
from datetime import datetime

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Extract JSON data from HTML, save as CSV, and store in database"

    def handle(self, *args, **kwargs):
        file_path = os.path.join(settings.MEDIA_ROOT, "result_1.html")  # ✅ Correct file system path
        output_csv = "/home/gr8/Documents/gr8/processed_stock_data.csv"  # Update path
                
    # Initialize empty list for collected data
    all_data = []
    source_dir = os.path.join(settings.MEDIA_ROOT)
    output_json = "/home/gr8/Documents/gr8/imp_output.json"
    print('Convert CSV to Data Proces Staring!')

    # df = calculate_50ma()
    # print(df)
    # exit()

    #send_telegram_message("⚡ Fetching price data started...")

    # Process HTML files
    def process_html(file_path):
        """Extract JSON data from an HTML file."""
        with open(file_path, "r", encoding="utf-8") as file:
            html_content = file.read()
            logger.info("Cron job executed successfully!")
        # Extract JSON using regex
        json_pattern = re.search(r"var jsonData = (\[.*?\]);", html_content, re.DOTALL)
        if json_pattern:
            json_data = json_pattern.group(1).replace("'", '"')  # Fix quotes
            try:
                row_data = json.loads(json_data)
                
                return json.loads(json_data), "HalfBat"  # Convert JSON string to Python object
            except json.JSONDecodeError:
                print(f"Error decoding JSON in {file_path}")

        return []

    # Process CSV files
    def process_csv(file_path):
        print('CSV process starting', file_path)
        """Convert CSV file to JSON format."""
        df = pd.read_csv(file_path)
        
        # Fix Date Fields
        for col in ["startDate", "endDate"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().replace("“", "").replace("”", "")
        print('CSV processed!')
        return df.to_dict(orient="records"), "50MA"  # Convert DataFrame to JSON list

    # Step 1:  
    #Iterate over files in source directory
    for filename in os.listdir(source_dir):
        file_path = os.path.join(source_dir, filename)
        logger.info(f"Cron job fielpath: {file_path}")

        if filename.endswith(".html"):
            logger.info(f"Cron job html: {file_path}")
            print(f'Process start with file Name: {filename}')
            data, trade_value = process_html(file_path) #
        elif filename.endswith(".csv"):
            logger.info(f"Cron job csv: {file_path}")
            print(f'Process start with file Name: {filename}')
            data, trade_value = process_csv(file_path)
        else:
            continue

        # Save each row with raw JSON data        
        for row in data:
            print(trade_value)
            if trade_value == 'HalfBat':
                logger.info(f"Cron job trade_value: {trade_value}")
                code = row.get("script", "Unknown HalfBat")
                market =row.get("market", "Unknown")
                price =row.get('entry', 0)
            else:
                logger.info(f"Cron job trade_value: {trade_value}")
                code = row.get("Symbol", "Unknown 50")
                market =row.get("market", "Equity")
                price =row.get('Price', 0)
            
            try:
                stock_entry = Source(
                    script = code,  # Default to 'Unknown' if missing
                    trade = trade_value,
                    market = market, #row.get("market", "Unknown"),
                    price = price, #row.get('startPrice', 0),
                    status = "open",  # Default status
                    raw_data = row,  # Store the full row as JSON
                    notes = 'Import raw data from Source',
                )
                print(code)
                stock_entry.save()
            except Exception as e:
                logger.info(f"Cron job faild!:{row}, Error: {e} ")
                print(f"Error saving row: {row}, Error: {e}")

        print('Data Imported successfully!', len(data))