import os, re
from flask import Flask, request, jsonify, redirect, render_template, url_for, g
from flask_session import Session
import pandas as pd
from werkzeug.utils import secure_filename


from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


import secrets
import io

from auth import is_logged_in, login, logout, init_oauth, auth_bp, google_login,  auth_callback
from settings import settings_page
from utils import allowed_file

from sqlalchemy import create_engine
from models import Base, FormResponse
from sqlalchemy.orm import sessionmaker
# Import necessary modules
from models import ColumnLabel, FormResponse

# Summarization
import pandas as pd

# Categorization
import re

# Initialize Flask application
app = Flask(__name__)
# Secret key to encrypt session data
app.secret_key = os.environ.get('SECRET_KEY')

# Flask Session
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

init_oauth(app)
app.register_blueprint(auth_bp)

engine = create_engine('sqlite:///database.db')  # swap for PostgreSQL URI if needed
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


# Define the folder to save uploaded files
UPLOAD_FOLDER = './uploaded_files'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_APP_ID = os.environ.get('GOOGLE_APP_ID')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
REDIRECT_URI = "http://localhost:8080/oauth2callback"


def get_drive_service(access_token):
    creds = Credentials(token=access_token)
    service = build('drive',
                     'v3', credentials=creds)
    return service



def download_file_from_drive(service, file_id):
    # Get file metadata
    file_metadata = service.files().get(fileId=file_id, fields="name, mimeType").execute()
    file_name = file_metadata['name']
    mime_type = file_metadata['mimeType']

    # Prepare the correct request
    if mime_type == 'application/vnd.google-apps.spreadsheet':
        # Export as Excel
        request = service.files().export_media(
            fileId=file_id,
            mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        file_name += '.xlsx'
    elif mime_type.startswith('application/vnd.google-apps.'):
        raise ValueError(f"Unsupported Google Docs format for export: {mime_type}")
    else:
        # Regular binary file (like uploaded .xlsx)
        request = service.files().get_media(fileId=file_id)

    # Download the file
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

    # Save locally or return the file-like object
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_name}")   
    with open(file_path, 'wb') as f:
        f.write(fh.getvalue())
    
    return f"{file_name}"


# Route to display the file preview
@app.route('/preview', methods=['GET', 'POST'])
def preview():
    session = Session()

    # Handle form submission (approvals)
    if request.method == "POST":
        for key, value in request.form.items():
            if key.startswith("decision_"):
                sid = int(key.split("_")[1])
                session.query(FormResponse).filter_by(submission_id=sid).update({"approved": value})
        session.commit()

    # Get filter parameter
    status_filter = request.args.get("status")  # approved, disapproved, or pending

    # Query data
    data = session.query(FormResponse).all()
    labels = {c.id: c.name for c in session.query(ColumnLabel).all()}

    # Pivot
    rows = {}
    for r in data:
        sid = r.submission_id
        if sid not in rows:
            rows[sid] = {'submission_id': sid}
        rows[sid][labels[r.column_id]] = r.value
        rows[sid]['approved'] = r.approved

    # Filter rows by approval status
    filtered_rows = []
    for row in rows.values():
        status = row.get('approved')
        if status_filter == "approved" and status == "approved":
            filtered_rows.append(row)
        elif status_filter == "disapproved" and status == "disapproved":
            filtered_rows.append(row)
        elif status_filter == "pending" and not status:
            filtered_rows.append(row)
        elif not status_filter:  # show all if no filter
            filtered_rows.append(row)

    # Use first 6 columns
    all_columns = list(labels.values())
    display_columns = all_columns[:6]  # first 6 columns

    session.close()
    return render_template("preview.html", responses=filtered_rows, columns=display_columns, status_filter=status_filter)
 
@app.route("/detail/<int:submission_id>", methods=["GET", "POST"])
def detail_view(submission_id):
    session = Session()
    labels = {c.id: c.name for c in session.query(ColumnLabel).all()}

    # Handle approve/disapprove submission
    if request.method == "POST":
        decision = request.form.get("decision")
        session.query(FormResponse).filter_by(submission_id=submission_id).update({"approved": decision})
        session.commit()

    responses = session.query(FormResponse).filter_by(submission_id=submission_id).all()
    details = {labels[r.column_id]: r.value for r in responses}

    # Use current approval status (assuming all rows for submission share it)
    approval_status = responses[0].approved if responses else None

    session.close()
    return render_template("detail.html", submission_id=submission_id, details=details, approval_status=approval_status)

### 
# Settings
###
# Route to display the settings page
# @app.route('/settings', methods=['GET', 'POST'])
# Route for the settings page
app.add_url_rule('/settings', 'settings', settings_page, methods=['GET', 'POST'])

# Route for the login page
app.add_url_rule('/login', 'login', login, methods=['GET', 'POST'])

app.add_url_rule('/google_login', 'google_login', google_login, methods=['GET', 'POST'])

app.add_url_rule('/auth_callback', 'auth_callback', auth_callback, methods=['GET', 'POST'])

# Route for logging out
app.add_url_rule('/logout', 'logout', logout)


@app.before_request
def generate_nonce():
    g.nonce = secrets.token_urlsafe(16)
    
@app.after_request
def add_csp_headers(response):
    csp = (
        "default-src 'self'; ",
        f"script-src 'self' '{g.nonce}' https://apis.google.com https://www.gstatic.com "
        "https://accounts.google.com https://code.jquery.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "connect-src 'self' https://www.googleapis.com https://oauth2.googleapis.com; "
        "img-src 'self' data: https://ssl.gstatic.com https://www.gstatic.com; "
        "frame-src https://accounts.google.com https://content.googleapis.com "
        "https://docs.google.com https://drive.google.com; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'self';"
    )
    response.headers['Content-Security-Policy'] = app
    return response


def store_csv(df):
    session = Session()
    # Store column names
    column_map = {}
    for col in df.columns:
        existing = session.query(ColumnLabel).filter_by(name=col).first()
        if not existing:
            existing = ColumnLabel(name=col)
            session.add(existing)
            session.commit()
        column_map[col] = existing.id

    # Store row data
    for i, row in df.iterrows():
        submission_id = i + 1  # could use UUID or timestamp
        for col, value in row.items():
            response = FormResponse(
                submission_id=submission_id,
                column_id=column_map[col],
                value=str(value)
            )
            session.add(response)

    session.commit()
    session.close()
    print('Data successfully stored in the database!')
    return
# Route to handle the home page and file uploads
@app.route('/', methods=['GET', 'POST'])
def upload():
    # If user is not logged in, redirect to login page
    if not is_logged_in():
        return redirect(url_for('login'))

    if request.method == 'POST':
        file_id = request.form['google_drive_file_id']
        access_token = request.form['access_token']
        if file_id:
            if not file_id or not access_token:
                return jsonify({"error": "Missing Google Drive file ID or access token."}), 400                 
            service = get_drive_service(access_token)
            file_path = download_file_from_drive(service, file_id)
            filename = secure_filename(file_path).split(".")[0]
            filetype = secure_filename(file_path).split(".")[1]
                    
            print('FILE', file_path)
                

        else:


            # Check if the post request has the file part
            if 'file' not in request.files:
                return jsonify({"error": "No file part"}), 400        
            else:
                file = request.files['file']
                # If no file is selected
                if file.filename == '':
                    return jsonify({"error": "No selected file"}), 400

                if not allowed_file(file.filename):
                    return jsonify({"error": "Please, upload CSV or XLSX files only!"}), 400

                # If file is valid and has allowed extension
                print('FILE', file.filename)
                if file and allowed_file(file.filename):
                    if not os.path.exists(app.config['UPLOAD_FOLDER']):
                        os.makedirs(app.config['UPLOAD_FOLDER'])   

                    # df, filename = file_to_df(file)
                    filetype = secure_filename(file.filename).split(".")[1]
                    filename = secure_filename(file.filename).split(".")[0]
                    file.save(f"{os.path.join(UPLOAD_FOLDER, filename)}.{filetype}")
                    print('File successfully uploaded!')        


        # Read CSV content
        if filetype == 'csv':
            df = pd.read_csv(f"{os.path.join(app.config['UPLOAD_FOLDER'], filename)}.{filetype}").head(5)
        elif filetype == 'xlsx':
            df = pd.read_excel(f"{os.path.join(app.config['UPLOAD_FOLDER'], filename)}.{filetype}", engine='openpyxl').head(5)
            # df.columns = df.iloc[0]
            # df = df[1:].reset_index(drop=True)
        print('DataFrame:', len(df))
        # Store the DataFrame to the database
        if df.empty:
            return jsonify({"error": "The uploaded file is empty or invalid."}), 400
        store_csv(df)
        return redirect(url_for("preview"))

    # GET request renders the upload form
    return render_template('upload.html', nonce=g.nonce, GOOGLE_API_KEY=GOOGLE_API_KEY, GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID, GOOGLE_APP_ID=GOOGLE_APP_ID)



# Run the Flask app on localhost
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
