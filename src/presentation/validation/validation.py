import re
from werkzeug.utils import secure_filename
import os
import uuid
import mimetypes

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt'}
DANGEROUS_EXTENSIONS = {'exe', 'sh', 'py', 'php', 'jsp', 'asp', 'aspx', 'bat', 'cmd', 'js', 'vbs', 'pl', 'cgi', 'jar'}

ALLOWED_MIME_TYPES = {
    'application/pdf',
    'image/png',
    'image/jpeg',
    'image/jpg',
    'text/csv',
    'text/plain',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

ALLOWED_DOCUMENT_TYPES = {
    'GST Certificate',
    'PAN Card',
    'Company Registration Certificate',
    'Bank Proof',
    'Purchase Orders',
    'Invoices',
    'Contracts',
    'Other Supporting Documents'
}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024 # 10 MB limit

MAGIC_BYTES = {
    'pdf': b'%PDF-',
    'png': b'\x89PNG\r\n\x1a\n',
    'jpeg': b'\xff\xd8\xff',
    'jpg': b'\xff\xd8\xff'
}

def allowed_file(filename: str) -> bool:
    """Checks if the uploaded file extension is in the permitted registry and free of dangerous double extensions."""
    if not filename or '.' not in filename:
        return False
        
    parts = filename.lower().split('.')
    # Reject double extensions containing dangerous scripts
    for part in parts[:-1]:
        if part in DANGEROUS_EXTENSIONS:
            return False
            
    ext = parts[-1]
    return ext in ALLOWED_EXTENSIONS

def validate_mime_type(content_type: str, filename: str) -> bool:
    """Validates that the file MIME type matches permitted application/image categories."""
    if not content_type:
        content_type, _ = mimetypes.guess_type(filename)
        
    if not content_type:
        return True # Default fallback if un-guessable
        
    base_mime = content_type.split(';')[0].strip().lower()
    return base_mime in ALLOWED_MIME_TYPES

def validate_magic_bytes(file_bytes: bytes, filename: str) -> bool:
    """Checks magic header bytes for image and PDF files to reject disguised executables."""
    if not filename or '.' not in filename:
        return False
    ext = filename.lower().rsplit('.', 1)[1]
    if ext in MAGIC_BYTES:
        magic = MAGIC_BYTES[ext]
        return file_bytes.startswith(magic)
    return True

def generate_secure_filename(original_filename: str) -> str:
    """Generates a UUID-prefixed secure storage filename preventing path traversal and collisions."""
    clean_base = secure_filename(original_filename)
    if not clean_base or clean_base in {'.', '..', ''}:
        clean_base = "upload.bin"
    file_id = str(uuid.uuid4().hex[:12])
    return f"{file_id}_{clean_base}"

def validate_document_type(doc_type: str) -> bool:
    """Checks if the document category is supported by the system."""
    return doc_type in ALLOWED_DOCUMENT_TYPES

def secure_filepath(filename: str) -> str:
    """Cleans file name, removing traversal attempts and escaping characters."""
    return generate_secure_filename(filename)

def check_file_size(size_bytes: int) -> bool:
    """Enforces upper size limit rules on files."""
    return size_bytes > 0 and size_bytes <= MAX_FILE_SIZE_BYTES

def validate_email(email: str) -> bool:
    """Regex pattern validation check for emails."""
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email))

def validate_pan(pan: str) -> bool:
    """Enforces standard Indian PAN card character format (5 letters, 4 numbers, 1 letter)."""
    pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
    return bool(re.match(pattern, pan.upper()))

def validate_gst(gst: str) -> bool:
    """Enforces standard Indian GST registration format (15 characters)."""
    pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
    return bool(re.match(pattern, gst.upper()))
