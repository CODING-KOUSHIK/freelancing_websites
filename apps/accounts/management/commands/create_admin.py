"""
Management command: create_admin
Usage: python manage.py create_admin

Creates a default superuser for the VoiceMarket platform.
Email and password are read from environment variables or use defaults.
"""
import os
from django.core.management.base import BaseCommand
from django.db import IntegrityError


class Command(BaseCommand):
    help = "Create default superadmin user for VoiceMarket"

    def handle(self, *args, **kwargs):
        from apps.accounts.models import CustomUser

        email = os.environ.get("ADMIN_EMAIL", "koushikbiswas029@gmail.com")
        password = os.environ.get("ADMIN_PASSWORD", "Admin@123456")
        full_name = os.environ.get("ADMIN_NAME", "Koushik Biswas")

        if CustomUser.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(
                f"Admin already exists: {email}"
            ))
            # Update password in case it changed
            user = CustomUser.objects.get(email=email)
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.is_verified = True
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"Password updated for: {email}"
            ))
            return

        try:
            user = CustomUser.objects.create_superuser(
                email=email,
                password=password,
                full_name=full_name,
            )
            user.is_verified = True
            user.save(update_fields=["is_verified"])
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ Superadmin created!\n"
                f"   Email:    {email}\n"
                f"   Password: {password}\n"
                f"   Login at: /admin/\n"
            ))
        except IntegrityError as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
