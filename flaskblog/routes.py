from flask import render_template, url_for, flash, redirect
from flaskblog.forms import PostForm
from flaskblog.models import Post
from flaskblog import app, db
import os, secrets
from moviepy import ImageClip


def upload_media(form_media):
    random_hex = secrets.token_hex(8)
    _, file_extension = os.path.splitext(form_media.filename)
    media_filename = random_hex + file_extension
    media_path = os.path.join(app.root_path, 'static/assets/uploaded_media/', media_filename)

    if file_extension in ['.jpg', '.png', '.jpeg']:
        clip = ImageClip(form_media)
        clip_resized = clip.resized(height=300)
        clip_resized.save_frame(media_path)

    return media_filename

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/blog')
def blog_page():
    posts = Post.query.all()
    return render_template('blog.html', posts=posts)


@app.route('/admin', methods=['GET', 'POST'])
def admin_page():
    form = PostForm()
    media_file = ''
    media_type = ''
    if form.validate_on_submit():
        if form.media.data:
            media_file = upload_media(form.media.data)
            media_type = 'image'
        post = Post(title=form.title.data, content=form.content.data, media=media_file, media_type=media_type)
        db.session.add(post)
        db.session.commit()
        flash(f'Post Successfully uploaded!', 'success')
        return redirect(url_for('blog_page'))
    return render_template('admin.html', form=form)