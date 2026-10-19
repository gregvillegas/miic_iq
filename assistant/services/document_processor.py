import os
import re
import csv
from typing import List, Dict, Any
from django.conf import settings
from pypdf import PdfReader
import docx
import openpyxl


class DocumentParser:
    """
    Parses various document types (PDF, DOCX, TXT, MD, XLSX, CSV) into
    a list of page/section-oriented text units:
    [{"page_number": 1, "text": "...", "metadata": {...}}]
    """

    @classmethod
    def parse_file(cls, file_path: str, file_type: str) -> List[Dict[str, Any]]:
        file_type = file_type.lower().strip('.')
        if file_type == 'pdf':
            return cls._parse_pdf(file_path)
        elif file_type in ['docx', 'doc']:
            return cls._parse_docx(file_path)
        elif file_type in ['txt', 'md']:
            return cls._parse_text(file_path)
        elif file_type in ['xlsx', 'xls']:
            return cls._parse_xlsx(file_path)
        elif file_type == 'csv':
            return cls._parse_csv(file_path)
        else:
            # Fallback to plain text
            return cls._parse_text(file_path)

    @staticmethod
    def _parse_pdf(file_path: str) -> List[Dict[str, Any]]:
        pages = []
        reader = PdfReader(file_path)
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ''
            clean_text = text.strip()
            if clean_text:
                pages.append({
                    'page_number': idx + 1,
                    'text': clean_text,
                    'metadata': {'total_pages': len(reader.pages)}
                })
        return pages

    @staticmethod
    def _parse_docx(file_path: str) -> List[Dict[str, Any]]:
        doc = docx.Document(file_path)
        sections = []
        current_text = []
        page_counter = 1

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            # If paragraph looks like a top-level heading or is long, break into logical pages
            current_text.append(text)
            if len("\n".join(current_text)) > 2500:
                sections.append({
                    'page_number': page_counter,
                    'text': "\n\n".join(current_text),
                    'metadata': {}
                })
                page_counter += 1
                current_text = []

        # Also extract text from tables
        for table in doc.tables:
            table_rows = []
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                table_rows.append(" | ".join(cells))
            if table_rows:
                current_text.append("\n[Table Data]:\n" + "\n".join(table_rows))

        if current_text:
            sections.append({
                'page_number': page_counter,
                'text': "\n\n".join(current_text),
                'metadata': {}
            })

        return sections if sections else [{'page_number': 1, 'text': 'Empty document', 'metadata': {}}]

    @staticmethod
    def _parse_text(file_path: str) -> List[Dict[str, Any]]:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        # Split into logical sections by Markdown headers or 3000-char blocks
        blocks = re.split(r'\n(?=#{1,3}\s)', content)
        if len(blocks) <= 1:
            # Split by double newline chunks if no headers
            blocks = [content]

        pages = []
        page_num = 1
        for b in blocks:
            b_clean = b.strip()
            if b_clean:
                pages.append({
                    'page_number': page_num,
                    'text': b_clean,
                    'metadata': {}
                })
                page_num += 1

        return pages if pages else [{'page_number': 1, 'text': '', 'metadata': {}}]

    @staticmethod
    def _parse_xlsx(file_path: str) -> List[Dict[str, Any]]:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        pages = []
        page_num = 1
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows_data = []
            for row in ws.iter_rows(values_only=True):
                non_empty = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
                if non_empty:
                    rows_data.append(" | ".join(non_empty))
            if rows_data:
                sheet_text = f"Sheet: {sheet_name}\n" + "\n".join(rows_data)
                pages.append({
                    'page_number': page_num,
                    'text': sheet_text,
                    'metadata': {'sheet_name': sheet_name}
                })
                page_num += 1
        return pages if pages else [{'page_number': 1, 'text': '', 'metadata': {}}]

    @staticmethod
    def _parse_csv(file_path: str) -> List[Dict[str, Any]]:
        rows = []
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            for r in reader:
                cleaned = [cell.strip() for cell in r if cell.strip()]
                if cleaned:
                    rows.append(" | ".join(cleaned))
        
        # Paginate every 50 rows
        pages = []
        batch_size = 50
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            pages.append({
                'page_number': (i // batch_size) + 1,
                'text': "\n".join(batch),
                'metadata': {'row_range': f"{i+1}-{i+len(batch)}"}
            })
        return pages if pages else [{'page_number': 1, 'text': '', 'metadata': {}}]


class RecursiveChunker:
    """
    Splits text into chunks of roughly 500-1000 tokens (~2000-4000 characters)
    with ~100 token overlap (approx 400 characters).
    Preserves document metadata and page numbers.
    """

    def __init__(self, target_chars: int = 2400, overlap_chars: int = 400):
        self.target_chars = target_chars
        self.overlap_chars = overlap_chars

    def chunk_document_pages(self, pages: List[Dict[str, Any]], doc_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        chunks = []
        chunk_idx = 0

        for page in pages:
            text = page['text'].strip()
            page_num = page['page_number']
            if not text:
                continue

            # If the page text fits in one chunk
            if len(text) <= self.target_chars:
                token_count = max(1, len(text.split()))
                chunks.append({
                    'chunk_index': chunk_idx,
                    'content': text,
                    'token_count': token_count,
                    'page_number': page_num,
                    'metadata': {
                        **doc_metadata,
                        **page.get('metadata', {}),
                        'page_number': page_num,
                        'chunk_index': chunk_idx
                    }
                })
                chunk_idx += 1
                continue

            # Text needs subdivision
            sub_chunks = self._split_text(text)
            for sub_text in sub_chunks:
                if not sub_text.strip():
                    continue
                token_count = max(1, len(sub_text.split()))
                chunks.append({
                    'chunk_index': chunk_idx,
                    'content': sub_text.strip(),
                    'token_count': token_count,
                    'page_number': page_num,
                    'metadata': {
                        **doc_metadata,
                        **page.get('metadata', {}),
                        'page_number': page_num,
                        'chunk_index': chunk_idx
                    }
                })
                chunk_idx += 1

        return chunks

    def _split_text(self, text: str) -> List[str]:
        # Split recursively on paragraph breaks, then sentences, then fallback
        paragraphs = text.split("\n\n")
        chunks = []
        current = ""

        for p in paragraphs:
            p = p.strip()
            if not p:
                continue

            if len(current) + len(p) + 2 <= self.target_chars:
                current = (current + "\n\n" + p).strip() if current else p
            else:
                if current:
                    chunks.append(current)
                    # Add overlap from previous
                    overlap = current[-self.overlap_chars:] if len(current) > self.overlap_chars else ""
                    current = (overlap + "\n\n" + p).strip()
                else:
                    # Paragraph itself is too large, split by sentences or chunks
                    sentences = re.split(r'(?<=[.!?])\s+', p)
                    sub_buf = ""
                    for s in sentences:
                        if len(sub_buf) + len(s) + 1 <= self.target_chars:
                            sub_buf = (sub_buf + " " + s).strip() if sub_buf else s
                        else:
                            if sub_buf:
                                chunks.append(sub_buf)
                                overlap = sub_buf[-self.overlap_chars:] if len(sub_buf) > self.overlap_chars else ""
                                sub_buf = (overlap + " " + s).strip()
                            else:
                                # Hard slice
                                for k in range(0, len(s), self.target_chars - self.overlap_chars):
                                    chunks.append(s[k:k + self.target_chars])
                    if sub_buf:
                        current = sub_buf

        if current:
            chunks.append(current)

        return chunks
