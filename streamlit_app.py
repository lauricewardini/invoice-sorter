import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime
import io
import re
import fitz  # PyMuPDF
from tempfile import NamedTemporaryFile
from collections import defaultdict

st.set_page_config(page_title="🍩 Donut Land Invoice Sorter", layout="centered")
st.title("🍩 Donut Land Invoice Sorter")
st.write("Upload your QuickBooks invoices PDF and we’ll sort them by date and packing note, then insert a daily donut count summary right after each day’s invoices.")

uploaded_file = st.file_uploader("📄 Upload PDF", type=["pdf"])

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
    valid_items = {
        "Maple Bar", "Chocolate Bar", "Tiger Bar", "Glazed Raised", "Chocolate Raised", "Cream Filled", "Raspberry Filled", 
        "Lemon Filled", "Sugar Raised", "Twist", "Apple Fritter", "Raspberry Fritter", "Blueberry Fritter", "Bear Claw", 
        "Frosted Claw", "Berry Claw", "Cin Roll", "Frosted Roll", "Buttermilk Bar (Glazed)", "Buttermilk Bar (Plain)", "French Cruller",
        "French Cruller (Chocolate)", "French Cruller (Maple)", "Old Fashioned (Glazed)", "Old Fashioned (Chocolate)", 
        "Old Fashioned (Maple)", "Old Fashioned (Plain)", "Rainbow Sprinkle Cake (Vanilla)", "Plain Cake w/ Choc Icing", 
        "Plain Cake with Choc Sprinkles", "Devil's Food", "Devil's Food with Sprinkles", "Coconut Cake (Vanilla)", 
        "Cinnamon Crumb", "Blueberry Cake", "Glazed Cake Donut", "Plain Cake"
    }

    lines = text.splitlines()
    for line in lines:
        for item in valid_items:
            if item.lower() in line.lower():
                qty_match = re.search(r'(\d+)', line)
                if qty_match:
                    qty = int(qty_match.group(1))
                    item_counts[item] += qty

    return item_counts

def create_summary_page(date, item_summary):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), f"Totals for {date.strftime('%m/%d/%Y')}", fontsize=14)
    y = 100
    for item, qty in sorted(item_summary.items()):
        page.insert_text((50, y), f"{item}: {qty}", fontsize=12)
        y += 20
    temp_file = NamedTemporaryFile(delete=False, suffix=".pdf")
    doc.save(temp_file.name)
    doc.close()
    return temp_file.name

if uploaded_file is not None:
    st.success("PDF uploaded! Click the button below to start sorting.")
    if st.button("🔃 Sort My Invoices"):
        with st.spinner("Sorting invoices and generating summaries..."):
            pdf_bytes = uploaded_file.read()
            reader = PdfReader(io.BytesIO(pdf_bytes))

            invoice_data = []
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
            reader_pages = reader.pages
            current_day = None
            daily_items = defaultdict(int)

            for idx, (date, _, page_indices, items) in enumerate(sorted_invoices):
                if current_day and date != current_day:
                    summary_path = create_summary_page(current_day, daily_items)
                    with open(summary_path, "rb") as f:
                        summary_reader = PdfReader(f)
                        for page in summary_reader.pages:
                            writer.add_page(page)
                    daily_items = defaultdict(int)

                current_day = date
                for item, qty in items.items():
                    daily_items[item] += qty
                for page_index in page_indices:
                    writer.add_page(reader_pages[page_index])
                if idx == len(sorted_invoices) - 1:
                    summary_path = create_summary_page(current_day, daily_items)
                    with open(summary_path, "rb") as f:
                        summary_reader = PdfReader(f)
                        for page in summary_reader.pages:
                            writer.add_page(page)

            with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_output:
                writer.write(temp_output)
                temp_output_path = temp_output.name

            st.success("✅ Done! Download your sorted PDF with daily summaries below:")
            st.download_button(
                "🗕️ Download PDF with Daily Donut Totals",
                open(temp_output_path, "rb"),
                file_name="sorted " + uploaded_file.name,
                mime="application/pdf"
            )
