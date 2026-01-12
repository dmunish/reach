from httpx import AsyncClient
from PIL import Image
import io
import base64
import fitz
from urllib.parse import urlparse
import os
from typing import List


async def fetch_file(url: str):
    async with AsyncClient(timeout=60.0) as http_client:
        response = await http_client.get(url)
        response.raise_for_status()
        return response.content
    
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