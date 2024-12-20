from flask import Flask
from flask_ckeditor import CKEditor
import os
from dotenv import find_dotenv, load_dotenv
import psycopg2

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

SECRET_KEY = os.getenv("SECRET_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")


app = Flask(__name__)
ckeditor = CKEditor(app)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['DATABASE_URL'] = DATABASE_URL

def get_db_connection():
    connection = psycopg2.connect(DATABASE_URL)
    return connection

from flaskblog import routes