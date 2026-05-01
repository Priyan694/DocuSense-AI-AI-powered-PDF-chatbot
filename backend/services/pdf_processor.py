import re
from pathlib import Path

import fitz
from langchain_core.documents import Document


def clean_page_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_documents_from_pdf(file_path: Path, pdf_name: str) -> tuple[list[Document], str | None]:
    documents: list[Document] = []
    low_text_pages = 0

    with fitz.open(file_path) as pdf:
        for page_index, page in enumerate(pdf, start=1):
            text = clean_page_text(page.get_text("text"))
            if len(text) < 30:
                low_text_pages += 1
                continue

            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "pdf_name": pdf_name,
                        "page_number": page_index,
                    },
                )
            )

    warning = None
    if not documents:
        warning = "No readable text found. OCR may be required."
    elif low_text_pages:
        warning = f"{low_text_pages} page(s) had little or no readable text."

    return documents, warning

