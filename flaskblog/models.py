from flaskblog import get_db_connection

def create_posts_table():
    connection = get_db_connection()
    cursor = connection.cursor()

    # Define your table schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id SERIAL PRIMARY KEY,
            title TEXT,
            content TEXT NOT NULL,
            media VARCHAR(200),
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    connection.commit()
    cursor.close()
    connection.close()