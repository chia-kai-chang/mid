import sqlite3
import os
import hashlib
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_PATH = 'documents.db'

def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    return any(col[1] == column_name for col in columns)

def migrate_existing_database(cursor):
    """Migrate existing database to add content_hash column"""
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents'")
    if not cursor.fetchone():
        # Table doesn't exist yet, no need to migrate
        return False

    # Check if content_hash column exists
    if check_column_exists(cursor, 'documents', 'content_hash'):
        # Column already exists
        return False

    print("檢測到舊版資料庫，正在自動遷移...")

    # Add content_hash column
    cursor.execute('''
        ALTER TABLE documents
        ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''
    ''')

    # Get all existing documents and calculate their hashes
    cursor.execute('SELECT id, content FROM documents')
    documents = cursor.fetchall()

    if documents:
        print(f"正在為 {len(documents)} 個現有文件計算 content_hash...")
        for doc_id, content in documents:
            content_hash = calculate_content_hash(content if content else '')
            cursor.execute('''
                UPDATE documents
                SET content_hash = ?
                WHERE id = ?
            ''', (content_hash, doc_id))
        print(f"✓ 已更新 {len(documents)} 個文件")

    print("✓ 資料庫遷移完成")
    return True

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Try to migrate existing database first
    migrated = migrate_existing_database(cursor)

    # Create documents table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL DEFAULT '',
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create index on content_hash for faster duplicate detection
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_content_hash
        ON documents(content_hash)
    ''')

    # Create users table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create default admin user if no users exist
    cursor.execute('SELECT COUNT(*) FROM users')
    user_count = cursor.fetchone()[0]

    if user_count == 0:
        admin_password_hash = generate_password_hash('admin123')
        cursor.execute('''
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        ''', ('admin', admin_password_hash, 'admin'))
        print("✓ 已創建默認管理員帳號 - 用戶名: admin, 密碼: admin123")
        print("⚠️ 請盡快修改默認密碼！")

    conn.commit()
    conn.close()

    if migrated:
        print("=" * 50)

def calculate_content_hash(content):
    """Calculate SHA-256 hash of content"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def check_duplicate(content):
    """Check if a document with the same content already exists"""
    content_hash = calculate_content_hash(content)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, original_filename, upload_date
        FROM documents
        WHERE content_hash = ?
        LIMIT 1
    ''', (content_hash,))

    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            'is_duplicate': True,
            'existing_file': dict(result)
        }
    else:
        return {
            'is_duplicate': False,
            'content_hash': content_hash
        }

def insert_document(filename, original_filename, file_path, file_type, content, content_hash):
    """Insert a new document into the database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO documents (filename, original_filename, file_path, file_type, content, content_hash)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (filename, original_filename, file_path, file_type, content, content_hash))

    conn.commit()
    doc_id = cursor.lastrowid
    conn.close()

    return doc_id

def search_documents(query):
    """Search for documents containing the query text"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, original_filename, file_type, upload_date,
               substr(content, 1, 200) as preview
        FROM documents
        WHERE content LIKE ?
        ORDER BY upload_date DESC
    ''', ('%' + query + '%',))

    results = cursor.fetchall()
    conn.close()

    return [dict(row) for row in results]

def get_document_by_id(doc_id):
    """Get a specific document by ID"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, original_filename, file_path, file_type, content, upload_date
        FROM documents
        WHERE id = ?
    ''', (doc_id,))

    result = cursor.fetchone()
    conn.close()

    return dict(result) if result else None

def get_all_documents():
    """Get all documents"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, original_filename, file_type, upload_date
        FROM documents
        ORDER BY upload_date DESC
    ''')

    results = cursor.fetchall()
    conn.close()

    return [dict(row) for row in results]

def delete_document(doc_id):
    """Delete a document by ID"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get file path before deleting
    cursor.execute('''
        SELECT file_path
        FROM documents
        WHERE id = ?
    ''', (doc_id,))

    result = cursor.fetchone()

    if result:
        file_path = result['file_path']

        # Delete from database
        cursor.execute('''
            DELETE FROM documents
            WHERE id = ?
        ''', (doc_id,))

        conn.commit()
        conn.close()

        return {
            'success': True,
            'file_path': file_path
        }
    else:
        conn.close()
        return {
            'success': False,
            'error': 'Document not found'
        }

# ==================== User Management Functions ====================

def create_user(username, password, role='user'):
    """Create a new user"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        password_hash = generate_password_hash(password)

        cursor.execute('''
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        ''', (username, password_hash, role))

        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        return {
            'success': True,
            'user_id': user_id
        }
    except sqlite3.IntegrityError:
        return {
            'success': False,
            'error': '用戶名已存在'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def verify_user(username, password):
    """Verify user credentials"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, username, password_hash, role
        FROM users
        WHERE username = ?
    ''', (username,))

    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        return {
            'success': True,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'role': user['role']
            }
        }
    else:
        return {
            'success': False,
            'error': '用戶名或密碼錯誤'
        }

def get_user_by_id(user_id):
    """Get user by ID"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, username, role, created_at
        FROM users
        WHERE id = ?
    ''', (user_id,))

    user = cursor.fetchone()
    conn.close()

    return dict(user) if user else None

def get_all_users():
    """Get all users"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, username, role, created_at
        FROM users
        ORDER BY created_at DESC
    ''')

    users = cursor.fetchall()
    conn.close()

    return [dict(user) for user in users]

def delete_user(user_id):
    """Delete a user by ID"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Don't allow deleting the last admin
    cursor.execute('''
        SELECT COUNT(*) FROM users WHERE role = 'admin'
    ''')
    admin_count = cursor.fetchone()[0]

    cursor.execute('''
        SELECT role FROM users WHERE id = ?
    ''', (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return {
            'success': False,
            'error': '用戶不存在'
        }

    if user[0] == 'admin' and admin_count <= 1:
        conn.close()
        return {
            'success': False,
            'error': '無法刪除最後一個管理員帳號'
        }

    cursor.execute('''
        DELETE FROM users WHERE id = ?
    ''', (user_id,))

    conn.commit()
    conn.close()

    return {
        'success': True
    }

def update_user_password(user_id, new_password):
    """Update user password"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    password_hash = generate_password_hash(new_password)

    cursor.execute('''
        UPDATE users
        SET password_hash = ?
        WHERE id = ?
    ''', (password_hash, user_id))

    conn.commit()
    conn.close()

    return {
        'success': True
    }
