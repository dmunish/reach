from bs4 import BeautifulSoup
from html import unescape
import json
import os
import re
from click import style
import pandas as pd
from urllib.parse import quote, urlparse, parse_qs, unquote
from scrapers.base_scraper import BaseParser
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
        # New BEM-style: <a class="adv-card ..."> is the card itself
        advisory_cards = parsed_page.find_all(
            "a", class_=lambda c: c and "adv-card" in c.split()
        )
        
        structured_entries = []
        for card in advisory_cards:
            url = card.get("href")
            if not url:
                continue
            
            url = convert_secure_url(url)
            
            date_tag = card.select_one(".adv-card__date")
            date_text = date_tag.get_text(strip=True) if date_tag else None
            
            if not date_text:
                continue
            
            try:
                formatted_date = pd.to_datetime(date_text, dayfirst=True).strftime('%Y-%m-%d')
            except Exception as e:
                logger.error(f"Error parsing NDMA date '{date_text}': {e}")
                continue
            
            title_tag = card.select_one(".adv-card__title")
            if title_tag:
                # Remove badge spans like <span class="badge-latest">Latest</span>
                for badge in title_tag.select(".badge-latest"):
                    badge.decompose()
                title_text = title_tag.get_text(strip=True)
            else:
                title_text = None
            
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
        # New BEM-style: div.proj-item
        items = parsed_page.find_all("div", class_="proj-item")

        structured_entries = []
        for item in items:
            # Title — the <a> is inside .proj-item__title
            title_tag = item.select_one(".proj-item__title a")
            if not title_tag:
                title_tag = item.select_one(".proj-item__title")
            title_text = title_tag.get_text(strip=True) if title_tag else None

            # Date
            date_tag = item.select_one(".proj-item__date")
            date_text = date_tag.get_text(strip=True) if date_tag else None
            
            if not date_text:
                continue
                
            try:
                formatted_date = pd.to_datetime(date_text, dayfirst=True).strftime('%Y-%m-%d')
            except Exception as e:
                logger.error(f"Error parsing NEOC date '{date_text}': {e}")
                continue

            # URL — prefer the view button, fallback to title link
            a_tag = item.select_one(".proj-item__btn[href]") or item.select_one("a[href]")
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
        return self._parse_archive_entries(parsed_page)

    def _parse_archive_entries(self, parsed_page: BeautifulSoup) -> list[dict]:
        """Parse archive press releases from the sidebar.

        Each archive item is an <a> tag with a mangled PDF URL in the <img src>
        that needs special cleaning.
        """
        entries = []

        # Find the sidebar column
        sidebar = parsed_page.find("div", class_="col-xl-4")
        if not sidebar:
            return entries

        # Archive items are <a> tags with d-flex mb-3 classes
        archive_links = sidebar.find_all(
            "a",
            class_=lambda c: c and "d-flex" in c.split() and "mb-3" in c.split()
        )

        for link in archive_links:
            # Title from h6.mb-1
            title_tag = link.find("h6", class_="mb-1")
            if not title_tag:
                continue
            title_text = title_tag.get_text(strip=True)

            # Date from small.text-muted
            date_tag = link.find("small", class_="text-muted")
            date_text = date_tag.get_text(strip=True) if date_tag else None

            formatted_date = None
            if date_text:
                try:
                    formatted_date = pd.to_datetime(date_text, dayfirst=True).strftime('%Y-%m-%d')
                except Exception as e:
                    logger.error(f"Error parsing archive date '{date_text}': {e}")

            # PDF URL from the mangled img src
            pdf_url = ""
            img_tag = link.find("img")
            if img_tag and img_tag.get("src"):
                pdf_url = self._clean_archive_pdf_url(img_tag["src"])

            # Fallback: use the page link href if no PDF extracted
            page_url = link.get("href", "")

            entries.append({
                "source": "PMD",
                "posted_date": formatted_date,
                "title": title_text,
                "url": pdf_url or page_url,
                "filetype": "pdf",
                "content_hash": self.generate_hash(title_text, formatted_date, pdf_url or page_url)
            })

        return entries

    @staticmethod
    def _clean_archive_pdf_url(raw_src: str) -> str:
        """Clean the mangled PDF URL from an archive entry's image src.

        The src looks like:
        https://weather.gov.pk/[&quot;\\/storage\\/uploads\\/nwfc\\/press_release\\/image\\/1784888310-Press Release 24-07-2026.pdf&quot;]

        It's a JSON-encoded array (HTML-escaped) appended to the base domain.
        We extract the JSON array, unescape HTML entities, parse as JSON,
        and reconstruct the full URL.
        """
        base_url = "https://weather.gov.pk"

        # Find the JSON array [...] after the domain
        match = re.search(r'\[(.*?)\]', raw_src)
        if not match:
            return ""

        json_part = match.group(0)  # e.g. [&quot;\/storage\/...pdf&quot;]

        # HTML-decode: &quot; → ", etc.
        decoded = unescape(json_part)

        # Parse as JSON array
        try:
            paths = json.loads(decoded)
            if isinstance(paths, list) and len(paths) > 0:
                raw_url = base_url + paths[0]
                return PmdPRParser._ensure_safe_url(raw_url)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding archive PDF URL JSON '{decoded}': {e}")

        return ""

    @staticmethod
    def _ensure_safe_url(url: str) -> str:
        """Percent-encode spaces and other unsafe characters in the URL path.

        Spaces in filenames like 'Press Release 29-06-2026.pdf' are not valid
        in URLs and will fail when httpx/requests tries to GET them downstream.
        Decode-then-encode to avoid double-encoding already-safe URLs.
        """
        parsed = urlparse(url)
        # Decode first so already-encoded %20 doesn't become %2520
        decoded_path = unquote(parsed.path)
        safe_path = quote(decoded_path, safe="/:")
        return parsed._replace(path=safe_path).geturl()