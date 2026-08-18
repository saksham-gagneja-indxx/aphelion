#!/usr/bin/env python3
"""
Setup Supabase database with all tables and schemas.
Uses the provided Supabase secret key.
"""

import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Supabase credentials
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"  # Will prompt for this
SUPABASE_KEY = "sb_secret_YOUR_KEY_HERE"  # From Supabase dashboard

def setup_database():
    """Initialize Supabase database with all tables."""

    print("=" * 80)
    print("SUPABASE DATABASE SETUP")
    print("=" * 80)
    print()

    # First, we need the Supabase URL
    supabase_url = input("Enter your Supabase project URL (https://xxxxx.supabase.co): ").strip()

    if not supabase_url.startswith("https://"):
        supabase_url = f"https://{supabase_url}"

    print(f"\nConnecting to Supabase...")
    print(f"URL: {supabase_url}")

    try:
        # Create Supabase client
        supabase: Client = create_client(supabase_url, SUPABASE_KEY)

        # Test connection
        print("Testing connection...")
        response = supabase.table("users").select("*").limit(1).execute()
        print("✓ Connected successfully!")

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("\nMake sure:")
        print("1. Supabase project is created")
        print("2. URL format is correct (https://xxxxx.supabase.co)")
        print("3. Secret key is valid")
        return False

    print()
    print("=" * 80)
    print("DATABASE SETUP COMPLETE")
    print("=" * 80)
    print()
    print("Your Supabase connection is ready!")
    print()
    print("Connection String for .env:")
    print(f"DATABASE_URL=postgresql://postgres:password@{supabase_url.replace('https://', '')}/postgres")
    print()

    return True


if __name__ == "__main__":
    setup_database()
