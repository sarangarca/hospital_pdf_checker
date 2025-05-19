import streamlit as st
st.set_page_config(page_title="Hospital PDF Section Checker", page_icon="📄", layout="centered")
import sys
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from fuzzywuzzy import fuzz
import tempfile
import os
import re

SECTION_HEADERS = [
    "Discharge Summary",
    "Diagnosis",
    "Investigation",
    "Culture Report",
    "Final Diagnosis",
    "History of Present Illness",
    "HOPI"  # Alternative for History of Present Illness
]

REFERRAL_KEYWORDS = [
    "referral form", "referral", "referred by", "referring doctor", "referring hospital", "referral reason"
]

# Add a slider to control the fuzzy threshold
st.sidebar.header("Settings")
FUZZY_THRESHOLD = st.sidebar.slider("Fuzzy Match Threshold", min_value=60, max_value=100, value=75, step=1, help="Lower values allow more typos, higher values require closer matches.")

# UI: Select document type
st.sidebar.header("Document Type")
doc_type = st.sidebar.radio("Select the type of document to analyze:", ["Discharge Summary", "Referral Form"])

def extract_pdf_form_fields(pdf_path):
    """Extract form fields from a PDF using PyMuPDF."""
    try:
        doc = fitz.open(pdf_path)
        fields = {}
        
        for page in doc:
            # Convert generators to lists first
            widgets = list(page.widgets())
            annots = list(page.annots())
            
            # Debug print
            print(f"Found {len(widgets)} widgets and {len(annots)} annotations")
            
            # Method 1: Get form fields through widgets
            for field in widgets:
                field_name = field.field_name or ""
                field_value = field.field_value or ""
                field_type = field.field_type
                
                # Debug print
                print(f"Processing widget: name={field_name}, type={field_type}")
                
                # Clean up field names and values
                field_name = field_name.strip()
                if isinstance(field_value, str):
                    field_value = field_value.strip()
                elif field_value is None:
                    field_value = ""
                
                if field_name:
                    fields[field_name] = field_value
            
            # Method 2: Get form fields through annotations
            for annot in annots:
                try:
                    # Check for PDF form field types
                    if annot.type[0] in [3, 4, 12, 13, 17]:  # Form field annotation types
                        field_name = annot.field_name or ""
                        field_value = None
                        
                        # Try different ways to get field value
                        if hasattr(annot, 'field_value'):
                            field_value = annot.field_value
                        elif hasattr(annot, 'info') and 'content' in annot.info:
                            field_value = annot.info['content']
                        elif hasattr(annot, 'get_textbox'):
                            field_value = annot.get_textbox()
                        
                        # Debug print
                        print(f"Annotation field: name={field_name}, value={field_value}, type={annot.type}")
                        
                        # Clean up
                        field_name = field_name.strip()
                        if isinstance(field_value, str):
                            field_value = field_value.strip()
                        elif field_value is None:
                            field_value = ""
                        
                        if field_name:
                            fields[field_name] = field_value
                except Exception as e:
                    print(f"Error processing annotation: {e}")
            
            # Method 3: Extract text from form XObjects
            for xref in page.get_contents():
                stream = doc.xref_stream(xref)
                if stream and b"/Tx BMC" in stream:  # Text form field
                    try:
                        text = page.get_text("text", clip=page.rect)
                        if ":" in text:
                            parts = text.split(":", 1)
                            field_name = parts[0].strip()
                            field_value = parts[1].strip()
                            if field_name and field_value:
                                fields[field_name] = field_value
                    except:
                        continue

            # Method 4: Extract text near form field boxes
            for annot in page.annots():
                if annot.type[0] == 3:  # FreeText annotation
                    rect = annot.rect
                    # Look for text slightly above the annotation
                    label_rect = fitz.Rect(rect.x0, rect.y0 - 20, rect.x1, rect.y0)
                    label = page.get_text("text", clip=label_rect).strip()
                    value = annot.info.get("content", "").strip()
                    
                    if label and value:
                        fields[label] = value
                        
        return fields
    except Exception as e:
        print(f"Error extracting form fields: {e}")  # Debug info
        return {}
    finally:
        if 'doc' in locals():
            doc.close()

def extract_text_from_pdf(pdf_path):
    text_per_page = []
    form_fields = extract_pdf_form_fields(pdf_path)
    
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text().strip()
            
            # Try to get form fields first
            if isinstance(form_fields, dict):
                for field_name, field_value in form_fields.items():
                    if field_value and isinstance(field_value, str):
                        text = f"{field_name}: {field_value}\n" + text
            
            if not text or len(text) < 20:
                images = convert_from_path(pdf_path, first_page=page_num+1, last_page=page_num+1)
                ocr_text = ""
                for img in images:
                    ocr_text += pytesseract.image_to_string(img)
                text_per_page.append(ocr_text)
            else:
                text_per_page.append(text)
        return text_per_page
    except Exception as e:
        return f"Error extracting text: {e}"
    finally:
        if 'doc' in locals():
            doc.close()

def fuzzy_find_section(text, section):
    lines = text.split('\n')
    for line in lines:
        clean_line = line.strip().lower()
        clean_section = section.lower()
        if fuzz.partial_ratio(clean_line, clean_section) >= FUZZY_THRESHOLD:
            return line.strip()  # Return the actual heading found
    return None

def fuzzy_find_all_headings(text, section, all_sections):
    lines = text.split('\n')
    matches = []
    section_lower = section.lower()
    longer_sections = [s.lower() for s in all_sections if len(s) > len(section)]
    for line in lines:
        clean_line = line.strip().lower()
        # Only match if not also a fuzzy match for any longer section name
        if fuzz.partial_ratio(clean_line, section_lower) >= FUZZY_THRESHOLD:
            if not any(fuzz.partial_ratio(clean_line, ls) >= FUZZY_THRESHOLD for ls in longer_sections):
                matches.append(line.strip())
    return matches

def analyze_sections(text_per_page):
    summary = []
    for section in SECTION_HEADERS:
        found = False
        page_found = []
        headings = []
        for idx, text in enumerate(text_per_page):
            matches = fuzzy_find_all_headings(text, section, SECTION_HEADERS)
            if matches:
                found = True
                page_found.append(str(idx + 1))
                headings.extend(matches)
        # Remove duplicate headings
        unique_headings = list(dict.fromkeys(headings))
        summary.append({
            "Section": section,
            "Status": "Present" if found else "Missing",
            "Pages": ', '.join(page_found) if found else "-",
            "Headings Used": '; '.join(unique_headings) if unique_headings else "-"
        })
    return summary

def is_referral_form(text_per_page):
    for text in text_per_page:
        for keyword in REFERRAL_KEYWORDS:
            if keyword in text.lower():
                return keyword  # Return the keyword found for better feedback
    return None

def extract_referral_fields(text):
    # Define possible fields and their keyword variations
    fields = {
        "Patient Name": ["patient name", "name of patient", "name", "pt. name", "patient's name", "name of the patient"],
        "Age": ["age", "patient age"],
        "Gender": ["gender", "sex", "male", "female", "m/f"],
        "Referred By": ["referred by", "referring doctor", "referring hospital", "refd by", "refd. by", "refd by"],
        "Referral Reason": ["referral reason", "reason for referral", "reason", "reason for ref.", "reason for ref"],
        "Diagnosis": ["diagnosis", "provisional diagnosis", "diagno"],
        "Date": ["date", "dt."],
        "Contact": ["contact", "phone", "mobile", "tel", "contact no", "contact number"],
        "Digital Signature": ["digitally signed by", "digital signature", "signed by"]
    }
    
    lines = text.split('\n')
    result = {field: "" for field in fields}
    empty_fields = []
    
    # First pass - detect digital signature and timestamp
    for i, line in enumerate(lines):
        lcline = line.lower()
        if "digitally signed by" in lcline:
            # Get the next line which usually contains the name
            if i + 1 < len(lines):
                result["Digital Signature"] = lines[i + 1].strip()
            # Get the date and time if available
            for j in range(i + 1, min(i + 4, len(lines))):
                if "date:" in lines[j].lower():
                    date_line = lines[j]
                    # Extract full timestamp including timezone if available
                    timestamp_match = re.search(r"date:?\s*([0-9.-]+\s*(?:[0-9:]+)?\s*(?:IST|UTC|GMT)?)", date_line, re.IGNORECASE)
                    if timestamp_match:
                        result["Date"] = timestamp_match.group(1).strip()
                    break
    
    # Second pass - extract other fields
    for i, line in enumerate(lines):
        lcline = line.lower()
        for field, keywords in fields.items():
            if field in ["Digital Signature", "Date"] and result[field]:
                continue  # Skip if already found in first pass
                
            for kw in keywords:
                if fuzz.partial_ratio(kw, lcline.strip()) >= 80 and not result[field]:
                    # Try regex for value after label, after colon, or after whitespace
                    match = re.search(rf"{re.escape(kw)}[\s:]*([\w\-/,. ]+)", lcline)
                    value = ""
                    if match:
                        value = match.group(1).strip()
                    # If value is empty, try next line
                    if not value and i+1 < len(lines):
                        next_line = lines[i+1].strip()
                        # Avoid picking up another label as value
                        if not any(fuzz.partial_ratio(next_line.lower(), k) >= 80 for k in keywords):
                            value = next_line
                    # For Age, try to extract a number
                    if field == "Age" and not value:
                        age_match = re.search(r"\b(\d{1,3})\b", lcline)
                        if age_match:
                            value = age_match.group(1)
                    # For Gender, look for M/F or Male/Female
                    if field == "Gender" and not value:
                        g_match = re.search(r"\b(male|female|m|f)\b", lcline)
                        if g_match:
                            value = g_match.group(1)
                    result[field] = value
    
    # Identify empty fields
    for field, value in result.items():
        if not value or not value.strip():
            empty_fields.append(field)
            
    return result, empty_fields

st.title("📄 Hospital PDF Section Checker")
st.markdown("""
Upload a multi-page hospital PDF (Discharge Summaries, Lab Reports, etc.).
This tool will auto-identify whether key medical sections are present or missing.
""")

uploaded_file = st.file_uploader(f"Upload PDF ({doc_type})", type=["pdf"])

def ocr_referral_form(pdf_path):
    # Extract form fields first
    form_fields = extract_pdf_form_fields(pdf_path)
    # Then extract scanned form fields
    fields = extract_scanned_form_fields(pdf_path)
    
    # Get text content for signature detection
    text_per_page = extract_text_from_pdf(pdf_path)
    if isinstance(text_per_page, str) and text_per_page.startswith("Error"):
        return text_per_page, "", "", ""
    
    full_text = '\n'.join(text_per_page)
    
    # Extract signature and date
    sig_fields = {}
    lines = full_text.split('\n')
    for i, line in enumerate(lines):
        if "digitally signed by" in line.lower():
            if i + 1 < len(lines):
                sig_fields["Digital Signature"] = lines[i + 1].strip()
        elif "date:" in line.lower():
            timestamp_match = re.search(r"date:?\s*([0-9.-]+\s*(?:[0-9:]+)?\s*(?:IST|UTC|GMT)?)", line, re.IGNORECASE)
            if timestamp_match:
                sig_fields["Date"] = timestamp_match.group(1).strip()
    
    # Merge signature fields with form fields
    fields.update(sig_fields)
    
    # Determine empty fields - only the ones we can detect reliably
    empty_fields = []
    for field in [
        "Patient Name", "Patient ID", "Contact",
        "Hospital Name", "Referred To", "Diagnosis",
        "Digital Signature", "Date"
    ]:
        if not fields.get(field):
            empty_fields.append(field)
    
    # Merge form fields into extracted fields if they exist
    if isinstance(form_fields, dict):
        for field_name, field_value in form_fields.items():
            field_name = field_name.strip().lower()
            # Map form field names to our field names - only the reliable ones
            field_mapping = {
                'name': 'Patient Name',
                'patient': 'Patient Name',
                'pt': 'Patient Name',
                'patient_id': 'Patient ID',
                'id': 'Patient ID',
                'registration': 'Patient ID',
                'reg_no': 'Patient ID',
                'hospital': 'Hospital Name',
                'facility': 'Hospital Name',
                'referred_to': 'Referred To',
                'referredto': 'Referred To',
                'ref_to': 'Referred To',
                'diagnosis': 'Diagnosis',
                'clinical_notes': 'Diagnosis',
                'contact': 'Contact',
                'phone': 'Contact',
                'mobile': 'Contact',
                'tel': 'Contact',
                'email': 'Contact'  # Email can also be contact
            }
            
            # Find matching field name
            for form_key, our_key in field_mapping.items():
                if form_key in field_name and not fields[our_key]:  # Only use if our field is empty
                    fields[our_key] = field_value
                    if our_key in empty_fields:
                        empty_fields.remove(our_key)
    
    # Also return the raw OCR output for the first page for debugging
    first_page_ocr = text_per_page[0] if text_per_page else ""
    return fields, empty_fields, full_text, first_page_ocr

def extract_scanned_form_fields(pdf_path):
    """Extract fields from a scanned form by looking at specific regions"""
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]  # Assume first page
        fields = {}
        
        # Common field labels we expect to find - only the reliable ones
        field_patterns = {
            "Patient Name": [r"(?i)patient.*?name\s*[:\s]\s*(.+?)(?:\||$)", r"(?i)name\s*[:\s]\s*(.+?)(?:\||$)"],
            "Patient ID": [r"(?i)patient\s*(?:id|number)\s*[:\s]\s*(.+?)(?:\||$)", r"(?i)(?:id|reg)\s*(?:no\.?|number)?\s*[:\s]\s*([A-Za-z0-9-]+)(?:\||$)"],
            "Hospital Name": [r"(?i)hospital\s*(?:name)?\s*[:\s]\s*(.+?)(?:\||$)", r"(?i)facility\s*[:\s]\s*(.+?)(?:\||$)", r"(?i)located\s+within\s+the\s+AOR\s+of\s+(.+?)(?:\||$)"],
            "Referred To": [r"(?i)referred\s+to\s*[:\s]\s*(.+?)(?:\||$)", r"(?i)ref\.\s*to\s*[:\s]\s*(.+?)(?:\||$)"],
            "Diagnosis": [r"(?i)diagnosis\s*[:\s]\s*(.+?)(?:\||$)", r"(?i)clinical\s+notes\s*[:\s]\s*(.+?)(?:\||$)"],
            "Contact": [r"(?i)contact\s*[:\s]\s*(.+?)(?:\||$)", r"(?i)phone\s*[:\s]\s*(\d+)", r"(?i)email\s*[:\s]\s*(\S+@\S+\.\S+)", r"\b\d{10}\b", r"(?i)(?:patient\s+)?email\s*[:\s]\s*(\S+@\S+\.\S+)"]
        }
        
        # Convert page to image for better text extraction
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Extract text with better OCR settings
        ocr_text = pytesseract.image_to_string(img, config='--psm 3')
        lines = ocr_text.split('\n')
        
        # Process each line
        for i, line in enumerate(lines):
            # Skip empty lines
            if not line.strip():
                continue
            
            # Check each field pattern
            for field_name, patterns in field_patterns.items():
                if any(re.search(pattern, line) for pattern in patterns):
                    # Found a field label, look for value in same line or next line
                    value = ""
                    
                    # Try to find value using regex capture groups
                    for pattern in patterns:
                        matches = re.finditer(pattern, line, re.IGNORECASE)
                        for match in matches:
                            if match.groups():
                                value = match.group(1).strip()
                                # Special handling for each field type
                                if field_name == "Contact":
                                    # Try to find phone number
                                    if phone_match := re.search(r'\b\d{10}\b', line):
                                        value = phone_match.group(0)
                                    # Try to find email
                                    if email_match := re.search(r'\S+@\S+\.\S+', line):
                                        email = email_match.group(0)
                                        value = f"{value} | Email ID: {email}" if value else email
                                elif field_name == "Patient Name":
                                    # Clean up patient name
                                    value = re.sub(r'\s*\|\s*Force Type.*', '', value).strip()
                                elif field_name == "Age":
                                    # Extract just the numeric age
                                    if age_match := re.search(r'\b(\d+)\b', value):
                                        value = age_match.group(1)
                                elif field_name == "Gender":
                                    # Normalize gender values
                                    value = value.lower()
                                    value = "Male" if re.search(r'\b(male|m)\b', value) else "Female" if re.search(r'\b(female|f)\b', value) else value
                                elif field_name == "Diagnosis":
                                    # Clean up diagnosis text
                                    value = re.sub(r'(?i)clinical\s+notes\s*[:\s]\s*', '', value).strip()
                                break
                        if value:
                            break
                    
                    # If no value found, look at next line
                    if not value and i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        # Only use next line if it doesn't look like a label
                        if not any(re.search(p, next_line) for patterns in field_patterns.values() for p in patterns):
                            value = next_line
                    
                    # Special handling for Gender field
                    if field_name == "Gender" and value:
                        if re.search(r"(?i)\b(male|m)\b", value):
                            value = "Male"
                        elif re.search(r"(?i)\b(female|f)\b", value):
                            value = "Female"
                    
                    fields[field_name] = value
        
        return fields
        
    except Exception as e:
        print(f"Error extracting scanned form fields: {e}")
        return {}
    finally:
        if 'doc' in locals():
            doc.close()

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name
    with st.spinner("Analyzing PDF..."):
        if doc_type == "Discharge Summary":
            text_per_page = extract_text_from_pdf(tmp_path)
            if isinstance(text_per_page, str) and text_per_page.startswith("Error"):
                st.error(text_per_page)
            else:
                summary = analyze_sections(text_per_page)
                st.success("Analysis complete!")
                st.markdown("### Section Summary")
                st.dataframe(summary, hide_index=True)
        elif doc_type == "Referral Form":
            fields, empty_fields, full_text, first_page_ocr = ocr_referral_form(tmp_path)
            if isinstance(fields, str) and fields.startswith("Error"):
                st.error(fields)
            else:
                if fields.get("Digital Signature"):
                    st.success(f"✓ Digitally signed by: {fields['Digital Signature']}")
                    if fields.get("Date"):
                        st.success(f"✓ Signed on: {fields['Date']}")
                
                st.markdown("### Form Fields Detection Results")
                # Show detected fields with their sources
                for k, v in fields.items():
                    if k not in ["Digital Signature", "Date"]:
                        if k in empty_fields:
                            st.error(f"❌ {k}: Not detected")
                        else:
                            st.success(f"{k}: {v}")
    os.remove(tmp_path)
else:
    st.info("Please upload a PDF to begin analysis.")