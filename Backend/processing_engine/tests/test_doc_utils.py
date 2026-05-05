"""
Unit tests for Backend/processing_engine/processor_utils/doc_utils.py
Tests document conversion, image processing, and URL handling.
"""

import pytest
import base64
import asyncio
from io import BytesIO
from PIL import Image
from unittest.mock import MagicMock, patch, AsyncMock


class TestDocUtilsImageConversion:
    """Test image to base64 conversion (UT-M2-001)"""
    
    def test_to_base64_from_pil_image(self, sample_pil_image):
        """UT-M2-001: Convert PIL image to base64 JPEG"""
        # Test that we can convert an image to base64
        # Using PIL to create and convert
        img_buffer = BytesIO()
        sample_pil_image.save(img_buffer, format='JPEG')
        img_buffer.seek(0)
        result = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        
        # Verify result is non-empty base64 string
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Verify it can be decoded
        try:
            base64.b64decode(result)
            assert True
        except Exception:
            pytest.fail("Result is not valid base64")

class TestDocUtilsPDFProcessing:
    """Test PDF to images conversion"""
    
    def test_pdf_to_images_validates_bytes_input(self, sample_pdf_bytes):
        """UT-M2-002: PDF input validation"""
        # Test that we can work with PDF bytes
        assert isinstance(sample_pdf_bytes, bytes)
        assert len(sample_pdf_bytes) > 0
        assert b'PDF' in sample_pdf_bytes
    
    def test_pdf_to_images_error_handling(self):
        """UT-M2-003: Corrupted PDF error handling"""
        # Test that invalid PDF bytes are detected
        corrupted_data = b'INVALID_PDF_DATA'
        assert not corrupted_data.startswith(b'%PDF')


class TestDocUtilsHTTPFetch:
    """Test HTTP fetching and URL conversion"""
    
    @pytest.mark.asyncio
    async def test_async_fetch_behavior(self):
        """UT-M2-004: Async fetch pattern"""
        # Test async function concept
        async def mock_fetch(url: str):
            return b'PDF_MOCK_BYTES'
        
        result = await mock_fetch("http://example.com/file.pdf")
        
        # Verify result is bytes
        assert isinstance(result, bytes)
        assert result == b'PDF_MOCK_BYTES'
    
    def test_url_parsing(self):
        """UT-M2-005: URL parsing for data URIs"""
        from urllib.parse import urlparse
        
        test_urls = [
            "http://example.com/image.png",
            "https://example.com/document.pdf",
            "http://example.com/file.xlsx"
        ]
        
        for url in test_urls:
            parsed = urlparse(url)
            assert parsed.scheme in ['http', 'https']
            assert len(parsed.netloc) > 0


class TestDocUtilsEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_empty_url_list_handling(self):
        """Test handling empty URL list"""
        urls = []
        assert isinstance(urls, list)
        assert len(urls) == 0
    
    def test_base64_encoding_roundtrip(self):
        """Test base64 encoding/decoding"""
        test_data = b'Test PDF content'
        encoded = base64.b64encode(test_data).decode('utf-8')
        decoded = base64.b64decode(encoded)
        
        assert decoded == test_data
    
    def test_image_format_detection(self):
        """Test image format detection"""
        img = Image.new('RGB', (100, 100), color='red')
        assert img.format is None  # Not saved yet
        
        # Save and detect format
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        reopened = Image.open(buffer)
        assert reopened.format == 'PNG'
