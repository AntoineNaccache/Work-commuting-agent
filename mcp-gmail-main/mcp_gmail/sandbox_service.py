"""
Sandbox service for safely opening and analyzing email links and attachments.
Uses E2B cloud sandboxes for isolated execution.
"""

import base64
import io
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    from e2b import Sandbox
    E2B_AVAILABLE = True
except ImportError:
    E2B_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import validators
    VALIDATORS_AVAILABLE = True
except ImportError:
    VALIDATORS_AVAILABLE = False

# Suspicious TLDs commonly used in phishing
SUSPICIOUS_TLDS = {
    '.xyz', '.tk', '.ml', '.ga', '.cf', '.gq', '.top', '.club', '.work',
    '.link', '.click', '.pw', '.cc', '.su', '.ru'
}

# Legitimate brand names for typosquatting detection
LEGITIMATE_BRANDS = {
    'google', 'facebook', 'paypal', 'amazon', 'microsoft', 'apple', 'netflix',
    'instagram', 'twitter', 'linkedin', 'dropbox', 'adobe', 'github'
}

# Suspicious file extensions
DANGEROUS_EXTENSIONS = {
    '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js', '.jar',
    '.msi', '.dll', '.app', '.deb', '.rpm', '.sh', '.run'
}

# File type magic bytes
MAGIC_BYTES = {
    'pdf': b'%PDF',
    'zip': b'PK\x03\x04',
    'docx': b'PK\x03\x04',  # DOCX is a zip
    'xlsx': b'PK\x03\x04',  # XLSX is a zip
    'png': b'\x89PNG',
    'jpg': b'\xff\xd8\xff',
    'gif': b'GIF89a',
    'exe': b'MZ',
}


class SandboxBrowser:
    """
    Browser sandbox for safely opening and analyzing URLs.
    Uses E2B cloud sandboxes with Playwright integration.
    """

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        """
        Initialize sandbox browser.

        Args:
            api_key: E2B API key (defaults to E2B_API_KEY env var)
            timeout: Timeout in seconds for sandbox operations
        """
        if not E2B_AVAILABLE:
            raise ImportError(
                "e2b library is required for sandbox functionality. "
                "Install with: pip install e2b"
            )

        # E2B uses environment variable E2B_API_KEY, so we set it if provided
        api_key_to_use = api_key or os.getenv('E2B_API_KEY') or os.getenv('MCP_GMAIL_E2B_API_KEY')
        if not api_key_to_use:
            raise ValueError(
                "E2B_API_KEY not set. Get your API key from https://e2b.dev and set it as "
                "environment variable E2B_API_KEY or MCP_GMAIL_E2B_API_KEY"
            )

        # Set the environment variable for E2B to use
        os.environ['E2B_API_KEY'] = api_key_to_use
        self.timeout = timeout

    def open_url(self, url: str, take_screenshot: bool = False) -> Dict[str, Any]:
        """
        Open a URL in a sandboxed browser and analyze it.

        Args:
            url: URL to open
            take_screenshot: Whether to capture a screenshot

        Returns:
            Dictionary with content analysis and safety assessment
        """
        result = {
            'url': url,
            'success': False,
            'title': '',
            'content': '',
            'html': '',
            'screenshot': None,
            'safety_score': 100,
            'warnings': [],
            'ssl_valid': False,
            'redirects': [],
            'error': None
        }

        try:
            # Validate URL format
            if not self._is_valid_url(url):
                result['error'] = 'Invalid URL format'
                result['safety_score'] = 0
                result['warnings'].append('Invalid URL format')
                return result

            # Perform URL safety checks before opening
            url_warnings = self._check_url_safety(url)
            result['warnings'].extend(url_warnings)

            # Create sandbox and open URL with Playwright
            # E2B Sandbox uses environment variable E2B_API_KEY (already set in __init__)
            sandbox = Sandbox.create()
            try:
                # Install Playwright and browsers
                sandbox.commands.run('pip install playwright')
                sandbox.commands.run('playwright install chromium')

                # Create Python script to open URL
                script = f'''
import asyncio
from playwright.async_api import async_playwright
import json

async def main():
    result = {{}}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()

        try:
            response = await page.goto("{url}", wait_until="networkidle", timeout=15000)
            result["status"] = response.status if response else None
            result["title"] = await page.title()
            result["url"] = page.url
            result["content"] = await page.content()

            # Extract text content
            text = await page.evaluate("() => document.body.innerText")
            result["text"] = text[:2000]  # First 2000 chars

            # Check for SSL
            result["ssl_valid"] = page.url.startswith("https://")

            {"await page.screenshot(path='/tmp/screenshot.png')" if take_screenshot else ""}

        except Exception as e:
            result["error"] = str(e)
        finally:
            await browser.close()

    print(json.dumps(result))

asyncio.run(main())
'''

                # Write and execute script
                sandbox.filesystem.write('/tmp/fetch_url.py', script)
                proc = sandbox.commands.run('python /tmp/fetch_url.py')

                if proc.exit_code == 0 and proc.stdout:
                    import json
                    page_result = json.loads(proc.stdout)

                    result['success'] = 'error' not in page_result
                    result['title'] = page_result.get('title', '')
                    result['html'] = page_result.get('content', '')
                    result['content'] = page_result.get('text', '')
                    result['ssl_valid'] = page_result.get('ssl_valid', False)

                    # Analyze HTML for threats
                    if result['html']:
                        html_warnings = self._analyze_html_content(result['html'], url)
                        result['warnings'].extend(html_warnings)

                    # Get screenshot if requested
                    if take_screenshot:
                        screenshot_data = sandbox.filesystem.read('/tmp/screenshot.png')
                        result['screenshot'] = base64.b64encode(screenshot_data).decode()

                else:
                    result['error'] = proc.stderr or 'Failed to fetch URL'

            except Exception as e:
                result['error'] = str(e)
                result['warnings'].append(f'Sandbox error: {str(e)}')
            finally:
                # Clean up sandbox
                try:
                    sandbox.close()
                except Exception:
                    pass

        except Exception as e:
            result['error'] = str(e)
            result['warnings'].append(f'Failed to create sandbox: {str(e)}')

        # Calculate final safety score
        result['safety_score'] = self._calculate_safety_score(result)

        return result

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            # Parse the URL
            parsed = urlparse(url)

            # Check basic requirements
            if not parsed.scheme in ['http', 'https']:
                return False

            if not parsed.netloc:
                return False

            # Check that netloc has at least a domain
            if '.' not in parsed.netloc and parsed.netloc != 'localhost':
                return False

            # URL is valid if it has scheme and netloc
            return True
        except Exception:
            return False

    def _check_url_safety(self, url: str) -> List[str]:
        """
        Check URL for common phishing patterns.

        Returns:
            List of warning messages
        """
        warnings = []
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Check for suspicious TLDs
        for tld in SUSPICIOUS_TLDS:
            if domain.endswith(tld):
                warnings.append(f'Suspicious TLD detected: {tld}')
                break

        # Check for IP address instead of domain
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', domain):
            warnings.append('URL uses IP address instead of domain name')

        # Check for URL shorteners (potential obfuscation)
        url_shorteners = ['bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'ow.ly', 'is.gd']
        if any(shortener in domain for shortener in url_shorteners):
            warnings.append('URL shortener detected - destination is hidden')

        # Check for typosquatting of legitimate brands
        for brand in LEGITIMATE_BRANDS:
            if brand in domain and domain != f'{brand}.com':
                # Check for character substitutions (e.g., paypa1, g00gle)
                if re.search(rf'{brand[0]}[0-9o]{{{len(brand)-2},{len(brand)-1}}}', domain):
                    warnings.append(f'Potential typosquatting of {brand}')
                    break

        # Check for overly long domains (common in phishing)
        if len(domain) > 50:
            warnings.append('Unusually long domain name')

        # Check for multiple subdomains (e.g., paypal.login.secure.scam.com)
        subdomain_count = domain.count('.')
        if subdomain_count > 3:
            warnings.append(f'Multiple subdomains detected ({subdomain_count})')

        return warnings

    def _analyze_html_content(self, html: str, url: str) -> List[str]:
        """
        Analyze HTML content for suspicious patterns.

        Returns:
            List of warning messages
        """
        warnings = []

        if not BS4_AVAILABLE:
            return warnings

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Check for password input fields
            password_fields = soup.find_all('input', {'type': 'password'})
            if password_fields:
                warnings.append('Page contains password input fields')

            # Check for credit card input patterns
            credit_card_patterns = soup.find_all('input', {'name': re.compile(r'card|cvv|credit', re.I)})
            if credit_card_patterns:
                warnings.append('Page requests credit card information')

            # Check for suspicious iframes
            iframes = soup.find_all('iframe')
            external_iframes = [
                iframe for iframe in iframes
                if iframe.get('src') and not urlparse(iframe.get('src')).netloc in url
            ]
            if external_iframes:
                warnings.append(f'Page contains {len(external_iframes)} external iframes')

            # Check for obfuscated JavaScript
            scripts = soup.find_all('script')
            for script in scripts:
                script_content = script.string or ''
                if 'eval(' in script_content or 'unescape(' in script_content:
                    warnings.append('Page contains obfuscated JavaScript')
                    break

            # Check for meta refresh redirects
            meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
            if meta_refresh:
                warnings.append('Page uses meta refresh redirect')

        except Exception as e:
            warnings.append(f'HTML analysis error: {str(e)}')

        return warnings

    def _calculate_safety_score(self, result: Dict[str, Any]) -> int:
        """
        Calculate safety score based on analysis results.

        Returns:
            Score from 0-100 (higher is safer)
        """
        score = 100

        # Deduct for each warning
        warning_penalties = {
            'suspicious tld': 15,
            'ip address': 20,
            'url shortener': 10,
            'typosquatting': 30,
            'password input': 25,
            'credit card': 30,
            'external iframe': 15,
            'obfuscated javascript': 25,
            'meta refresh': 10,
            'long domain': 10,
            'multiple subdomains': 15,
        }

        for warning in result['warnings']:
            warning_lower = warning.lower()
            for pattern, penalty in warning_penalties.items():
                if pattern in warning_lower:
                    score -= penalty
                    break
            else:
                # Generic warning penalty
                score -= 5

        # Deduct for SSL issues
        if not result['ssl_valid']:
            score -= 15

        # Deduct for errors
        if result['error']:
            score -= 10

        return max(0, min(100, score))


class SandboxFileViewer:
    """
    File sandbox for safely opening and analyzing email attachments.
    """

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        """
        Initialize sandbox file viewer.

        Args:
            api_key: E2B API key (defaults to E2B_API_KEY env var)
            timeout: Timeout in seconds for sandbox operations
        """
        if not E2B_AVAILABLE:
            raise ImportError(
                "e2b library is required for sandbox functionality. "
                "Install with: pip install e2b"
            )

        # E2B uses environment variable E2B_API_KEY, so we set it if provided
        api_key_to_use = api_key or os.getenv('E2B_API_KEY') or os.getenv('MCP_GMAIL_E2B_API_KEY')
        if not api_key_to_use:
            raise ValueError(
                "E2B_API_KEY not set. Get your API key from https://e2b.dev"
            )

        # Set the environment variable for E2B to use
        os.environ['E2B_API_KEY'] = api_key_to_use
        self.timeout = timeout

    def open_file(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str
    ) -> Dict[str, Any]:
        """
        Open a file in a sandboxed environment and analyze it.

        Args:
            file_bytes: File content as bytes
            filename: Original filename
            mime_type: MIME type of the file

        Returns:
            Dictionary with file analysis and safety assessment
        """
        result = {
            'filename': filename,
            'mime_type': mime_type,
            'size': len(file_bytes),
            'success': False,
            'content': '',
            'safety_score': 100,
            'warnings': [],
            'file_type': None,
            'metadata': {},
            'error': None
        }

        try:
            # Analyze file header and metadata
            header_analysis = self._analyze_file_header(file_bytes, filename, mime_type)
            result.update(header_analysis)

            # Check for dangerous file extensions
            ext_warnings = self._check_file_extension(filename)
            result['warnings'].extend(ext_warnings)

            # Extract content based on file type
            if mime_type == 'application/pdf':
                content = self._extract_pdf_content(file_bytes)
                result['content'] = content
                result['success'] = True
            elif mime_type.startswith('text/'):
                result['content'] = file_bytes.decode('utf-8', errors='ignore')[:5000]
                result['success'] = True
            elif mime_type.startswith('image/'):
                result['content'] = f'Image file: {filename}'
                result['success'] = True
            else:
                result['content'] = f'Unsupported file type: {mime_type}'
                result['warnings'].append(f'Unsupported file type for preview: {mime_type}')

        except Exception as e:
            result['error'] = str(e)
            result['warnings'].append(f'File analysis error: {str(e)}')

        # Calculate final safety score
        result['safety_score'] = self._calculate_file_safety_score(result)

        return result

    def _analyze_file_header(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str
    ) -> Dict[str, Any]:
        """
        Analyze file header (magic bytes) to detect file type.

        Returns:
            Dictionary with analysis results
        """
        result = {
            'file_type': 'Unknown',
            'warnings': [],
            'metadata': {}
        }

        # Check magic bytes
        header = file_bytes[:8]
        detected_type = None

        for file_type, magic in MAGIC_BYTES.items():
            if header.startswith(magic):
                detected_type = file_type
                result['file_type'] = file_type
                break

        # Check for extension/type mismatch
        file_ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        if detected_type:
            if file_ext == 'pdf' and detected_type != 'pdf':
                result['warnings'].append(
                    f'File extension mismatch: Claims to be PDF but is {detected_type.upper()}'
                )
            elif file_ext == 'exe' and detected_type == 'exe':
                result['warnings'].append('Executable file detected')
            elif detected_type == 'exe' and file_ext != 'exe':
                result['warnings'].append(
                    f'DANGEROUS: Executable file disguised as .{file_ext}'
                )

        # Check for suspicious double extensions
        if filename.count('.') > 1:
            parts = filename.split('.')
            if len(parts) >= 3 and any(ext in parts[-2].lower() for ext in ['exe', 'bat', 'cmd']):
                result['warnings'].append(
                    f'Suspicious double extension: {parts[-2]}.{parts[-1]}'
                )

        return result

    def _check_file_extension(self, filename: str) -> List[str]:
        """
        Check for dangerous file extensions.

        Returns:
            List of warning messages
        """
        warnings = []

        file_ext = ('.' + filename.rsplit('.', 1)[-1].lower()) if '.' in filename else ''

        if file_ext in DANGEROUS_EXTENSIONS:
            warnings.append(f'DANGEROUS: Executable file type {file_ext}')

        # Check for macro-enabled Office documents
        macro_extensions = {'.docm', '.xlsm', '.pptm', '.dotm', '.xltm'}
        if file_ext in macro_extensions:
            warnings.append(f'Macro-enabled document detected: {file_ext}')

        return warnings

    def _extract_pdf_content(self, pdf_bytes: bytes) -> str:
        """
        Extract text from PDF file.

        Returns:
            Extracted text content
        """
        try:
            from pypdf import PdfReader

            pdf_file = io.BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)

            # Extract text from first few pages
            text_parts = []
            for i, page in enumerate(reader.pages[:3]):  # First 3 pages
                text = page.extract_text()
                if text.strip():
                    text_parts.append(f"--- Page {i + 1} ---\n{text}")

            full_text = "\n\n".join(text_parts)

            # Limit text length
            if len(full_text) > 5000:
                full_text = full_text[:5000] + "\n\n... [Content truncated]"

            return full_text

        except Exception as e:
            return f"Error extracting PDF text: {str(e)}"

    def _calculate_file_safety_score(self, result: Dict[str, Any]) -> int:
        """
        Calculate file safety score based on analysis results.

        Returns:
            Score from 0-100 (higher is safer)
        """
        score = 100

        # Severe penalties
        for warning in result['warnings']:
            warning_lower = warning.lower()
            if 'dangerous' in warning_lower or 'executable' in warning_lower:
                score -= 40
            elif 'disguised' in warning_lower or 'mismatch' in warning_lower:
                score -= 35
            elif 'macro-enabled' in warning_lower:
                score -= 20
            elif 'suspicious' in warning_lower:
                score -= 15
            else:
                score -= 5

        # Deduct for errors
        if result['error']:
            score -= 10

        # Deduct for unknown file type
        if result['file_type'] == 'Unknown':
            score -= 10

        return max(0, min(100, score))


# Utility functions

def extract_urls_from_email(message_body: str) -> List[str]:
    """
    Extract all URLs from email message body.

    Args:
        message_body: Email body text (plain or HTML)

    Returns:
        List of URLs found in the message
    """
    import html

    # Decode HTML entities first (e.g., &gt; -> >, &amp; -> &)
    decoded_body = html.unescape(message_body)

    # Enhanced URL regex pattern that handles more characters
    # This pattern matches http/https URLs with various characters including URL-encoded ones
    url_pattern = re.compile(
        r'https?://[^\s<>"{}|\\^`\[\]]+',
        re.IGNORECASE
    )

    urls = url_pattern.findall(decoded_body)

    # Clean up URLs - remove trailing punctuation and HTML artifacts
    cleaned_urls = []
    for url in urls:
        # Remove common trailing characters that aren't part of URLs
        url = url.rstrip('.,;:!?)\'">')

        # Remove HTML tags that might be at the end (e.g., </a>)
        url = re.sub(r'<[^>]+>$', '', url)

        # Only include if it looks like a complete URL
        if '://' in url and len(url) > 10:
            cleaned_urls.append(url)

    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in cleaned_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    return unique_urls


def format_safety_report(
    url: Optional[str] = None,
    filename: Optional[str] = None,
    score: int = 100,
    warnings: List[str] = None,
    content: str = '',
    metadata: Dict[str, Any] = None
) -> str:
    """
    Format a safety analysis report for display.

    Args:
        url: URL being analyzed (if applicable)
        filename: Filename being analyzed (if applicable)
        score: Safety score (0-100)
        warnings: List of warning messages
        content: Content summary
        metadata: Additional metadata

    Returns:
        Formatted report string
    """
    warnings = warnings or []
    metadata = metadata or {}

    # Determine status emoji and text
    if score >= 90:
        status_emoji = '✅'
        status_text = 'Safe'
    elif score >= 70:
        status_emoji = '✅'
        status_text = 'Likely Safe'
    elif score >= 40:
        status_emoji = '⚠️ '
        status_text = 'Suspicious'
    else:
        status_emoji = '❌'
        status_text = 'DANGEROUS'

    # Build report
    lines = []

    # Header
    if url:
        lines.append(f'🔗 Link Preview: {url}')
    elif filename:
        lines.append(f'📄 File Preview: {filename}')

    lines.append('')
    lines.append(f'Safety Score: {score}/100 ({status_text})')
    lines.append(f'Status: {status_emoji} {status_text}')
    lines.append('')

    # Content summary
    if content:
        lines.append('Content Summary:')
        # Truncate if too long
        content_preview = content[:500] if len(content) > 500 else content
        for line in content_preview.split('\n'):
            lines.append(f'  {line}')
        if len(content) > 500:
            lines.append('  ... [Content truncated]')
        lines.append('')

    # Metadata
    if metadata:
        lines.append('File Information:')
        for key, value in metadata.items():
            lines.append(f'  {key}: {value}')
        lines.append('')

    # Warnings
    if warnings:
        lines.append('Safety Checks:')
        for warning in warnings:
            # Determine warning emoji
            warning_lower = warning.lower()
            if 'dangerous' in warning_lower or 'executable' in warning_lower:
                emoji = '❌'
            elif 'suspicious' in warning_lower or 'warning' in warning_lower:
                emoji = '⚠️ '
            else:
                emoji = '⚠️ '
            lines.append(f'  {emoji} {warning}')
        lines.append('')

    # Recommendation
    lines.append('Recommendation:')
    if score >= 70:
        lines.append('  This appears safe to open.')
    elif score >= 40:
        lines.append('  Proceed with caution. Review warnings carefully.')
    else:
        lines.append('  DO NOT OPEN. High risk of malicious content.')

    return '\n'.join(lines)


def get_sandbox_browser(api_key: Optional[str] = None, timeout: int = 30) -> SandboxBrowser:
    """
    Get a SandboxBrowser instance.

    Args:
        api_key: E2B API key (optional)
        timeout: Sandbox timeout in seconds

    Returns:
        SandboxBrowser instance
    """
    return SandboxBrowser(api_key=api_key, timeout=timeout)


def get_sandbox_file_viewer(api_key: Optional[str] = None, timeout: int = 30) -> SandboxFileViewer:
    """
    Get a SandboxFileViewer instance.

    Args:
        api_key: E2B API key (optional)
        timeout: Sandbox timeout in seconds

    Returns:
        SandboxFileViewer instance
    """
    return SandboxFileViewer(api_key=api_key, timeout=timeout)
