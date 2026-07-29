import unittest
from src.presentation.validation.validation import (
    allowed_file, check_file_size, validate_document_type,
    validate_mime_type, secure_filepath, validate_magic_bytes
)

class TestValidationUnit(unittest.TestCase):
    """Unit test suite for secure file validation, MIME type checks, and filename sanitization."""

    def test_allowed_file_valid_extensions(self):
        self.assertTrue(allowed_file('document.pdf'))
        self.assertTrue(allowed_file('report.csv'))
        self.assertTrue(allowed_file('invoice.xlsx'))
        self.assertTrue(allowed_file('image.png'))

    def test_allowed_file_invalid_and_dangerous_extensions(self):
        self.assertFalse(allowed_file('script.py'))
        self.assertFalse(allowed_file('executable.exe'))
        self.assertFalse(allowed_file('shell.sh'))
        self.assertFalse(allowed_file('malicious.pdf.exe'))
        self.assertFalse(allowed_file('file_without_extension'))

    def test_check_file_size(self):
        self.assertTrue(check_file_size(1024))
        self.assertTrue(check_file_size(10 * 1024 * 1024)) # 10MB
        self.assertFalse(check_file_size(10 * 1024 * 1024 + 1)) # Exceeds 10MB

    def test_validate_document_type(self):
        self.assertTrue(validate_document_type('GST Certificate'))
        self.assertTrue(validate_document_type('PAN Card'))
        self.assertFalse(validate_document_type('Fake Document Category'))

    def test_validate_mime_type(self):
        self.assertTrue(validate_mime_type('application/pdf', 'doc.pdf'))
        self.assertTrue(validate_mime_type('image/png', 'img.png'))
        self.assertFalse(validate_mime_type('application/x-executable', 'bad.exe'))

    def test_secure_filepath(self):
        safe_name = secure_filepath('../../../etc/passwd.pdf')
        self.assertNotIn('../', safe_name)
        self.assertTrue(safe_name.endswith('.pdf'))

    def test_validate_magic_bytes(self):
        pdf_bytes = b'%PDF-1.4 header contents...'
        self.assertTrue(validate_magic_bytes(pdf_bytes, 'file.pdf'))
        
        fake_pdf_bytes = b'MZExecutableMagicHeader...'
        self.assertFalse(validate_magic_bytes(fake_pdf_bytes, 'fake.pdf'))

if __name__ == '__main__':
    unittest.main()
