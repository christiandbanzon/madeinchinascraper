import io
import re
import time
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger

from config import HEADERS


class PDFExtractor:
    """Utility for fetching PDFs and extracting emails/text with graceful fallbacks."""

    def __init__(self, session: Optional[requests.Session] = None, request_timeout_seconds: int = 20):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)
        self.request_timeout_seconds = request_timeout_seconds

    def analyze_url(self, url: str, display_name: Optional[str] = None) -> Dict:
        """Download a certificate (PDF or landing page), extract emails, and return analysis details.

        Returns a dict: { name, type, url, emails, error }
        """
        result: Dict = {
            "name": display_name or self._infer_name_from_url(url),
            "type": "PDF",
            "url": url,
            "emails": [],
            "error": None,
        }

        try:
            # First attempt: direct GET
            response = self.session.get(url, timeout=self.request_timeout_seconds)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()

            if "application/pdf" in content_type or url.lower().endswith(".pdf"):
                text = self._extract_text_from_pdf_bytes(response.content)
                emails = self._extract_emails_from_text(text) if text else []
                result["emails"] = emails
                return result

            # Fallback: page may contain embedded PDF or links
            soup = BeautifulSoup(response.content, "html.parser")

            # Try <embed type="application/pdf"> or iframe with .pdf
            pdf_srcs: List[str] = []
            embed = soup.find("embed", attrs={"type": "application/pdf"})
            if embed and embed.get("src"):
                pdf_srcs.append(embed.get("src"))

            for iframe in soup.find_all("iframe"):
                src = iframe.get("src") or ""
                if ".pdf" in src.lower():
                    pdf_srcs.append(src)

            # Also collect anchor links that point to pdfs
            for a in soup.find_all("a"):
                href = a.get("href") or ""
                if ".pdf" in href.lower():
                    pdf_srcs.append(href)

            # Deduplicate while preserving order
            seen = set()
            unique_pdf_srcs: List[str] = []
            for src in pdf_srcs:
                if not src:
                    continue
                abs_src = self._absolutize(url, src)
                if abs_src not in seen:
                    seen.add(abs_src)
                    unique_pdf_srcs.append(abs_src)

            for pdf_url in unique_pdf_srcs[:3]:  # limit attempts
                try:
                    pdf_resp = self.session.get(pdf_url, timeout=self.request_timeout_seconds)
                    pdf_resp.raise_for_status()
                    text = self._extract_text_from_pdf_bytes(pdf_resp.content)
                    emails = self._extract_emails_from_text(text) if text else []
                    if emails:
                        result["emails"] = emails
                        result["url"] = pdf_url
                        return result
                    time.sleep(1)
                except Exception as inner_err:  # noqa: BLE001
                    logger.debug(f"Error fetching embedded PDF {pdf_url}: {inner_err}")

            # Last resort: try to find emails directly on the landing page text
            page_text = soup.get_text(separator=" ", strip=True)
            result["emails"] = self._extract_emails_from_text(page_text)
            return result

        except Exception as e:  # noqa: BLE001
            result["error"] = str(e)
            return result

    @staticmethod
    def _extract_emails_from_text(text: Optional[str]) -> List[str]:
        if not text:
            return []
        pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
        emails = pattern.findall(text)
        # Deduplicate while preserving order
        unique: List[str] = []
        seen = set()
        for e in emails:
            if e not in seen:
                seen.add(e)
                unique.append(e)
        return unique

    @staticmethod
    def _infer_name_from_url(url: str) -> str:
        return url.rsplit("/", 1)[-1] or "certificate"

    @staticmethod
    def _absolutize(base_url: str, ref: str) -> str:
        try:
            if ref.startswith("http://") or ref.startswith("https://"):
                return ref
            if ref.startswith("//"):
                return "https:" + ref
            # naive join
            if ref.startswith("/"):
                from urllib.parse import urlparse

                p = urlparse(base_url)
                return f"{p.scheme}://{p.netloc}{ref}"
            # relative path
            if base_url.endswith("/"):
                return base_url + ref
            return base_url.rsplit("/", 1)[0] + "/" + ref
        except Exception:  # noqa: BLE001
            return ref

    @staticmethod
    def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> Optional[str]:
        """Try PyPDF2 first, fall back to pdfplumber."""
        if not pdf_bytes:
            return None

        # Try PyPDF2
        try:
            import PyPDF2  # type: ignore

            reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            text_parts: List[str] = []
            for page in reader.pages:
                try:
                    page_text = page.extract_text() or ""
                except Exception:  # noqa: BLE001
                    page_text = ""
                text_parts.append(page_text)
            text = " ".join(text_parts).strip()
            if text:
                return text
        except Exception:  # noqa: BLE001
            logger.debug("PyPDF2 failed; will try pdfplumber")

        # Fallback to pdfplumber
        try:
            import pdfplumber  # type: ignore

            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                text_parts: List[str] = []
                for page in pdf.pages:
                    try:
                        page_text = page.extract_text() or ""
                    except Exception:  # noqa: BLE001
                        page_text = ""
                    text_parts.append(page_text)
            text = " ".join(text_parts).strip()
            return text or None
        except Exception:  # noqa: BLE001
            logger.debug("pdfplumber failed to extract text")
            return None


