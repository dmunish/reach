from urllib.parse import urlparse, parse_qs, unquote

def convert_secure_url(url):
    """Convert secure viewer URLs to direct URLs"""
    if "secure-viewer?" not in url:
        return url
    
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    file_path = query_params.get('file', [''])[0]
    
    # URL decode the file path
    decoded_path = unquote(file_path)
    decoded_path = decoded_path.lstrip('/')
    
    # Construct the direct URL
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    direct_url = f"{base_url}/{decoded_path}"
    
    return direct_url