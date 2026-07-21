"""
Management command to test API endpoints
Usage: python manage.py test_api
"""
import requests
import json
from django.core.management.base import BaseCommand
from django.test import Client


class Command(BaseCommand):
    help = 'Test API endpoints'

    def add_arguments(self, parser):
        parser.add_argument(
            '--base-url',
            type=str,
            default='http://localhost:8000',
            help='Base URL for API'
        )

    def handle(self, *args, **options):
        base_url = options['base_url']
        api_base = f"{base_url}/stocks/api/trading"
        
        self.stdout.write(self.style.SUCCESS('Testing API Endpoints...\n'))
        
        # Test client
        client = Client()
        
        # Test 1: List Strategies
        self.stdout.write('1. Testing GET /strategies/')
        try:
            response = client.get(f'{api_base}/strategies/')
            if response.status_code == 200:
                data = json.loads(response.content)
                self.stdout.write(self.style.SUCCESS(f'   ✅ Success: {len(data.get("data", {}).get("strategies", []))} strategies'))
            else:
                self.stdout.write(self.style.ERROR(f'   ❌ Failed: Status {response.status_code}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error: {e}'))
        
        # Test 2: System Status
        self.stdout.write('\n2. Testing GET /status/')
        try:
            response = client.get(f'{api_base}/status/')
            if response.status_code == 200:
                data = json.loads(response.content)
                self.stdout.write(self.style.SUCCESS(f'   ✅ Success: System status retrieved'))
                if 'data' in data:
                    strategies = data['data'].get('strategies', {})
                    self.stdout.write(f'      Strategies: {strategies.get("total", 0)} total, {strategies.get("enabled", 0)} enabled')
            else:
                self.stdout.write(self.style.ERROR(f'   ❌ Failed: Status {response.status_code}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error: {e}'))
        
        # Test 3: List Positions
        self.stdout.write('\n3. Testing GET /positions/')
        try:
            response = client.get(f'{api_base}/positions/')
            if response.status_code == 200:
                data = json.loads(response.content)
                self.stdout.write(self.style.SUCCESS(f'   ✅ Success: {len(data.get("data", {}).get("positions", []))} positions'))
            else:
                self.stdout.write(self.style.ERROR(f'   ❌ Failed: Status {response.status_code}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error: {e}'))
        
        # Test 4: Get Performance
        self.stdout.write('\n4. Testing GET /performance/')
        try:
            response = client.get(f'{api_base}/performance/?days=30')
            if response.status_code == 200:
                data = json.loads(response.content)
                self.stdout.write(self.style.SUCCESS('   ✅ Success: Performance data retrieved'))
            else:
                self.stdout.write(self.style.ERROR(f'   ❌ Failed: Status {response.status_code}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error: {e}'))
        
        # Test 5: Get Risk Exposure
        self.stdout.write('\n5. Testing GET /risk/exposure/')
        try:
            response = client.get(f'{api_base}/risk/exposure/')
            if response.status_code == 200:
                data = json.loads(response.content)
                self.stdout.write(self.style.SUCCESS('   ✅ Success: Risk exposure retrieved'))
            else:
                self.stdout.write(self.style.ERROR(f'   ❌ Failed: Status {response.status_code}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error: {e}'))
        
        self.stdout.write('\n' + self.style.SUCCESS('API Testing Complete!'))
        self.stdout.write(f'\nAPI Base URL: {api_base}')
        self.stdout.write('See API_DOCUMENTATION.md for full endpoint documentation.')
