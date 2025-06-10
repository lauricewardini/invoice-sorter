import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime
import io
import re
import fitz  # PyMuPDF
from tempfile import NamedTemporaryFile
import pandas as pd
from collections import defaultdict

st.set_page_config(page_title="🍩 Donut Land Invoice Sorter", layout="centered")
st.title("🍩 Donut Land Invoice Sorter")
st.write("Upload your QuickBooks invoices PDF below and we'll sort them by date and packing note (Brown Boxes, Trays, etc), and generate a donut count summary per day.")

uploaded_file = st.file_uploader("📤 Upload PDF", type=["pdf"])

if uploaded_file is not None:
    st.success("PDF uploaded! Click the button below to start sorting.")
    if st.button("🔃 Sort My Invoices"):
        with st.spinner("Sorting invoices and generating summaries..."):
            pdf_bytes = uploaded_file.read()
            reader = PdfReader(io.BytesIO(pdf_bytes))

            invoice_data = []

            def extract_date(text):
                match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', text)
                if match:
                    date_str = match.group(1)
                    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
                        try:
                            return datetime.strptime(date_str, fmt).date()
                        except ValueError:
                            continue
                return datetime(1900, 1, 1).date()

def extract_items(text):
    item_counts = defaultdict(int)

    # Define only the donut names you care about
    valid_items = {
        "Maple Bar", "Chocolate Bar", "Raspberry Filled", "Cream Filled",
        "Twist", "Apple Fritter", "Bear Claw", "Cin Roll", "Buttermilk Bar",
        "Glazed Raised", "Old Fashioned", "Vanilla Cake", "Chocolate Cake",
        "Sugar Raised", "Devils Food", "Coconut Bar"
    }

    lines = text.splitlines()
    for line in lines:
        match = re.match(r'^\\s*(\\d+)\\s+([A-Za-z ]+)', line.strip())
        if match:
            qty = int(match.group(1))
            item = match.group(2).strip().title()

            if item in valid_items:
                item_counts[item] += qty

    return item_counts

            current_invoice = {
                'date': None,
                'note': None,
                'pages': [],
                'items': defaultdict(int)
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
                            current_invoice['pages'],
                            current_invoice['items']
                        ))

                    current_invoice = {
                        'date': extract_date(all_text),
                        'note': 'unknown',
                        'pages': [i],
                        'items': extract_items(text)
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
                    page_items = extract_items(text)
                    for k, v in page_items.items():
                        current_invoice['items'][k] += v

            if current_invoice['pages']:
                invoice_data.append((
                    current_invoice['date'],
                    current_invoice['note'],
                    current_invoice['pages'],
                    current_invoice['items']
                ))

            sorted_invoices = sorted(invoice_data, key=lambda x: (x[0], x[1]))

            writer = PdfWriter()
            summary_by_date = defaultdict(lambda: defaultdict(int))

            for date, _, page_indices, items in sorted_invoices:
                for item, qty in items.items():
                    summary_by_date[date][item] += qty
                for page_index in page_indices:
                    writer.add_page(reader.pages[page_index])

            # Save sorted PDF temporarily
            with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_sorted_file:
                writer.write(temp_sorted_file)
                sorted_pdf_path = temp_sorted_file.name

            def create_daily_summaries_pdf(summary_by_date):
                doc = fitz.open()
                for date in sorted(summary_by_date.keys()):
                    page = doc.new_page()
                    page.insert_text((50, 50), f"Summary for {date.strftime('%m/%d/%Y')}", fontsize=14)

                    y = 100
                    for item, qty in summary_by_date[date].items():
                        page.insert_text((50, y), f"{item}: {qty}", fontsize=12)
                        y += 20
                temp_file = NamedTemporaryFile(delete=False, suffix=".pdf")
                doc.save(temp_file.name)
                doc.close()
                return temp_file.name

            def append_summary_to_pdf(original_pdf_path, summary_by_date, output_path):
                main_doc = fitz.open(original_pdf_path)
                summary_path = create_daily_summaries_pdf(summary_by_date)
                summary_doc = fitz.open(summary_path)
                main_doc.insert_pdf(summary_doc)
                main_doc.save(output_path)
                main_doc.close()

            final_pdf_path = "invoices_with_summary.pdf"
            final_filename = "sorted " + uploaded_file.name

            append_summary_to_pdf(sorted_pdf_path, summary_by_date, final_pdf_path)

            st.success("✅ Done! Download your sorted + daily summarized PDF below:")
            with open(final_pdf_path, "rb") as f:
                st.download_button(
                    "📅 Download Final PDF with Per-Day Summary",
                    f.read(),
                    file_name=final_filename,
                    mime="application/pdf"
                )

