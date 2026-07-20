import re
import json
import os
import pandas as pd
from django.core.management.base import BaseCommand
from data.models import Stock50MA
from django.conf import settings
from datetime import datetime

class Command(BaseCommand):
    help = "Extract JSON data from HTML, save as CSV, and store in database"

    def handle(self, *args, **kwargs):
        
        file_path = os.path.join(settings.MEDIA_ROOT, "result_1.html")  # ✅ Correct file system path
        output_csv = "/home/gr8/Documents/gr8/processed_stock_data.csv"  # Update path

        try:
            # Read the HTML file
            with open(file_path, "r", encoding="utf-8") as file:
                html_content = file.read()

            # Extract the JSON data using regex
            json_pattern = re.search(r"var jsonData = (\[.*?\]);", html_content, re.DOTALL)
            if json_pattern:
                json_data = json_pattern.group(1).replace("'", '"')  # Replace ' with " for valid JSON format
                stock_data = json.loads(json_data)  # Convert JSON string to Python object
            else:
                raise ValueError("JSON data not found in the HTML file.")
            
            # Convert to Pandas DataFrame
            df = pd.DataFrame(stock_data)

            def clean_date(date_str):
                """Remove spaces and convert date to YYYY-MM-DD format."""
                date_str = date_str.strip().replace("“", "").replace("”", "")  # Remove special quotes
                return datetime.strptime(date_str, "%Y-%m-%d").date()

            df["startDate"] = df["startDate"].apply(clean_date)
            df["endDate"] = df["endDate"].apply(clean_date)

            # Compute 50-day moving average (if applicable)
            if 'entry' in df.columns:
                df['50_MA'] = df['entry'].rolling(window=50, min_periods=1).mean()

            # Save to CSV
            #df.to_csv(output_csv, index=False)
            
            # Store in Database
            #Stock50MA.objects.all().delete()  # Optional: Clear previous data before inserting new
            stock_records = [
                Stock50MA(
                    script=row["script"],
                    start_date=row["startDate"],
                    start_swing=row["startSwing"],
                    start_price=row["startPrice"],
                    end_date=row["endDate"],
                    end_swing=row["endSwing"],
                    end_price=row["endPrice"],
                    entry=row["entry"],
                    sl=row["sl"],
                    window=row["window"],
                    period=row["period"],
                    direction=row["direction"],
                    market=row["market"],
                    moving_average_50=row.get("50_MA")  # Add moving average if available
                ) 
                for _, row in df.iterrows()
            ]
            Stock50MA.objects.bulk_create(stock_records)
            
            self.stdout.write(self.style.SUCCESS(f"CSV file saved and data stored in DB successfully."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
