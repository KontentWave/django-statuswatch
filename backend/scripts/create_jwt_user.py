#!/usr/bin/env python
"""
Create test user for JWT login demo
Usage: python scripts/create_jwt_user.py
"""
import os
import sys
import django

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = "jwt"
email = "jwt@test.local"
password = "JwtP@ss123456"  # Meets complexity: 12+ chars, upper, lower, number, special

user, created = User.objects.get_or_create(
    username=username,
    defaults={
        "email": email,
        "is_active": True,
        "is_staff": False,
        "is_superuser": False,
    }
)

if created:
    user.set_password(password)
    user.save()
    print(f"✅ Created user: {username} / {password}")
else:
    # Update password in case it changed
    user.set_password(password)
    user.save()
    print(f"✅ User already exists: {username} / {password} (password updated)")

print(f"   Email: {email}")
print(f"   Active: {user.is_active}")
print(f"\n🎯 Test login at: POST /api/auth/token/")
print(f"   Body: {{'username': '{username}', 'password': '{password}'}}")
