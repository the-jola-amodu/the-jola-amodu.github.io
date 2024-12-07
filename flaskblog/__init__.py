from flask import Flask
from flask_ckeditor import CKEditor
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
ckeditor = CKEditor(app)
app.config['SECRET_KEY'] = '5a340cc628ca0eb4c15fb7957130c63b'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

db = SQLAlchemy(app)

from flaskblog import routes