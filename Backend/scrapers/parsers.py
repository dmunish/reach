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
        structured_entries = []

        # 1. Parse the main press release entry (if present)
        main_entry = self._parse_main_entry(parsed_page)
        if main_entry:
            structured_entries.append(main_entry)

        # 2. Parse the sidebar archive entries
        archive_entries = self._parse_archive_entries(parsed_page)
        structured_entries.extend(archive_entries)

        return structured_entries

    def _parse_main_entry(self, parsed_page: BeautifulSoup) -> dict | None:
        """Parse the main/featured press release from the detail section."""
        subtitle_row = parsed_page.find("div", class_="subtitlebg_color")
        if not subtitle_row:
            return None

        # The subtitle row has two columns: first = date, second = title
        cols = subtitle_row.find_all("div", class_=lambda c: c and "col-lg-" in c)
        title_text = None
        date_text = None

        for col in cols:
            h5 = col.find("h5", class_="mb-0")
            if not h5:
                continue
            # The date column has a <small> child with the time
            if h5.find("small"):
                # Extract date text before the <br> and <small>
                date_text = h5.get_text(separator=" ", strip=True)
                # The text is like "24 July 2026 03:18 PM"; extract just the date portion
                # Use the first text node before <br>
                for child in h5.children:
                    if isinstance(child, str) and child.strip():
                        date_text = child.strip()
                        break
            else:
                title_text = h5.get_text(strip=True)

        # Parse the date
        formatted_date = None
        if date_text:
            try:
                formatted_date = pd.to_datetime(date_text, dayfirst=True).strftime('%Y-%m-%d')
            except Exception as e:
                logger.error(f"Error parsing main entry date '{date_text}': {e}")

        # PDF URL from the file-container section
        pdf_url = ""
        file_container = parsed_page.find("div", class_="file-container")
        if file_container:
            pdf_link = file_container.find("a", href=True)
            if pdf_link:
                pdf_url = self._ensure_safe_url(pdf_link["href"])

        if not title_text:
            return None

        return {
            "source": "PMD",
            "posted_date": formatted_date,
            "title": title_text,
            "url": pdf_url,
            "filetype": "pdf",
            "content_hash": self.generate_hash(title_text, formatted_date, pdf_url)
        }

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