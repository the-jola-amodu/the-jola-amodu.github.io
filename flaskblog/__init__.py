from flask import Flask
from flask_ckeditor import CKEditor
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import find_dotenv, load_dotenv

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

SECRET_KEY = os.getenv("SECRET_KEY")
SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")


app = Flask(__name__)
ckeditor = CKEditor(app)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI

db = SQLAlchemy(app)

from flaskblog import routes