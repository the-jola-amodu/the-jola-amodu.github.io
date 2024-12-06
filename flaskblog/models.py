from datetime import datetime
from flaskblog import db

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String)
    content = db.Column(db.String, nullable=False)
    media = db.Column(db.String(20))
    media_type = db.Column(db.String)
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"Post: {self.title} on {self.date_created}"