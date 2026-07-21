"""
Management command to automatically login to Breeze API and update session key in .env
NOTE: For manual login, use: python manage.py update_breeze_session
Usage: python manage.py get_breeze_session
"""
import os
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from django.core.management.base import BaseCommand
from decouple import config
from pathlib import Path


class Command(BaseCommand):
    help = "Automatically login to Breeze API and update session key in .env file"
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--headless',
            action='store_true',
            help='Run browser in headless mode',
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Breeze API username (or set BREEZE_USERNAME in .env)',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Breeze API password (or set BREEZE_PASSWORD in .env)',
        )
        parser.add_argument(
            '--api-key',
            type=str,
            help='Breeze API key (or set BREEZE_API_KEY in .env)',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Breeze API session retrieval...'))
        
        # Get credentials
        username = options.get('username') or config('BREEZE_USERNAME', default=None)
        password = options.get('password') or config('BREEZE_PASSWORD', default=None)
        api_key = options.get('api_key') or config('BREEZE_API_KEY', default=None)
        
        if not username or not password:
            self.stdout.write(
                self.style.ERROR(
                    'Username and password are required. '
                    'Provide via --username/--password or set BREEZE_USERNAME/BREEZE_PASSWORD in .env'
                )
            )
            return
        
        if not api_key:
            self.stdout.write(
                self.style.WARNING(
                    'API key not provided. Will try to extract from page.'
                )
            )
        
        # Setup Chrome options
        chrome_options = Options()
        if options.get('headless'):
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver = None
        try:
            self.stdout.write('Initializing browser...')
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Navigate to Breeze API login page
            self.stdout.write('Navigating to Breeze API login page...')
            driver.get('https://api.icicidirect.com/apiuser/home')
            
            # Wait for page to load
            time.sleep(3)
            
            # Try to find and fill login form
            self.stdout.write('Looking for login form...')
            
            # Wait for login elements (adjust selectors based on actual page structure)
            try:
                # Try to find username/email field
                username_selectors = [
                    "input[name='username']",
                    "input[name='email']",
                    "input[type='text']",
                    "input[id*='user']",
                    "input[id*='email']",
                    "#username",
                    "#email"
                ]
                
                username_field = None
                for selector in username_selectors:
                    try:
                        username_field = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        break
                    except TimeoutException:
                        continue
                
                if not username_field:
                    # Try by XPath
                    username_field = driver.find_element(By.XPATH, "//input[@type='text' or @type='email']")
                
                username_field.clear()
                username_field.send_keys(username)
                self.stdout.write(self.style.SUCCESS('✓ Username entered'))
                
                # Find password field
                password_selectors = [
                    "input[name='password']",
                    "input[type='password']",
                    "#password"
                ]
                
                password_field = None
                for selector in password_selectors:
                    try:
                        password_field = driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except NoSuchElementException:
                        continue
                
                if not password_field:
                    password_field = driver.find_element(By.XPATH, "//input[@type='password']")
                
                password_field.clear()
                password_field.send_keys(password)
                self.stdout.write(self.style.SUCCESS('✓ Password entered'))
                
                # Find and click login button
                login_selectors = [
                    "button[type='submit']",
                    "input[type='submit']",
                    "button:contains('Login')",
                    "button:contains('Sign in')",
                    ".btn-primary",
                    "#login",
                    "#submit"
                ]
                
                login_button = None
                for selector in login_selectors:
                    try:
                        login_button = driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except NoSuchElementException:
                        continue
                
                if not login_button:
                    # Try by text
                    login_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Login') or contains(text(), 'Sign in')]")
                
                login_button.click()
                self.stdout.write(self.style.SUCCESS('✓ Login button clicked'))
                
                # Wait for page to load after login
                time.sleep(5)
                
                # Check if login was successful
                current_url = driver.current_url
                self.stdout.write(f'Current URL: {current_url}')
                
                # Try to find session key on the page
                page_source = driver.page_source
                
                # Look for session key patterns
                session_patterns = [
                    r'session[_\s]*key[:\s]*([A-Za-z0-9]+)',
                    r'session[_\s]*token[:\s]*([A-Za-z0-9]+)',
                    r'Session[_\s]*Key[:\s]*([A-Za-z0-9]+)',
                    r'<input[^>]*value=["\']([A-Za-z0-9]{8,})["\']',
                    r'<span[^>]*>([A-Za-z0-9]{8,})</span>',
                    r'<td[^>]*>([A-Za-z0-9]{8,})</td>',
                ]
                
                session_key = None
                for pattern in session_patterns:
                    matches = re.findall(pattern, page_source, re.IGNORECASE)
                    if matches:
                        # Take the longest match (likely the session key)
                        session_key = max(matches, key=len)
                        if len(session_key) >= 8:  # Session keys are usually at least 8 chars
                            break
                
                # Also try to find in specific elements
                if not session_key:
                    try:
                        # Look for elements that might contain session key
                        session_elements = driver.find_elements(By.XPATH, 
                            "//*[contains(text(), 'Session') or contains(text(), 'session')]")
                        for elem in session_elements:
                            text = elem.text
                            # Extract alphanumeric sequence
                            match = re.search(r'([A-Za-z0-9]{8,})', text)
                            if match:
                                session_key = match.group(1)
                                break
                    except:
                        pass
                
                # If still not found, check URL parameters
                if not session_key:
                    if 'session' in current_url.lower():
                        match = re.search(r'session[=:]([A-Za-z0-9]+)', current_url, re.IGNORECASE)
                        if match:
                            session_key = match.group(1)
                
                if session_key:
                    self.stdout.write(self.style.SUCCESS(f'✓ Session key found: {session_key[:10]}...'))
                    
                    # Update .env file
                    self.update_env_file(session_key)
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'\n✅ Successfully updated BREEZE_SESSION in .env file!\n'
                            f'Session key: {session_key}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            '\n⚠ Session key not found automatically.\n'
                            'Please check the page manually and update .env file.\n'
                            'Page source saved to: breeze_page_source.html'
                        )
                    )
                    # Save page source for debugging
                    with open('breeze_page_source.html', 'w', encoding='utf-8') as f:
                        f.write(page_source)
                    
                    # Interactive mode
                    self.stdout.write('\nPlease enter the session key manually:')
                    manual_key = input('Session Key: ').strip()
                    if manual_key:
                        self.update_env_file(manual_key)
                        self.stdout.write(self.style.SUCCESS('✓ Session key updated!'))
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error during login process: {str(e)}')
                )
                self.stdout.write('\nPage source saved to: breeze_page_source.html')
                with open('breeze_page_source.html', 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                raise
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {str(e)}')
            )
            return
        
        finally:
            if driver:
                self.stdout.write('Closing browser...')
                driver.quit()
    
    def update_env_file(self, session_key):
        """Update BREEZE_SESSION in .env file"""
        # Find .env file
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        env_file = base_dir / '.env'
        
        if not env_file.exists():
            self.stdout.write(
                self.style.WARNING(f'.env file not found at {env_file}. Creating new one...')
            )
            # Create new .env file
            with open(env_file, 'w') as f:
                f.write(f'BREEZE_SESSION={session_key}\n')
            return
        
        # Read existing .env file
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Update or add BREEZE_SESSION
        updated = False
        new_lines = []
        for line in lines:
            if line.strip().startswith('BREEZE_SESSION='):
                new_lines.append(f'BREEZE_SESSION={session_key}\n')
                updated = True
            else:
                new_lines.append(line)
        
        if not updated:
            # Add new line
            new_lines.append(f'BREEZE_SESSION={session_key}\n')
        
        # Write back to file
        with open(env_file, 'w') as f:
            f.writelines(new_lines)
        
        self.stdout.write(self.style.SUCCESS(f'✓ Updated .env file at {env_file}'))
