Render / Heroku deployment notes

1) Environment variables
- Set GROQ_API_KEY in the service's environment settings.
- Optional: GROQ_DEFAULT_MODEL

2) Using Render (recommended for this app)
- Create a new Web Service on Render and connect it to this repository.
- Set the build command to: pip install -r requirements.txt
- Render will use the Procfile by default: `web: gunicorn app:app --bind 0.0.0.0:$PORT`
- Deploy and open the generated URL.

3) Using Vercel (serverless)
- Possible but subject to function timeouts. If you prefer Vercel, consider migrating the model call to a background worker or using a different host.

4) Notes
- Do not commit secrets. Use the provider's environment variable settings.
- If you see issues on first deploy, check the service logs for missing env vars or dependency install errors.
