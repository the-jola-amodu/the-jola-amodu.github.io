from flaskblog import app
from flaskblog.models import create_posts_table

if __name__ == '__main__':

    with app.app_context():
        create_posts_table()

    app.run(debug=True)
