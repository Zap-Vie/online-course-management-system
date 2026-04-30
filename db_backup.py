import os
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'online_course_db')
BACKUP_DIR = 'backups'

if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

def backup_database():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(BACKUP_DIR, f"backup_{DB_NAME}_{timestamp}.sql")
    MYSQLDUMP_PATH = os.getenv('MYSQLDUMP_PATH')
    dump_cmd = [
        MYSQLDUMP_PATH,
        f'-h{DB_HOST}',
        f'-u{DB_USER}',
        f'-p{DB_PASSWORD}',
        DB_NAME
    ]
    
    try:
        with open(backup_file, 'w') as f:
            subprocess.run(dump_cmd, stdout=f, check=True)
    except subprocess.CalledProcessError as e:
        print(e)

if __name__ == "__main__":
    backup_database()