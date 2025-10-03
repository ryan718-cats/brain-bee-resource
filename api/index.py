from vercel_wsgi import make_handler
from app import app

# export handler for Vercel
handler = make_handler(app)
