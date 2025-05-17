
import os, json
import datetime
from flask import jsonify
import pandas as pd
from werkzeug.utils import secure_filename
# Allowed Extensions
ALLOWED_EXTENSIONS = {'csv', 'xlsx'}

SETTINGS_FILE = 'settings.json'
# Define the folder to save uploaded files
UPLOAD_FOLDER = './uploaded_files'


def delete_file(file_path):
    print('FILE PATH, file_path')
    try:
        os.remove(file_path)
        print(f"{file_path} has been deleted successfully.")
    except FileNotFoundError:
        print(f"{file_path} does not exist.")
    except PermissionError:
        print(f"Permission denied: Cannot delete {file_path}.")
    except Exception as e:
        print(f"An error occurred: {e}")


def delete_files(user):
    print('delete files ')
    try:
        # Delete PDF files (never store PDF files)
        files = os.listdir('./uploaded_files/')
        for f in files:
            os.remove('./uploaded_files/'+f)
    except FileNotFoundError:
        print(f"{f} does not exist.")
    except PermissionError:
        print(f"Permission denied: Cannot delete {f}.")
    except Exception as e:
        print(f"An error occurred: {e}")

    with open(SETTINGS_FILE, 'r') as file:
        settings = json.load(file)
    
    # if param store_p is no True
    if not settings['store_p']:    
        try:
            # Delete pickle objects
            files = os.listdir(os.path.join('./objects/', user, '/*'))
            print('files ', files)
            for f in files:
                os.remove(f)
        except FileNotFoundError:
            print(f"{f} does not exist.")
        except PermissionError:
            print(f"Permission denied: Cannot delete {f}.")
        except Exception as e:
            print(f"An error occurred: {e}")


# Create a helper function to check file extension
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Helper function to validate if the input is a valid list of strings
def validate_string(str1):
    if not isinstance(str1, str):
        return False, []
    # Convert comma-separated string to a list and strip any extra spaces
    str_list = [s.strip() for s in str1.split(',') if s.strip()]
    # If the list is empty, return False
    if len(str_list) == 0:
        return False, []
    return True, str_list



def save_file(df, filename):
    filetype = secure_filename(filename).split(".")[1]
    filename = secure_filename(filename).split(".")[0]
    filename = f"{filename}-{datetime.datetime.now().strftime('%Y%m%d')}.{filetype}"        
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    print('FILE', filepath)
        
    if filetype == 'csv':
        # Save to  csv file
        df.to_csv(filepath, index="False")
    elif filetype == 'xlsx':
        # Save to Excel file
        df.to_excel(filepath, index=False, engine='openpyxl')

    print('File successfully saved!')