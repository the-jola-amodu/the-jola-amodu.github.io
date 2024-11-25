from flask import Flask, render_template, url_for, flash, redirect
from forms import PostForm, EntranceForm
from flask_ckeditor import CKEditor
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
ckeditor = CKEditor(app)
app.config['SECRET_KEY'] = '5a340cc628ca0eb4c15fb7957130c63b'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

db = SQLAlchemy(app)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/blog')
def blog_page():
    return render_template('blog.html')


@app.route('/admin')
def admin_page():
    form = PostForm()
    if form.validate_on_submit():
        flash(f'Post Successfully uploaded!', 'success')
        return redirect(url_for('blog_page'))
    return render_template('admin.html', form=form)


if __name__ == '__main__':
    app.run(debug=True)
