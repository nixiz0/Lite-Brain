import os, uuid
import requests
from pdf2image import convert_from_path
from CONFIG import OCR_API_URL, OCR_API_TIMEOUT_S, MIN_CHAR_PER_PAGE, AVG_MIN_CHARS, BLANK_PAGE_THRESHOLD


# =========== OCR CALL API ===========
def ocr_api(file_path, timeout=OCR_API_TIMEOUT_S):
    """
    Calls the OCR API with a file and returns extracted text.

    Args:
        file_path (str): Local path to the file to OCR.
        timeout (int): Request timeout in seconds.

    Returns:
        str: Extracted text.

    Raises:
        Exception: For non-200 API responses.
    """
    # Important: OCR API infers type from the filename, not Content-Type
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f)}
        response = requests.post(OCR_API_URL, files=files, timeout=timeout)

    if response.status_code == 200:
        data = response.json()
        # API returns text under "extracted_text"
        return data.get("extracted_text", "")
    else:
        raise Exception(f"OCR API error {response.status_code}: {response.text}")


# =========== OCR ON PDF PAGES ===========
def ocr_pages(pages_text, pdf_path):
    """
    Performs selective per-page OCR for a PDF:
      - Adds native text first when available.
      - If native text is insufficient, runs OCR on that page only.
    Returns a list of ordered chunks: {text, source, page_number}.
    """
    chunks = []

    for i, page_text in enumerate(pages_text):
        page_number = i + 1
        txt = (page_text or "").strip()

        # Add native text when available
        if txt:
            chunks.append(
                {
                    "text": txt,
                    "source": "native",
                    "page_number": page_number,
                }
            )

        # Run OCR if native text is below the quality threshold
        if len(txt) < MIN_CHAR_PER_PAGE:
            # Convert only this page to an image
            images = convert_from_path(
                pdf_path,
                first_page=page_number,
                last_page=page_number,
            )
            page_img = images[0]

            # Save temporary image for OCR API
            img_tmp_name = f"ocr_page_{page_number}_{uuid.uuid4()}.png"
            img_path = os.path.join("/tmp", img_tmp_name)
            page_img.save(img_path)

            try:
                # Extract OCR text for that page
                ocr_text = ocr_api(img_path).strip()
            finally:
                # Cleanup: ensure temp file is removed safely
                try:
                    if os.path.exists(img_path):
                        os.remove(img_path)
                except OSError:
                    pass

            # Append OCR text if successful
            if ocr_text:
                chunks.append(
                    {
                        "text": ocr_text,
                        "source": "ocr",
                        "page_number": page_number,
                    }
                )

    return chunks


# =========== Function Analysis PDF need OCR or not ===========
def analyze_pdf_need_ocr(pages_text):
    """
    Analyze extracted text from PDF pages to decide if OCR is needed.

    Returns:
        needs_ocr (bool): True if OCR is recommended (many blank/short pages).
        total_pages (int): Number of pages in the PDF.
        blank_pages (int): Count of pages with very little text.
        total_chars (int): Total number of characters in all pages.
        avg_chars_per_page (int): Average characters per page.
    """
    total_pages = len(pages_text)

    # Count pages with less than MIN_CHAR_PER_PAGE non-whitespace characters
    blank_pages = sum(
        1 for page in pages_text if len((page or "").strip()) < MIN_CHAR_PER_PAGE
    )
    total_chars = sum(len(page or "") for page in pages_text)
    avg_chars_per_page = int(total_chars / total_pages) if total_pages else 0

    # Need OCR if too many blank pages or pages are too short
    needs_ocr = (
        blank_pages > total_pages * BLANK_PAGE_THRESHOLD
        or avg_chars_per_page < AVG_MIN_CHARS
    )
    return needs_ocr, total_pages, blank_pages, total_chars, avg_chars_per_page
