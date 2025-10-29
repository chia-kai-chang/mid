from flask import Flask, render_template, request, jsonify, send_file
import os
import uuid
from werkzeug.utils import secure_filename
from markitdown import MarkItDown
import database

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
ALLOWED_EXTENSIONS = {
    'pdf',           # PDF files
    'doc', 'docx',   # Word documents
    'xls', 'xlsx',   # Excel spreadsheets
    'ppt', 'pptx'    # PowerPoint presentations
}

# Initialize MarkItDown converter
md_converter = MarkItDown()

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

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
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
def get_document(doc_id):
    """Get document details"""
    document = database.get_document_by_id(doc_id)

    if document:
        return jsonify(document)
    else:
        return jsonify({'error': 'Document not found'}), 404

@app.route('/api/download/<int:doc_id>', methods=['GET'])
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

if __name__ == '__main__':
    # Initialize database
    database.init_db()

    # Create upload folder if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Run the app
    app.run(debug=True, host='127.0.0.1', port=5003)
