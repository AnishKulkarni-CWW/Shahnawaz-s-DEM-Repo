"""
FIDELITAS — HTML Parser

Turns a developer HTML file/ZIP, or a fetched Live/S3/Litmus URL, into a
normalized ImplementationModel: ordered images (with alt/width/height/
border), ordered links/CTAs, page title, and flattened visible text.
"""

import os
import re
import zipfile
import tempfile
from typing import Optional

import requests
import urllib3
from bs4 import BeautifulSoup

from .models import ImplementationModel, HtmlImage, HtmlLink


def load_html_from_upload(path: str, source_name: str) -> ImplementationModel:
    """path may be a .html file or a .zip package containing one."""
    if path.lower().endswith(".zip"):
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(path) as z:
                z.extractall(tmp)
            html_file = _find_index_html(tmp)
            if not html_file:
                m = ImplementationModel(source_name=source_name)
                m.fetch_error = "No .html file found inside the uploaded ZIP."
                return m
            with open(html_file, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
            return parse_html_string(raw, source_name)
    else:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
        return parse_html_string(raw, source_name)


def _find_index_html(root_dir: str) -> Optional[str]:
    candidates = []
    for dirpath, _, files in os.walk(root_dir):
        for fn in files:
            if fn.lower().endswith((".html", ".htm")):
                candidates.append(os.path.join(dirpath, fn))
    if not candidates:
        return None
    # prefer a file literally named index.html
    for c in candidates:
        if os.path.basename(c).lower() == "index.html":
            return c
    return candidates[0]


def fetch_html_from_url(url: str, source_name: str, timeout: int = 15, verify_ssl: bool = True) -> ImplementationModel:
    if not verify_ssl:
        # The user explicitly opted into this via a sidebar toggle with its
        # own warning already shown — no need to also spam logs with the
        # standard urllib3 warning on every single request.
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        resp = requests.get(
            url, timeout=timeout, verify=verify_ssl,
            headers={"User-Agent": "Mozilla/5.0 (FIDELITAS QA Auditor)"},
        )
        resp.raise_for_status()
        model = parse_html_string(resp.text, source_name)
        model.fetch_error = None
        return model
    except requests.exceptions.SSLError as e:
        model = ImplementationModel(source_name=source_name)
        model.fetch_error = (
            f"SSL certificate verification failed ({e.__class__.__name__}). This usually means a "
            f"corporate network/proxy is intercepting HTTPS traffic with its own certificate. If you're "
            f"on such a network, enable 'Disable SSL certificate verification' in the sidebar — otherwise "
            f"this URL may genuinely have a certificate problem worth investigating."
        )
        return model
    except requests.exceptions.RequestException as e:
        model = ImplementationModel(source_name=source_name)
        model.fetch_error = f"Could not fetch this URL: {e}"
        return model


def parse_html_string(raw_html: str, source_name: str) -> ImplementationModel:
    model = ImplementationModel(source_name=source_name, raw_html=raw_html)
    soup = BeautifulSoup(raw_html, "html.parser")

    title_tag = soup.find("title")
    model.title = title_tag.get_text(strip=True) if title_tag else None

    for i, img in enumerate(soup.find_all("img")):
        model.images.append(HtmlImage(
            src=img.get("src", "") or "",
            alt=img.get("alt", "") if img.get("alt") is not None else "",
            width=img.get("width"),
            height=img.get("height"),
            border=img.get("border"),
            order=i,
        ))

    for i, a in enumerate(soup.find_all("a")):
        href = a.get("href", "") or ""
        text = a.get_text(strip=True)
        if not text:
            img_inside = a.find("img")
            if img_inside:
                text = f"[image: {img_inside.get('alt', '')}]"
        model.links.append(HtmlLink(href=href, text=text, order=i, style=a.get("style")))

    model.text_content = soup.get_text(separator="\n")
    return model
