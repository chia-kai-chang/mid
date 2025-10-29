import sqlite3
import os
import hashlib
from datetime import datetime

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

    # Create table if not exists (for new databases)
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
