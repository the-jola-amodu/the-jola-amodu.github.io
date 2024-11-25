from flask import Flask, render_template, url_for
from forms import PostForm, EntranceForm
from flask_ckeditor import CKEditor

app = Flask(__name__)
ckeditor = CKEditor(app)
app.config['SECRET_KEY'] = '5a340cc628ca0eb4c15fb7957130c63b'


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/blog')
def blog_page():
    return render_template('blog.html')


@app.route('/admin')
def admin_page():
    form = PostForm()
    return render_template('admin.html', form=form)


if __name__ == '__main__':
    app.run(debug=True)
