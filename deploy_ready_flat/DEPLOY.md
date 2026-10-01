# Put the dashboard online (free) with Streamlit Community Cloud

1. Create a GitHub account and a NEW repository (Private is fine).
2. Upload all files from this folder to the repo (drag and drop in GitHub).
   Do NOT upload .env or any file that contains a key.
3. Go to https://share.streamlit.io and sign in with GitHub.
4. Click "Create app" -> pick your repo, branch "main", main file "streamlit_app.py" -> Advanced settings -> Secrets.
5. Paste (with your NEW key and a password):
       SCRAPER_PROVIDER = "scrapecreators"
       SCRAPECREATORS_API_KEY = "your_new_key"
       APP_PASSWORD = "a_strong_password"
6. Click Deploy. In a few minutes you get a link like https://your-app.streamlit.app
