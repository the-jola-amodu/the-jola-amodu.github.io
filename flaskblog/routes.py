from flask import render_template, url_for, flash, redirect, send_from_directory
from flaskblog.forms import PostForm, LinkedInForm, ResumeForm
from flaskblog import get_db_connection
from flaskblog import app
from flaskblog.portfolio_data import get_all_portfolio_data
from flaskblog.resume_parser import extract_pdf_text, parse_experiences_text
import json
import os, secrets
from moviepy import ImageClip

RESUME_JSON_PATH = os.path.join(os.path.dirname(app.root_path), 'content', 'resume.json')


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


def upload_document(form_file):
    """Save an uploaded document (e.g. the LinkedIn PDF) into
    static/assets/documents/ under a randomised name."""
    random_hex = secrets.token_hex(8)
    _, file_extension = os.path.splitext(form_file.filename)
    doc_filename = random_hex + file_extension
    doc_path = os.path.join(app.root_path, 'static/assets/documents/', doc_filename)
    form_file.save(doc_path)
    return doc_filename


def save_document_record(doc_key, filename):
    """Upsert a document record in the `documents` table. Fails soft."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO documents (doc_key, filename)
            VALUES (%s, %s)
            ON CONFLICT (doc_key) DO UPDATE
            SET filename = EXCLUDED.filename,
                date_created = CURRENT_TIMESTAMP;
        """, (doc_key, filename))
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception:
        return False


def get_document_filename(doc_key):
    """Look up a stored document filename. Fails soft (returns None)."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT filename FROM documents WHERE doc_key = %s;", (doc_key,))
        row = cursor.fetchone()
        cursor.close()
        connection.close()
        if row and row[0]:
            return row[0]
    except Exception:
        pass
    return None


def get_linkedin_pdf_url():
    """Static URL of the uploaded LinkedIn PDF, or '' if none stored yet."""
    filename = get_document_filename('linkedin_pdf')
    if filename:
        return url_for('static', filename='assets/documents/' + filename)
    return ''


def get_all_posts():
    """Every blog post as dicts (so templates can use post.title etc.).
    Fails soft — the homepage renders even if the DB is unreachable."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM posts ORDER BY id DESC;")
        columns = [desc[0] for desc in cursor.description]
        posts = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        connection.close()
        return posts
    except Exception:
        return []


def read_resume_json():
    """Load content/resume.json as a dict. Fails soft."""
    try:
        with open(RESUME_JSON_PATH, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def write_resume_json(data):
    """Persist the merged resume data back into content/resume.json."""
    try:
        with open(RESUME_JSON_PATH, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except OSError:
        pass


def save_resume_data(doc_key, payload_dict):
    """Persist parsed resume data to the resume_data table (survives deploys)."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO resume_data (doc_key, content)
            VALUES (%s, %s)
            ON CONFLICT (doc_key) DO UPDATE
            SET content = EXCLUDED.content, date_created = CURRENT_TIMESTAMP;
        """, (doc_key, json.dumps(payload_dict, ensure_ascii=False)))
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception:
        return False


def load_resume_data(doc_key):
    """Load parsed resume data from the DB. Fails soft (returns None)."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT content FROM resume_data WHERE doc_key = %s;", (doc_key,))
        row = cursor.fetchone()
        cursor.close()
        connection.close()
        if row and row[0]:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def refresh_experiences_from_linkedin():
    """Re-parse the stored LinkedIn PDF and rebuild ONLY the experience
    section of content/resume.json. Entries are uniform (company, period,
    role) and deduped on company+date. GitHub owns projects and the Resume
    PDF is storage-only, so nothing else is touched. The result is persisted
    to the DB so the deployed site reflects uploads. Returns a stats dict."""
    stats = {"experiences": 0}
    docs_dir = os.path.join(app.root_path, 'static', 'assets', 'documents')
    filename = get_document_filename('linkedin_pdf')
    if not filename:
        return stats
    path = os.path.join(docs_dir, filename)
    if not os.path.exists(path):
        return stats
    text = extract_pdf_text(path)
    if not text:
        return stats
    experiences = parse_experiences_text(text)
    if not experiences:
        return stats  # fail soft: keep the current experiences

    base = read_resume_json()
    base['work'] = experiences
    write_resume_json(base)
    save_resume_data('linkedin_experiences', {'work': experiences})
    stats['experiences'] = len(experiences)
    return stats


@app.route('/')
def index():
    # Dual-mode portfolio data (GitHub API / resume.json / poems / art).
    # get_all_portfolio_data() fails soft: the homepage renders even when the
    # GitHub API is rate-limited or a content file is missing.
    data = get_all_portfolio_data()

    # The LinkedIn upload owns experiences: the DB copy (persisted on upload,
    # survives deploys on read-only hosts) overrides the file's work section.
    stored = load_resume_data('linkedin_experiences')
    if stored and stored.get('work'):
        resume = dict(data['resume'])
        resume['work'] = stored['work']
        data['resume'] = resume

    # Projects come from GitHub only — resume/LinkedIn never touch them.
    data["linkedin_pdf_url"] = get_linkedin_pdf_url()
    data["posts"] = get_all_posts()  # the blog lives on the creative side
    return render_template('index.html', **data)


@app.route('/resume')
def resume_page():
    """Serve the uploaded Resume PDF; fall back to the bundled CV."""
    docs_dir = os.path.join(app.root_path, 'static', 'assets', 'documents')
    filename = get_document_filename('resume_pdf')
    if filename and os.path.exists(os.path.join(docs_dir, filename)):
        return send_from_directory(docs_dir, filename)
    return send_from_directory(docs_dir, 'Jolas CV.pdf')


@app.route('/blog')
def blog_page():
    """Standalone blog page — the journal proper lives on the creative side."""
    return render_template('blog.html', posts=get_all_posts())


@app.route('/art/<path:filename>')
def art_media(filename):
    """Serve creative-mode polaroid images from content/art/ (file-drop friendly)."""
    art_dir = os.path.join(os.path.dirname(app.root_path), 'content', 'art')
    return send_from_directory(art_dir, filename)


@app.route('/admin', methods=['GET', 'POST'])
def admin_page():
    form = PostForm()
    linkedin_form = LinkedInForm()
    resume_form = ResumeForm()
    media_file = ''
    if form.submit.data and form.validate_on_submit():

        if form.media.data:
            media_file = upload_media(form.media.data)
        
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO posts (title, content, media) 
            VALUES (%s, %s, %s);
        """, (form.title.data, form.content.data, media_file))

        connection.commit()
        cursor.close()
        connection.close()

        flash(f'Post Successfully uploaded!', 'success')
        return redirect(url_for('index') + '#journal')

    if linkedin_form.submit.data and linkedin_form.linkedin_pdf.data:
        if linkedin_form.validate_on_submit():
            filename = upload_document(linkedin_form.linkedin_pdf.data)
            if save_document_record('linkedin_pdf', filename):
                stats = refresh_experiences_from_linkedin()
                flash(
                    'LinkedIn PDF uploaded! Experiences were rebuilt from it '
                    f"({stats.get('experiences', 0)} uniform entries). Linked at /linkedin.",
                    'success',
                )
            else:
                flash('PDF saved, but the database record could not be updated.', 'danger')
            return redirect(url_for('admin_page'))
        flash('PDF files only!', 'danger')
        return redirect(url_for('admin_page'))

    if resume_form.submit.data and resume_form.resume_pdf.data:
        if resume_form.validate_on_submit():
            filename = upload_document(resume_form.resume_pdf.data)
            if save_document_record('resume_pdf', filename):
                flash(
                    'Resume PDF uploaded! It is now the downloadable CV at /resume.',
                    'success',
                )
            else:
                flash('PDF saved, but the database record could not be updated.', 'danger')
            return redirect(url_for('admin_page'))
        flash('PDF files only!', 'danger')
        return redirect(url_for('admin_page'))
    return render_template('admin.html', form=form, linkedin_form=linkedin_form, resume_form=resume_form)


@app.route('/linkedin')
def linkedin_page():
    """Serve the uploaded LinkedIn profile PDF; fall back to the live page."""
    filename = get_document_filename('linkedin_pdf')
    if filename:
        docs_dir = os.path.join(app.root_path, 'static/assets/documents/')
        return send_from_directory(docs_dir, filename)
    return redirect('https://www.linkedin.com/in/jola-amodu/')