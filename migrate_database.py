"""
Database Migration Script
Adds content_hash column to existing documents table
"""
import sqlite3
import hashlib
import os

DATABASE_PATH = 'documents.db'

def calculate_content_hash(content):
    """Calculate SHA-256 hash of content"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    return any(col[1] == column_name for col in columns)

def migrate_database():
    """Migrate database to add content_hash column"""

    if not os.path.exists(DATABASE_PATH):
        print(f"資料庫檔案不存在: {DATABASE_PATH}")
        print("系統將在首次執行時自動建立新資料庫")
        return

    print(f"開始遷移資料庫: {DATABASE_PATH}")

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Check if content_hash column exists
        if check_column_exists(cursor, 'documents', 'content_hash'):
            print("✓ content_hash 欄位已存在，無需遷移")
            conn.close()
            return

        print("正在新增 content_hash 欄位...")

        # Add content_hash column with a default value
        cursor.execute('''
            ALTER TABLE documents
            ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''
        ''')

        print("✓ content_hash 欄位已新增")

        # Get all existing documents
        cursor.execute('SELECT id, content FROM documents')
        documents = cursor.fetchall()

        if documents:
            print(f"正在為 {len(documents)} 個現有文件計算 content_hash...")

            # Update content_hash for all existing documents
            for doc_id, content in documents:
                content_hash = calculate_content_hash(content if content else '')
                cursor.execute('''
                    UPDATE documents
                    SET content_hash = ?
                    WHERE id = ?
                ''', (content_hash, doc_id))

            print(f"✓ 已更新 {len(documents)} 個文件的 content_hash")

        # Create index on content_hash
        print("正在建立索引...")
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_content_hash
            ON documents(content_hash)
        ''')
        print("✓ 索引已建立")

        conn.commit()
        print("\n✅ 資料庫遷移成功完成！")

    except sqlite3.Error as e:
        print(f"\n❌ 遷移失敗: {str(e)}")
        conn.rollback()
        raise

    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 50)
    print("資料庫遷移工具")
    print("=" * 50)
    print()

    migrate_database()

    print()
    print("=" * 50)
