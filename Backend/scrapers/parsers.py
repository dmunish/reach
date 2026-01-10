from bs4 import BeautifulSoup
import os
import pandas as pd
from urllib.parse import urlparse, parse_qs, unquote
from scrapers.base_scraper import BaseParser

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

class NdmaParser(BaseParser):
    def parse_entries(self, html: str) -> list[dict]:
        parsed_page = BeautifulSoup(html, 'html.parser')
        advisory_cards = parsed_page.find_all("div", class_="advisory-card")
        
        structured_entries = []
        for card in advisory_cards:
            a_tag = card.find_parent("a")
            if not a_tag or not a_tag.get("href"):
                continue
            
            pdf_url = convert_secure_url(a_tag["href"])
            
            date_tag = card.find("p", class_="advisory-date")
            date_text = date_tag.get_text(strip=True) if date_tag else None
            
            formatted_date = pd.to_datetime(date_text, dayfirst=True).strftime('%Y-%m-%d')
            
            title_tag = card.find("h4", class_="advisory-title")
            title_text = title_tag.get_text(strip=True) if title_tag else None
            
            try:
                if "?file=" in pdf_url:
                    filename_with_ext = unquote(pdf_url.split("?file=")[-1])
                    filename_with_ext = filename_with_ext.split("/")[-1]
                else:
                    # Handle direct URLs
                    filename_with_ext = os.path.basename(unquote(pdf_url))
                
                filename, filetype = os.path.splitext(filename_with_ext)
                filetype = filetype.lstrip('.')
            except Exception as e:
                print(f"Error extracting filename from '{pdf_url}': {e}")
                continue

            structured_entries.append({
                "source": "NDMA",
                "posted_date": formatted_date,
                "title": title_text,
                "url": pdf_url,
                "filename": filename,
                "filetype": filetype
            })
        
        return structured_entries

class NeocParser(BaseParser):
    def parse_entries(self, html: str) -> list[dict]:
        parsed_page = BeautifulSoup(html, 'html.parser')
        divs = parsed_page.find_all("div", class_="panel panel-default proj-card")

        structured_entries = []
        for div in divs:
            # Title
            title_tag = div.find("h5", class_="proj-title")
            title_text = title_tag.get_text(strip=True) if title_tag else None

            # Date
            date_tag = div.find("span", class_="proj-date")
            date_text = date_tag.get_text(strip=True) if date_tag else None
            
            if not date_text:
                continue
                
            try:
                formatted_date = pd.to_datetime(date_text, dayfirst=True).strftime('%Y-%m-%d')
            except Exception as e:
                print(f"Error parsing date '{date_text}': {e}")
                continue

            # URL
            a_tag = div.find("a", href=True)
            if not a_tag or not a_tag.get("href"):
                continue
            
            url = convert_secure_url(a_tag["href"])
            
            try:
                if "?file=" in url:
                    filename_with_ext = unquote(url.split("?file=")[-1])
                    filename_with_ext = filename_with_ext.split("/")[-1]
                else:
                    filename_with_ext = os.path.basename(unquote(url))
                
                filename, filetype = os.path.splitext(filename_with_ext)
                filetype = filetype.lstrip('.')
            except Exception as e:
                print(f"Error extracting filename from '{url}': {e}")
                continue

            structured_entries.append({
                "source": "NEOC",
                "posted_date": formatted_date,
                "title": title_text,
                "url": url,
                "filename": filename,
                "filetype": filetype
            })
        
        return structured_entries