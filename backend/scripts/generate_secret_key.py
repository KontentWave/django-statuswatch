#!/usr/bin/env python3
"""
Generate a secure Django SECRET_KEY.

Usage:
    python scripts/generate_secret_key.py

This will output a cryptographically secure random key suitable for production use.
Copy the output and set it as SECRET_KEY in your .env file.
"""

from django.core.management.utils import get_random_secret_key

if __name__ == "__main__":
    key = get_random_secret_key()
    print("\n" + "=" * 80)
    print("Generated SECRET_KEY:")
    print("=" * 80)
    print(f"\nSECRET_KEY={key}\n")
    print("=" * 80)
    print("\nAdd this line to your .env file (DO NOT commit to git!)")
    print("=" * 80 + "\n")
