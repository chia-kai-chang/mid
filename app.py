from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import os
import uuid
from werkzeug.utils import secure_filename
from markitdown import MarkItDown
import database
from functools import wraps

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
ALLOWED_EXTENSIONS = {
    'pdf',           # PDF files
    'doc', 'docx',   # Word documents
    'xls', 'xlsx',   # Excel spreadsheets
    'ppt', 'pptx'    # PowerPoint presentations
}

# Initialize MarkItDown converter
md_converter = MarkItDown()

# ==================== Authentication Decorators ====================

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
            # return jsonify({'error': '請先登入'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '請先登入'}), 401

        user = database.get_user_by_id(session['user_id'])
        if not user or user['role'] != 'admin':
            return jsonify({'error': '需要管理員權限'}), 403

        return f(*args, **kwargs)
    return decorated_function

# ==================== Helper Functions ====================

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(file_path):
    """Extract text from document using MarkItDown"""
    try:
        result = md_converter.convert(file_path)
        return result.text_content
    except Exception as e:
        print(f"Error extracting text: {str(e)}")
        return ""

# ==================== Authentication Routes ====================

@app.route('/login', methods=['GET'])
def login_page():
    """Render the login page"""
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def login():
    """Handle user login"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': '請輸入用戶名和密碼'}), 400

    result = database.verify_user(username, password)

    if result['success']:
        session['user_id'] = result['user']['id']
        session['username'] = result['user']['username']
        session['role'] = result['user']['role']
        return jsonify({
            'success': True,
            'user': result['user']
        })
    else:
        return jsonify({'error': result['error']}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    """Handle user logout"""
    session.clear()
    return jsonify({'success': True})

@app.route('/api/current_user', methods=['GET'])
def get_current_user():
    """Get current logged in user info"""
    if 'user_id' in session:
        user = database.get_user_by_id(session['user_id'])
        if user:
            return jsonify({
                'logged_in': True,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'role': user['role']
                }
            })

    return jsonify({'logged_in': False})

# ==================== Main Routes ====================

@app.route('/')
@login_required
def index():
    """Render the main page"""
    user = database.get_user_by_id(session['user_id'])
    return render_template('index.html', user=user)

@app.route('/admin')
@admin_required
def admin_page():
    """Render the admin page"""
    return render_template('admin.html')

# ==================== Document Routes ====================

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_files():
    """Handle file upload"""
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('files[]')
    uploaded_files = []
    errors = []
    skipped_files = []

    for file in files:
        if file.filename == '':
            continue

        if file and allowed_file(file.filename):
            try:
                # Generate unique filename
                original_filename = secure_filename(file.filename)
                file_extension = original_filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4()}.{file_extension}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

                # Save file temporarily
                file.save(file_path)

                # Extract text content
                content = extract_text_from_file(file_path)

                # Check for duplicate
                duplicate_check = database.check_duplicate(content)

                if duplicate_check['is_duplicate']:
                    # Remove the temporary file
                    os.remove(file_path)

                    # Add to skipped list
                    existing = duplicate_check['existing_file']
                    skipped_files.append({
                        'filename': original_filename,
                        'reason': 'duplicate',
                        'existing_filename': existing['original_filename'],
                        'existing_upload_date': existing['upload_date']
                    })
                else:
                    # Save to database (not duplicate)
                    doc_id = database.insert_document(
                        filename=unique_filename,
                        original_filename=original_filename,
                        file_path=file_path,
                        file_type=file_extension,
                        content=content,
                        content_hash=duplicate_check['content_hash']
                    )

                    uploaded_files.append({
                        'id': doc_id,
                        'filename': original_filename,
                        'status': 'success'
                    })

            except Exception as e:
                # Clean up file if it exists
                if os.path.exists(file_path):
                    os.remove(file_path)

                errors.append({
                    'filename': file.filename,
                    'error': str(e)
                })
        else:
            errors.append({
                'filename': file.filename,
                'error': 'File type not allowed'
            })

    return jsonify({
        'uploaded': uploaded_files,
        'skipped': skipped_files,
        'errors': errors
    })

@app.route('/api/search', methods=['GET'])
@login_required
def search():
    """Search for documents"""
    query = request.args.get('q', '')

    if not query:
        # Return all documents if no query
        results = database.get_all_documents()
    else:
        # Search for documents containing the query
        results = database.search_documents(query)

    return jsonify({'results': results})

@app.route('/api/document/<int:doc_id>', methods=['GET'])
@login_required
def get_document(doc_id):
    """Get document details"""
    document = database.get_document_by_id(doc_id)

    if document:
        return jsonify(document)
    else:
        return jsonify({'error': 'Document not found'}), 404

@app.route('/api/download/<int:doc_id>', methods=['GET'])
@login_required
def download_file(doc_id):
    """Download original file"""
    document = database.get_document_by_id(doc_id)

    if document and os.path.exists(document['file_path']):
        return send_file(
            document['file_path'],
            as_attachment=True,
            download_name=document['original_filename']
        )
    else:
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/delete/<int:doc_id>', methods=['DELETE'])
@login_required
def delete_document(doc_id):
    """Delete a document"""
    result = database.delete_document(doc_id)

    if result['success']:
        # Delete the physical file
        if os.path.exists(result['file_path']):
            try:
                os.remove(result['file_path'])
            except Exception as e:
                print(f"Warning: Could not delete file {result['file_path']}: {str(e)}")

        return jsonify({'success': True, 'message': 'Document deleted successfully'})
    else:
        return jsonify({'success': False, 'error': result['error']}), 404

# ==================== User Management Routes (Admin Only) ====================

@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    """Get all users (admin only)"""
    users = database.get_all_users()
    return jsonify({'users': users})

@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    """Create a new user (admin only)"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')

    if not username or not password:
        return jsonify({'error': '請輸入用戶名和密碼'}), 400

    if role not in ['user', 'admin']:
        return jsonify({'error': '無效的角色'}), 400

    result = database.create_user(username, password, role)

    if result['success']:
        return jsonify({'success': True, 'user_id': result['user_id']})
    else:
        return jsonify({'error': result['error']}), 400

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete a user (admin only)"""
    # Prevent admin from deleting themselves
    if user_id == session['user_id']:
        return jsonify({'error': '無法刪除自己的帳號'}), 400

    result = database.delete_user(user_id)

    if result['success']:
        return jsonify({'success': True, 'message': '用戶已刪除'})
    else:
        return jsonify({'error': result['error']}), 400

@app.route('/api/change_password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    data = request.get_json()
    new_password = data.get('new_password')

    if not new_password:
        return jsonify({'error': '請輸入新密碼'}), 400

    if len(new_password) < 6:
        return jsonify({'error': '密碼長度至少為 6 個字符'}), 400

    result = database.update_user_password(session['user_id'], new_password)

    if result['success']:
        return jsonify({'success': True, 'message': '密碼已更新'})
    else:
        return jsonify({'error': '更新密碼失敗'}), 500

if __name__ == '__main__':
    # Initialize database
    database.init_db()

    # Create upload folder if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Run the app
    app.run(debug=True, host='127.0.0.1', port=5003)
