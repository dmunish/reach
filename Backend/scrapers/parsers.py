from bs4 import BeautifulSoup
import os
from click import style
import pandas as pd
from urllib.parse import urlparse, parse_qs, unquote
from scrapers.base_scraper import BaseParser
import json
from utils import get_logger

logger = get_logger(__name__)

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
    def parse_entries(self, response) -> list[dict]:
        html = response.text
        parsed_page = BeautifulSoup(html, 'html.parser')
        advisory_cards = parsed_page.find_all("div", class_="advisory-card")
        
        structured_entries = []
        for card in advisory_cards:
            a_tag = card.find_parent("a")
            if not a_tag or not a_tag.get("href"):
                continue
            
            url = convert_secure_url(a_tag["href"])
            
            date_tag = card.find("p", class_="advisory-date")
            date_text = date_tag.get_text(strip=True) if date_tag else None
            
            formatted_date = pd.to_datetime(date_text, dayfirst=True).strftime('%Y-%m-%d')
            
            title_tag = card.find("h4", class_="advisory-title")
            title_text = title_tag.get_text(strip=True) if title_tag else None
            
            try:
                if "?file=" in url:
                    filename_with_ext = unquote(url.split("?file=")[-1])
                    filename_with_ext = filename_with_ext.split("/")[-1]
                else:
                    # Handle direct URLs
                    filename_with_ext = os.path.basename(unquote(url))
                
                filename, filetype = os.path.splitext(filename_with_ext)
                filetype = filetype.lstrip('.')
            except Exception as e:
                logger.error(f"Error extracting filename from '{url}': {e}")
                continue

            structured_entries.append({
                "source": "NDMA",
                "posted_date": formatted_date,
                "title": title_text,
                "url": url,
                "filename": filename,
                "filetype": filetype,
                "content_hash": self.generate_hash(url, formatted_date, title_text)
            })
        
        return structured_entries

class NeocParser(BaseParser):
    def parse_entries(self, response) -> list[dict]:
        html = response.text
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
                logger.error(f"Error parsing date '{date_text}': {e}")
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
                logger.error(f"Error extracting filename from '{url}': {e}")
                continue

            structured_entries.append({
                "source": "NEOC",
                "posted_date": formatted_date,
                "title": title_text,
                "url": url,
                "filename": filename,
                "filetype": filetype,
                "content_hash": self.generate_hash(url, formatted_date, title_text)
            })
        
        return structured_entries

class NdmaAPIParser(BaseParser):
    def parse_entries(self, response) -> list[dict]:
        alerts = response.json().get("data", [])
        structured_entries = []
        for alert in alerts:
            title = alert.get("title")
            formatted_date = pd.to_datetime(alert.get("updated_at"), dayfirst=True).strftime('%Y-%m-%d')
            raw_text = json.dumps(alert)
            structured_entries.append({
                    "source": "NDMA",
                    "posted_date": formatted_date,
                    "title": title,
                    "filetype": "txt",
                    "raw_text": raw_text,
                    "content_hash": self.generate_hash(title, formatted_date, raw_text)
                })
            
        return structured_entries

class PmdPRParser(BaseParser):
    def parse_entries(self, response) -> list[dict]:
        html = response.text
        parsed_page = BeautifulSoup(html, 'html.parser')
        press_releases = parsed_page.find_all("div", class_="col-md-12", style="background-color:#00416A;")

        structured_entries = []
        for press_release in press_releases:
            # Title
            title_tag = press_release.find("h4", align="center")
            title_text = title_tag.get_text(strip=True) if title_tag else None

            # Date
            date_tag = press_release.find("h5", align="center")
            date_text = None
            if date_tag:
                # Extracts "2 Apr, 2023 01:59 PM" from "Issue Date: 2 Apr, 2023 01:59 PM"
                date_text = date_tag.get_text(strip=True).replace("Issue Date:", "").strip()
            
            try:
                formatted_date = pd.to_datetime(date_text).strftime('%Y-%m-%d')
            except Exception as e:
                logger.error(f"Error parsing date '{date_text}': {e}")
                formatted_date = None

            # Content
            content_div = press_release.find("div", class_="PR_English")
            if content_div:
                # Convert internal h3 into markdown headings
                for h3 in content_div.find_all("h3"):
                    h3.string = f"### {h3.get_text(strip=True)}"
                content_text = content_div.get_text(separator="\n", strip=True)
            else:
                content_text = ""

            # Coalesce into raw_text
            raw_text_parts = []
            if title_text:
                raw_text_parts.append(f"# {title_text}")
            if date_text:
                raw_text_parts.append(f"**Issue Date:** {date_text}")
            if content_text:
                raw_text_parts.append(content_text)
            
            raw_text = "\n\n".join(raw_text_parts)

            structured_entries.append({
                "source": "PMD",
                "posted_date": formatted_date,
                "title": title_text,
                "url": str(response.url),
                "filetype": "txt",
                "raw_text": raw_text,
                "content_hash": self.generate_hash(title_text, formatted_date ,raw_text)
                
            })
        
        return structured_entries