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

    with fitz.open(file_path) as pdf:
        for page_index, page in enumerate(pdf, start=1):
            text = clean_page_text(page.get_text("text"))
            if len(text) < 30:
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

    return documents, warning
