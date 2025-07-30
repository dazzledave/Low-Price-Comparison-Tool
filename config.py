# Email Configuration for Price Alerts
# Update these settings with your email provider details

# Gmail Settings (recommended)
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USER = 'your-email@gmail.com'  # Replace with your Gmail
EMAIL_PASSWORD = 'your-app-password'  # Replace with your Gmail app password

# Alternative: Outlook/Hotmail
# EMAIL_HOST = 'smtp-mail.outlook.com'
# EMAIL_PORT = 587
# EMAIL_USER = 'your-email@outlook.com'
# EMAIL_PASSWORD = 'your-password'

# Alternative: Yahoo
# EMAIL_HOST = 'smtp.mail.yahoo.com'
# EMAIL_PORT = 587
# EMAIL_USER = 'your-email@yahoo.com'
# EMAIL_PASSWORD = 'your-app-password'

# Price Monitoring Settings
PRICE_CHECK_INTERVAL_HOURS = 6  # How often to check prices (in hours)
MAX_PRICE_CHECKS_PER_RUN = 10   # Maximum alerts to check in one run
DELAY_BETWEEN_CHECKS = 2        # Seconds between checking each alert

# Email Template Settings
SENDER_NAME = 'Pic2Price Price Alerts'
EMAIL_SUBJECT_PREFIX = 'Price Alert:' 