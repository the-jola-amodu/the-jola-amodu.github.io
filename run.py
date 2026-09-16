from flaskblog import app
from flaskblog.models import create_posts_table, create_documents_table, create_resume_data_table

if __name__ == '__main__':

    with app.app_context():
        create_posts_table()
        for create in (create_documents_table, create_resume_data_table):
            try:  # the site must still boot if the DB hiccups
                create()
            except Exception as exc:
                print(f"[warn] could not create a table: {exc}")

    app.run(debug=True)
