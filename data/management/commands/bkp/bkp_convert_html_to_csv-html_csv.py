import os
import re
import json
import pandas as pd
from django.core.management.base import BaseCommand
from data.models import Import #Stock50MA
from django.conf import settings
from datetime import datetime

class Command(BaseCommand):
    help = "Extract JSON data from HTML, save as CSV, and store in database"

    def handle(self, *args, **kwargs):
    
        
        file_path = os.path.join(settings.MEDIA_ROOT, "result_1.html")  # ✅ Correct file system path
        output_csv = "/home/gr8/Documents/gr8/processed_stock_data.csv"  # Update path
    
            
    # Initialize empty list for collected data
    all_data = []
    source_dir = os.path.join(settings.MEDIA_ROOT)
    output_json = "/home/gr8/Documents/gr8/imp_output.json"
    
    def storeData(raw_data, method):
        print('Sttt Data')
        stock_data = raw_data #json.loads(raw_data)  # Convert JSON string to Python object
        # Convert to Pandas DataFrame
        df = pd.DataFrame(stock_data)
        #json_str = df.to_json(orient='records')
        #print(type(json_str), json_str)
        
        # Compute 50-day moving average (if applicable)
        if 'entry' in df.columns:
            ma50 = df['entry'].rolling(window=50, min_periods=1).mean()
            print(df['entry'])
            exit()
        # Store in Database
            #Stock50MA.objects.all().delete()  # Optional: Clear previous data before inserting new
            stock_records = [
                Import(
                    script=row["script"],
                    trade = method,
                    price = row["startPrice"],
                    market = row["market"],
                    notes = 'Import raw data',
                    raw_data = row
                    
                ) 
                for _, row in df.iterrows()
            ]
            Import.objects.bulk_create(stock_records)

    # Process HTML files
    def process_html(file_path):
        """Extract JSON data from an HTML file."""
        with open(file_path, "r", encoding="utf-8") as file:
            html_content = file.read()

        # Extract JSON using regex
        json_pattern = re.search(r"var jsonData = (\[.*?\]);", html_content, re.DOTALL)
        if json_pattern:
            json_data = json_pattern.group(1).replace("'", '"')  # Fix quotes
            
                #data, script, market, price, 
            try: #script, market, price,
                row_data = json.loads(json_data)
                
                return json.loads(json_data), "HalfBat"  # Convert JSON string to Python object
            except json.JSONDecodeError:
                print(f"Error decoding JSON in {file_path}")

        return []

    # Process CSV files
    def process_csv(file_path):
        """Convert CSV file to JSON format."""
        print('csv procrsss@')
        df = pd.read_csv(file_path)
        
        # Fix Date Fields
        for col in ["startDate", "endDate"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().replace("“", "").replace("”", "")

        return df.to_dict(orient="records"), "50MA"  # Convert DataFrame to JSON list

    

    # Iterate over files in source directory
    for filename in os.listdir(source_dir):
        file_path = os.path.join(source_dir, filename)

        if filename.endswith(".htmls"):
            print(f"Processing HTML file: {filename}")
            #data, trade_value = process_html(file_path) #script, market, price,
            #storeData(process_html(file_path), 'Halfbat' )
        elif filename.endswith(".csv"):
            print(f"Processing CSV file: {filename}")
            data, trade_value = process_csv(file_path)
            #all_data.extend(process_csv(file_path))
            #print('ddd', process_csv(file_path))
            #storeData(process_csv(file_path), '50MA' )
        else:
            continue

        # Save each row with raw JSON data
        
        for row in data:
            if trade_value == 'Halfbat':
                code = row.get("script", "Unknown")
                market =row.get("market", "Unknown")
                price =row.get('entry', 0)
            else:
                code = row.get("Symbol", "Unknown")
                market =row.get("market", "Equity")
                price =row.get('Price', 0)
            
            try:
                stock_entry = Import(
                    script = code,  # Default to 'Unknown' if missing
                    trade = trade_value,
                    market =market, #row.get("market", "Unknown"),
                    price = price, #row.get('startPrice', 0),
                    status ="open",  # Default status
                    raw_data =row,  # Store the full row as JSON
                    notes = 'Import raw data from Source',
                )
                stock_entry.save()
                #self.stdout.write(self.style.SUCCESS(f"Saved: {stock_entry}"))
            except Exception as e:
                print('ffff', {e})
                #self.stderr.write(self.style.ERROR(f"Error saving row: {row}, Error: {e}"))

'''    # Save all extracted data into a single JSON file
    with open(output_json, "w", encoding="utf-8") as json_file:
        json.dump(all_data, json_file, indent=4)

        print(f"Data processed and saved to: {output_json}")

        try:
            # Read the HTML file
            with open(file_path, "r", encoding="utf-8") as file:
                html_content = file.read()
            # Extract the JSON data using regex
            json_pattern = re.search(r"var jsonData = (\[.*?\]);", html_content, re.DOTALL)
            if json_pattern:
                json_data = json_pattern.group(1).replace("'", '"') # Replace ' with " for valid JSON format
                stock_data = json.loads(json_data)  # Convert JSON string to Python object
            else:
                raise ValueError("JSON data not found in the HTML file.")
            if file == 'html':
                raw_data, method, market = json_data, 'Halfbat',  'NSE'
            else:
                raw_data, method, market = json_data, '50Ma',  'NSE'
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
                Import(
                    script=row["script"],
                    trade = method,
                    price = row["startPrice"],
                    market = row["market"],
                    notes = 'Import raw data',
                    raw_data = raw_data
                    
                ) 
                for _, row in df.iterrows()
            ]
            Import.objects.bulk_create(stock_records)

            self.stdout.write(self.style.SUCCESS(f"CSV file saved and data stored in DB successfully."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
'''