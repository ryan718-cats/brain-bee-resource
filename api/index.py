from app import app

# Export the Flask app for Vercel
# No need for vercel_wsgi or make_handler
app = app