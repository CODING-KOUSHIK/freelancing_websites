"""Drive admin — Google Drive configuration"""
from django.contrib import admin


# No Django models for Drive — it uses SiteSettings from core.
# Admin config is done through SiteSettings (key: google_drive_folder_id, google_service_account_json)
