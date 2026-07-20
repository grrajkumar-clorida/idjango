"""
Simple command to update BREEZE_SESSION in .env file
Usage: python manage.py update_breeze_session
       python manage.py update_breeze_session --session-key YOUR_SESSION_KEY
"""
from django.core.management.base import BaseCommand
from pathlib import Path
import os


class Command(BaseCommand):
    help = "Update BREEZE_SESSION in .env file"
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--session-key',
            type=str,
            help='Breeze API session key to set',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Breeze API Session Key Updater'))
        self.stdout.write('=' * 80)
        
        # Get session key from argument or prompt
        session_key = options.get('session_key')
        
        if not session_key:
            self.stdout.write('\nTo get your session key:')
            self.stdout.write('1. Go to: https://api.icicidirect.com/apiuser/home')
            self.stdout.write('2. Login with your credentials')
            self.stdout.write('3. Find the Session Key on the page')
            self.stdout.write('4. Copy the session key\n')
            
            session_key = input('Enter Breeze API Session Key: ').strip()
        
        if not session_key:
            self.stdout.write(self.style.ERROR('❌ Session key cannot be empty!'))
            return
        
        # Update .env file
        result = self.update_env_file(session_key)
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS('\n✅ SUCCESS!'))
            self.stdout.write('=' * 80)
            self.stdout.write(f'Session key has been updated in .env file')
            self.stdout.write(f'Session Key: {session_key}')
            self.stdout.write(f'File: {result["file_path"]}')
            self.stdout.write('=' * 80)
            
            # Verify
            self.stdout.write('\nVerifying update...')
            from decouple import config
            try:
                updated_key = config('BREEZE_SESSION', default=None)
                if updated_key == session_key:
                    self.stdout.write(self.style.SUCCESS('✓ Verification successful!'))
                else:
                    self.stdout.write(self.style.WARNING('⚠ Verification failed. Please check .env file manually.'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠ Could not verify: {str(e)}'))
        else:
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {result["error"]}'))
    
    def update_env_file(self, session_key):
        """Update BREEZE_SESSION in .env file"""
        try:
            # Find .env file (check multiple locations)
            base_dir = Path(__file__).resolve().parent.parent.parent.parent
            env_file = base_dir / '.env'
            
            # Also check project root
            if not env_file.exists():
                env_file = Path.cwd() / '.env'
            
            # Create if doesn't exist
            if not env_file.exists():
                self.stdout.write(f'\n⚠ .env file not found. Creating new one at {env_file}...')
                with open(env_file, 'w') as f:
                    f.write(f'# Breeze API Configuration\n')
                    f.write(f'BREEZE_SESSION={session_key}\n')
                return {
                    'success': True,
                    'file_path': str(env_file),
                    'action': 'created'
                }
            
            # Read existing .env file
            with open(env_file, 'r') as f:
                lines = f.readlines()
            
            # Update or add BREEZE_SESSION
            updated = False
            new_lines = []
            for line in lines:
                stripped = line.strip()
                # Match BREEZE_SESSION with or without quotes, with or without spaces
                if stripped.startswith('BREEZE_SESSION=') or stripped.startswith('BREEZE_SESSION ='):
                    # Extract existing value to preserve formatting
                    if '=' in stripped:
                        new_lines.append(f'BREEZE_SESSION={session_key}\n')
                    else:
                        new_lines.append(f'BREEZE_SESSION={session_key}\n')
                    updated = True
                else:
                    new_lines.append(line)
            
            if not updated:
                # Add new line at the end
                new_lines.append(f'\n# Breeze API Session Key\n')
                new_lines.append(f'BREEZE_SESSION={session_key}\n')
            
            # Write back to file
            with open(env_file, 'w') as f:
                f.writelines(new_lines)
            
            return {
                'success': True,
                'file_path': str(env_file),
                'action': 'updated' if updated else 'added'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
