import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime
import io
import re
import fitz  # PyMuPDF
from tempfile import NamedTemporaryFile
import pandas as pd

st.set_page_config(page_title="🍩 Donut Land Invoice Sorter", layout="centered")
st.title("🍩 Donut Land Invoice Sorter")
st.write("Upload your QuickBooks invoices PDF below and we'll sort them by date and packing note (Brown Boxes, Trays, etc).")

uploaded_file = st.file_uploader("📤 Upload PDF", type=["pdf"])

if uploaded_file is not None:
    st.success("PDF uploaded! Click the button below to start sorting.")
    if st.button("🔃 Sort My Invoices"):
        with st.spinner("Sorting invoices... this may take 5–10 seconds"):
            pdf_bytes = uploaded_file.read()
            reader = PdfReader(io.BytesIO(pdf_bytes))

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
                'pages': []
            }

            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                lines = text.splitlines()
                all_text = " ".join(lines)
                first_block = "\n".join(lines[:10]).lower()

                is_new_invoice = 'invoice' in first_block

                if is_new_invoice:
                    if current_invoice['pages']:
                        invoice_data.append((
                            current_invoice['date'],
                            current_invoice['note'],
                            current_invoice['pages']
                        ))

                    current_invoice = {
                        'date': extract_date(all_text),
                        'note': 'unknown',
                        'pages': [i]
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

            if current_invoice['pages']:
                invoice_data.append((
                    current_invoice['date'],
                    current_invoice['note'],
                    current_invoice['pages']
                ))

            sorted_invoices = sorted(invoice_data, key=lambda x: (x[0], x[1]))

            writer = PdfWriter()
            for _, _, page_indices in sorted_invoices:
                for page_index in page_indices:
                    writer.add_page(reader.pages[page_index])

            with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_sorted_file:
                writer.write(temp_sorted_file)
                sorted_pdf_path = temp_sorted_file.name

            # TEMP: Fake data for demo. Replace with actual quantity parsing later.
            summary_df = pd.DataFrame({
                "Item": ["Maple Bar", "Chocolate Bar", "Apple Fritter"],
                "Total Quantity": [35, 50, 20]
            })

            def create_summary_pdf(summary_df):
                doc = fitz.open()
                page = doc.new_page()

                page.insert_text((50, 50), "TOTAL ITEMS SUMMARY", fontsize=16, bold=True)

                y = 100
                for index, row in summary_df.iterrows():
                    item = row['Item']
                    qty = row['Total Quantity']
                    page.insert_text((50, y), f"{item}: {qty}", fontsize=12)
                    y += 20

                temp_file = NamedTemporaryFile(delete=False, suffix=".pdf")
                doc.save(temp_file.name)
                doc.close()
                return temp_file.name

            def append_summary_to_pdf(original_pdf_path, summary_df, output_path):
                main_doc = fitz.open(original_pdf_path)
                summary_path = create_summary_pdf(summary_df)
                summary_doc = fitz.open(summary_path)

                main_doc.insert_pdf(summary_doc)
                main_doc.save(output_path)
                main_doc.close()

            final_pdf_path = "invoices_with_summary.pdf"
            final_filename = "sorted " + uploaded_file.name

            append_summary_to_pdf(sorted_pdf_path, summary_df, final_pdf_path)

            st.success("✅ Done! Download your sorted + summarized invoices below:")
            with open(final_pdf_path, "rb") as f:
                st.download_button(
                    "📅 Download Final PDF with Totals Summary",
                    f.read(),
                    file_name=final_filename,
                    mime="application/pdf"
                )

