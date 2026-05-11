import os
from src.tools.database import init_db
from src.settings import get_config

def clear_database():
    config = get_config()
    db_path = config.app_db_path
    
    # 1. Delete the database file
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Database at '{db_path}' deleted.")
    else:
        print(f"Database at '{db_path}' not found.")
        
    # 2. Re-initialize the database with schema and default seeds
    init_db()
    print("Database recreated and initialized with default seeds.")

if __name__ == "__main__":
    clear_database()
