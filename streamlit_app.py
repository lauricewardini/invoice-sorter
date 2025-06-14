import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime
import io
import re
import fitz  # PyMuPDF
from tempfile import NamedTemporaryFile
from collections import defaultdict, OrderedDict
import pandas as pd
from rapidfuzz import process, fuzz

st.set_page_config(page_title="🍩 Donut Land Invoice Sorter", layout="centered")
st.title("🍩 Donut Land Invoice Sorter")
st.write("This app automatically checks your live Google Sheet for the vendor order and sorts invoices according to date, packing note, route, and vendor order.")

GOOGLE_SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRHPqLmzPV7uNIhjfmvAtvr-1P1rs88LadRLAHoK4Q-QfTcimSo8_rD0FnUpURnjeda5b0UV9XD1Oyt/pub?output=csv"

uploaded_file = st.file_uploader("📄 Upload QuickBooks Invoices PDF", type=["pdf"])

valid_items_order = [
    "Maple Bar", "Chocolate Bar", "Tiger Bar", "Glazed Raised", "Chocolate Raised", "Cream Filled", "Maple Cream Filled", "Raspberry Filled", 
    "Lemon Filled", "Sugar Raised", "Twist", "Apple Fritter", "Raspberry Fritter", "Blueberry Fritter", "Bear Claw", 
    "Frosted Claw", "Berry Claw", "Cin Roll", "Frosted Roll", "Buttermilk Bar (Glazed)", "Buttermilk Bar (Plain)", "French Cruller (Glazed)",
    "French Cruller (Chocolate)", "French Cruller (Maple)", "Old Fashioned (Glazed)", "Old Fashioned (Chocolate)", 
    "Old Fashioned (Maple)", "Old Fashioned (Plain)", "Rainbow Sprinkle Cake (Vanilla)", "Plain Cake w/ Choc Icing", 
    "Plain Cake with Choc Sprinkles", "Chocolate Frosted Cake (NO SPRINKLES)", "Devil's Food", "Devil's Food with Sprinkles", 
    "Coconut Cake (Vanilla)", "Cinnamon Crumb", "Blueberry Cake", "Glazed Cake Donut", "Plain Cake", "Donuts", "Fancy Donuts", 
    "Assorted Regular Donuts", "Assorted Fancy Donuts", "Assorted Cake", "Assorted Cake (NO PLAIN, NO SPRINKLES)", "Mixed Muffins"
]
valid_items = set(valid_items_order)

donuts_per_screen = {
    "Maple Bar": 20,
    "Chocolate Bar": 20,
    "Glazed Raised": 35,
    "Chocolate Raised": 35,
    "Cream Filled": 35,
    "Raspberry Filled": 35,
    "Twist": 20,
    "Apple Fritter": 20,
    "Raspberry Fritter": 20,
    "Blueberry Fritter": 20,
    "Bear Claw": 20,
}

packing_note_order = {'morning': 0, 'box': 1, 'tray': 2}
route_order = {'route 1': 0, 'route 2': 1}

def normalize_packing_note(note):
    note = str(note).lower()
    if "box" in note:
        return "box"
    elif "tray" in note:
        return "tray"
    elif "morning" in note:
        return "morning"
    return note

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

valid_items = set(i.lower() for i in valid_items_order)

def extract_items(text):
    item_counts = defaultdict(int)
    lines = text.splitlines()

    # Sort by length descending to prioritize longest matches first
    sorted_items = sorted(valid_items_order, key=lambda x: -len(x))

    for line in lines:
        line_lower = line.lower()

        for item in sorted_items:
            item_lower = item.lower()
            if item_lower in line_lower:
                qty_match = re.search(r'(\d+)', line)
                if qty_match:
                    qty = int(qty_match.group(1))
                    item_counts[item] += qty
                    break  # Avoid double-counting substrings
    return item_counts

def create_summary_page(date, item_summary):
    import math

    # Use ordered lists instead of sets
    category_mapping = {
        "Fancy Donuts": [
            "Apple Fritter", "Bear Claw", "Frosted Claw", "Berry Claw", "Raspberry Fritter",
            "Blueberry Fritter", "Cin Roll", "Frosted Roll", "Twist", "Buttermilk Bar (Glazed)", 
            "Buttermilk Bar (Plain)"
        ],
        "Raised Donuts": [
            "Maple Bar", "Chocolate Bar", "Tiger Bar", "Glazed Raised", "Chocolate Raised", "Cream Filled",
            "Raspberry Filled", "Lemon Filled", "Sugar Raised", "French Cruller (Glazed)",
            "French Cruller (Chocolate)", "French Cruller (Maple)"
        ],
        "Cake Donuts": [
            "Old Fashioned (Glazed)", "Old Fashioned (Chocolate)", "Old Fashioned (Maple)",
            "Old Fashioned (Plain)", "Devil's Food", "Devil's Food with Sprinkles", "Plain Cake", 
            "Plain Cake w/ Choc Icing", "Plain Cake with Choc Sprinkles", "Rainbow Sprinkle Cake (Vanilla)",
            "Coconut Cake (Vanilla)", "Chocolate Frosted Cake (NO SPRINKLES)", "Blueberry Cake", "Cinnamon Crumb", 
            "Glazed Cake Donut", "Assorted Cake", "Assorted Cake (NO PLAIN, NO SPRINKLES)"
        ]
    }

    # Assign items to categories + preserve order
    item_to_category = {}
    category_order = list(category_mapping.keys())

    for cat, items in category_mapping.items():
        for item in items:
            item_to_category[item] = cat

    categorized_items = {cat: [] for cat in category_order}
    categorized_items["Other"] = []

    for item in item_summary:
        category = item_to_category.get(item, "Other")
        categorized_items[category].append((item, item_summary[item]))

    # Sort each category's items in the original list order
    for cat, item_list in category_mapping.items():
        items_found = {name: qty for name, qty in categorized_items[cat]}
        sorted_items = [(name, items_found[name]) for name in item_list if name in items_found]
        categorized_items[cat] = sorted_items

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), f"Totals for {date.strftime('%m/%d/%Y')}", fontsize=14)

    y = 90
    y_step = 18
    row_spacing = 16
    col1_x = 60
    col2_x = 360
    page_margin_bottom = 750

    for category in category_order + ["Other"]:
        items = categorized_items.get(category, [])
        if not items:
            continue

        page.insert_text((col1_x, y), category, fontsize=13)
        y += y_step

        page.draw_line((col1_x, y), (col2_x + 140, y))
        y += y_step

        page.insert_text((col1_x, y), "Item", fontsize=11)
        page.insert_text((col2_x, y), "Qty", fontsize=11)
        y += y_step

        for item, qty in items:
            if item in donuts_per_screen:
                screens_raw = qty / donuts_per_screen[item]
                screens = math.ceil(screens_raw * 2) / 2
                screens_display = str(int(screens)) if screens.is_integer() else str(screens)
                unit = "screen" if screens_display == "1" else "screens"
                qty_display = f"{screens_display} {unit}"
            else:
                qty_num = int(qty) if isinstance(qty, (int, float)) and qty == int(qty) else qty
                unit = "donut" if qty_num == 1 else "donuts"
                qty_display = f"{qty_num} {unit}"

            page.insert_text((col1_x, y), item, fontsize=10)
            page.insert_text((col2_x, y), qty_display, fontsize=10)

            y += row_spacing

            if y > page_margin_bottom:
                page = doc.new_page()
                y = 50

        y += y_step

    temp_file = NamedTemporaryFile(delete=False, suffix=".pdf")
    doc.save(temp_file.name)
    doc.close()
    return temp_file.name

if uploaded_file is not None:
    try:
        vendor_df = pd.read_csv(GOOGLE_SHEET_CSV_URL, skiprows=1)
        vendor_df.columns = [c.strip().lower().replace(" ", "_") for c in vendor_df.columns]
        vendor_df = vendor_df[vendor_df["vendor_name"].notna()]
        vendor_df["packing_note"] = vendor_df["packing_note"].apply(normalize_packing_note)
        vendor_df["route"] = vendor_df["route"].str.lower()
        vendor_df["vendor_name"] = vendor_df["vendor_name"].str.lower()
        vendor_df = vendor_df.reset_index(drop=True)
        vendor_rank = {row["vendor_name"]: i for i, row in vendor_df.iterrows()}

        st.success("PDF uploaded! Click the button below to start sorting.")
        if st.button("🔃 Sort My Invoices"):
            with st.spinner("Sorting invoices and generating summaries..."):
                pdf_bytes = uploaded_file.read()
                reader = PdfReader(io.BytesIO(pdf_bytes))

                invoice_data = []
                current_invoice = {
                    'date': None,
                    'note': None,
                    'route': '',
                    'vendor': '',
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
                                current_invoice['route'],
                                vendor_rank.get(current_invoice['vendor'], 9999),
                                current_invoice['pages'],
                                current_invoice['items']
                            ))
                        current_invoice = {
                            'date': extract_date(all_text),
                            'note': 'unknown',
                            'route': '',
                            'vendor': '',
                            'pages': [i],
                            'items': extract_items(text)
                        }

                        for l in lines:
                            l_lower = l.lower()
                            if 'box' in l_lower:
                                current_invoice['note'] = 'box'
                            elif 'tray' in l_lower:
                                current_invoice['note'] = 'tray'
                            elif 'morning' in l_lower:
                                current_invoice['note'] = 'morning'

                            if 'route 1' in l_lower:
                                current_invoice['route'] = 'route 1'
                            elif 'route 2' in l_lower:
                                current_invoice['route'] = 'route 2'

                            try:
                                matched_vendor = None

                                # Exact match by line containing the full vendor name (safer)
                                for vendor in vendor_rank:
                                    vendor_clean = vendor.strip().lower()
                                    if vendor_clean and vendor_clean in l_lower:
                                        matched_vendor = vendor
                                        break

                                # Fallback to fuzzy match only if exact match fails
                                if not matched_vendor:
                                    match_result = process.extractOne(l_lower, vendor_rank.keys(), scorer=fuzz.token_sort_ratio)
                                    if match_result:
                                        match, score, _ = match_result
                                        if score >= 95:
                                            matched_vendor = match

                                if matched_vendor:
                                    current_invoice['vendor'] = matched_vendor
                            except Exception as e:
                                print(f"Vendor matching error on line: {l} -> {e}")

                    else:
                        current_invoice['pages'].append(i)
                        page_items = extract_items(text)
                        for k, v in page_items.items():
                            current_invoice['items'][k] += v

                if current_invoice['pages']:
                    invoice_data.append((
                        current_invoice['date'],
                        current_invoice['note'],
                        current_invoice['route'],
                        vendor_rank.get(current_invoice['vendor'], 9999),
                        current_invoice['pages'],
                        current_invoice['items']
                    ))

                sorted_invoices = sorted(invoice_data, key=lambda x: (
                    x[0],
                    packing_note_order.get(x[1], 99),
                    route_order.get(x[2], 99),
                    x[3]
                ))

                writer = PdfWriter()
                reader_pages = reader.pages
                current_day = None
                daily_items = defaultdict(int)

                for idx, (date, _, _, _, page_indices, items) in enumerate(sorted_invoices):
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
                    "🔄️ Download PDF with Daily Donut Totals",
                    open(temp_output_path, "rb"),
                    file_name="sorted " + uploaded_file.name,
                    mime="application/pdf"
                )

    except Exception as e:
        st.error(f"❌ Error processing file: {e}")
