from flask import Blueprint, request, redirect, render_template, session, url_for
import json
import os 
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth

auth_bp = Blueprint("auth", __name__)
oauth = OAuth()

def init_oauth(app):

    app.config['GOOGLE_CLIENT_ID'] = os.environ.get("GOOGLE_CLIENT_ID")
    app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get("GOOGLE_CLIENT_SECRET")
    app.config['GOOGLE_DISCOVERY_URL'] = "https://accounts.google.com/.well-known/openid-configuration"
    # app.config['AUTHORIZE_URL'] = "https://accounts.google.com/o/oauth2/auth"
    # app.config['ACCESS_TOKEN_URL'] = "https://accounts.google.com/o/oauth2/token"
 
    # Google OAuth Configuration
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url=app.config["GOOGLE_DISCOVERY_URL"],
        client_kwargs={"scope": "openid email profile"}       
    )



#app.add_url_rule('/google_login', 'google_login', methods=['GET', 'POST'])
@auth_bp.route('/google_login', methods=['GET', 'POST'])
def google_login():
    return oauth.google.authorize_redirect(url_for("auth_callback", _external=True))

#app.add_url_rule('/auth_callback', 'auth_callback', methods=['GET', 'POST'])
@auth_bp.route('/auth_callback', methods=['GET', 'POST'])
def auth_callback():
    token = oauth.google.authorize_access_token()
    user_info = token.get("userinfo") # Get user info
    session["user"] = user_info  # Save user info in session
    return redirect(url_for("preview"))



load_dotenv()
# Hardcoded user credentials for demonstration purposes
users = json.loads(os.getenv('USERS'))
      
# Helper function to check if user is logged in
def is_logged_in():
    return 'user' in session

# Function for login page
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the credentials are valid
        if username in users and users[username] == password:
            session['user'] = {"name": username, "email": username}
            return redirect(url_for('preview'))
        else:
            error = "Invalid credentials. Please try again."
            return render_template('login.html', error=error)

    # Render the login form for GET requests
    return render_template('login.html')

# Function to log user out
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))