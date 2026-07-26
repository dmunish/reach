from httpx import AsyncClient, HTTPStatusError, RequestError
from PIL import Image
import io
import base64
import fitz
from urllib.parse import urlparse
import os
import asyncio
from typing import List
from utils import get_logger

logger = get_logger(__name__)

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://weather.gov.pk/",
    "Accept": "*/*",
}

async def fetch_file(url: str):
    last_error = None
    for attempt in range(3):
        try:
            async with AsyncClient(timeout=60.0) as http_client:
                response = await http_client.get(url, headers=FETCH_HEADERS)
                response.raise_for_status()
                return response.content
        except HTTPStatusError as e:
            if e.response.status_code in (429, 503):
                last_error = e
                await asyncio.sleep(2 ** attempt)
                continue
            raise
        except RequestError as e:
            last_error = e
            await asyncio.sleep(2 ** attempt)
            continue
    raise last_error
    
def to_base64(img: Image.Image) -> str:
    """Convert PIL Image to base64 string."""
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=90)
    return base64.b64encode(buffered.getvalue()).decode()

def pdf_to_images(file: bytes, dpi: int = 72):
    """
    Returns a list of PIL images for a pdf file byte stream
    """
    images = []
    document = fitz.open(stream=file, filetype="pdf")

    for page_num in range(document.page_count):
        page = document[page_num]
        mat = fitz.Matrix(dpi/72, dpi/72)
        pixels = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pixels.width, pixels.height], pixels.samples)
        images.append(img)

    document.close()
    return images

async def url_to_b64_strings(url: str) -> List[str]:
    _, file_ext = os.path.splitext(urlparse(url).path)
    file_type = file_ext.lstrip('.').lower()
    file = await fetch_file(url)
    
    strings = []
    if file_type in ["png", "jpeg", "jpg", "gif", "webp"]:
        mime_type = "jpeg" if file_type == "jpg" else file_type
        b64_encoding = base64.b64encode(file).decode("utf-8")
        strings.append(f"data:image/{mime_type};base64,{b64_encoding}")
    
    elif file_type == "pdf":
        images = pdf_to_images(file)
        if images:
            for image in images:
                strings.append(f"data:image/jpeg;base64,{to_base64(image)}")
        else:
            raise ValueError("Could not extract images from PDF")
    
    else:
        raise ValueError(f"Unsupported file type: {file_type}")
    
    return strings