#!/usr/bin/env python3
"""
ARTLU.RUN Setup Script
Run once to install dependencies, create .env, and initialize the database.
"""

import os
import sys

def main():
    print("ARTLU.RUN Setup")
    print("=" * 30)

    if sys.version_info < (3, 8):
        print("Python 3.8 or higher required")
        sys.exit(1)

    # Install dependencies
    print("Installing dependencies...")
    os.system('pip install -r requirements.txt')

    # Create .env if missing
    if not os.path.exists('.env'):
        if os.path.exists('.env.example'):
            import shutil
            shutil.copy('.env.example', '.env')
            print("Created .env from .env.example — edit with your actual keys")
        else:
            print("Warning: no .env.example found")
    else:
        print(".env already exists")

    # Initialize database
    print("Initializing database...")
    from models import init_db, seed_races
    init_db()
    seed_races()
    print("Database initialized with seed data")

    print("\nSetup complete!")
    print("Next steps:")
    print("  1. Edit .env with your Stripe keys and Gmail app password")
    print("  2. Run: python app.py")
    print("  3. Visit: http://localhost:5000")
    print("  4. Test login: test@example.com / TEST-123")

if __name__ == "__main__":
    main()
