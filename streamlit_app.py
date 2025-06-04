import streamlit as st
import pytesseract
from pdf2image import convert_from_bytes
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime
from PIL import Image
import tempfile
import io
import re

st.set_page_config(page_title="🍩 Donut Land Invoice Sorter", layout="centered")
st.title("🍩 Donut Land Invoice Sorter")
st.write("Upload your QuickBooks invoices PDF below and we'll sort them by date and packing note (Box, Morning, Tray).")

uploaded_file = st.file_uploader("📤 Upload PDF", type=["pdf"])

if uploaded_file is not None:
    st.success("PDF uploaded! Click the button below to start sorting.")
    if st.button("🔃 Sort My Invoices"):
        with st.spinner("Sorting invoices... this may take 15–30 seconds"):
            pdf_bytes = uploaded_file.read()
            reader = PdfReader(io.BytesIO(pdf_bytes))
            images = convert_from_bytes(pdf_bytes, dpi=150)

            invoice_data = []

            def extract_date(text):
                match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', text)
                if match:
                    date_str = match.group(1)
                    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
                return datetime(1900, 1, 1)

            current_invoice = {
                'date': None,
                'note': None,
                'pages': [],
                'sources': []
            }

            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                source = 'pdf'

                if not text or text.strip() == "":
                    text = pytesseract.image_to_string(images[i])
                    source = 'img'

                lines = text.splitlines()
                all_text = " ".join(lines)
                first_block = "\n".join(lines[:10]).lower()

                is_new_invoice = 'invoice' in first_block

                if is_new_invoice:
                    if current_invoice['pages']:
                        invoice_data.append((
                            current_invoice['date'],
                            current_invoice['note'],
                            current_invoice['pages'],
                            current_invoice['sources']
                        ))

                    current_invoice = {
                        'date': extract_date(all_text),
                        'note': 'unknown',
                        'pages': [i],
                        'sources': [source]
                    }

                    for l in lines:
                        l_lower = l.lower()
                        if 'box' in l_lower:
                            current_invoice['note'] = 'box'
                            break
                        elif 'tray' in l_lower:
                            current_invoice['note'] = 'tray'
                            break
                        elif 'morning' in l_lower:
                            current_invoice['note'] = 'morning'
                            break
                else:
                    current_invoice['pages'].append(i)
                    current_invoice['sources'].append(source)

            if current_invoice['pages']:
                invoice_data.append((
                    current_invoice['date'],
                    current_invoice['note'],
                    current_invoice['pages'],
                    current_invoice['sources']
                ))

            sorted_invoices = sorted(invoice_data, key=lambda x: (x[0], x[1]))

            writer = PdfWriter()
            for _, _, page_indices, sources in sorted_invoices:
                for page_index, source in zip(page_indices, sources):
                    if source == 'pdf':
                        writer.add_page(reader.pages[page_index])
                    else:
                        img = images[page_index]
                        temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
                        img.convert('RGB').save(temp_path)
                        with open(temp_path, 'rb') as f:
                            fallback_reader = PdfReader(f)
                            writer.add_page(fallback_reader.pages[0])

            output_pdf = io.BytesIO()
            writer.write(output_pdf)
            output_pdf.seek(0)

            st.success("✅ Done! Download your sorted PDF below:")
            st.download_button(
                label="📥 Download Sorted Invoices",
                data=output_pdf,
                file_name="sorted_invoices.pdf",
                mime="application/pdf"
            )
