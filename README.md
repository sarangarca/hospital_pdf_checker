# Hospital PDF Section Checker

A Python application that analyzes hospital PDF documents (discharge summaries and referral forms) using OCR and form field extraction.

## Features

- Analyzes Discharge Summaries
  - Detects presence of key medical sections
  - Supports both digital and scanned PDFs
  - Fuzzy matching for section headers

- Processes Referral Forms
  - Extracts patient information
  - Detects digital signatures
  - Extracts form fields and contact information

## Requirements

- Python 3.x
- Tesseract OCR
- Required Python packages:
  - streamlit
  - PyMuPDF
  - pytesseract
  - pdf2image
  - python-Levenshtein
  - fuzzywuzzy
  - pillow

## Installation

1. Install Tesseract OCR:
```bash
brew install tesseract
```

2. Install Python dependencies:
```bash
pip install streamlit PyMuPDF pytesseract pdf2image python-Levenshtein fuzzywuzzy pillow
```

## Usage

Run the application using Streamlit:
```bash
streamlit run ocr.py
```

## License

MIT License
