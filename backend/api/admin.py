from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "email_verified", "email_verification_sent_at", "created_at")
    list_filter = ("email_verified", "created_at")
    search_fields = ("user__email", "user__username")
    readonly_fields = ("email_verification_token", "created_at", "updated_at")

    fieldsets = (
        ("User", {"fields": ("user",)}),
        (
            "Email Verification",
            {
                "fields": (
                    "email_verified",
                    "email_verification_token",
                    "email_verification_sent_at",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
