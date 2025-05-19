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

## System Requirements

### 1. Python 3.8 or higher
Verify your Python installation:
```bash
python --version
```

### 2. Tesseract OCR
Required for processing scanned PDFs. Installation instructions by operating system:

#### macOS
```bash
# Using Homebrew
brew install tesseract

# Verify installation
tesseract --version
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
tesseract --version
```

#### Windows
1. Download the installer from [UB-Mannheim's GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
2. Run the installer
3. Add Tesseract to your PATH:
   - Right-click Computer/This PC → Properties → Advanced system settings
   - Click Environment Variables
   - Under System Variables, find PATH
   - Add the Tesseract installation directory (typically C:\\Program Files\\Tesseract-OCR)
4. Restart your computer
5. Verify installation in Command Prompt:
   ```cmd
   tesseract --version
   ```

### 3. Poppler (for PDF to Image Conversion)

#### macOS
```bash
brew install poppler
```

#### Ubuntu/Debian
```bash
sudo apt-get install poppler-utils
```

#### Windows
1. Download [poppler for Windows](http://blog.alivate.com.au/poppler-windows/)
2. Extract to a directory (e.g., C:\\Program Files\\poppler)
3. Add the bin directory to your PATH

## Installation

1. Clone the repository:
```bash
git clone https://github.com/sarangarca/hospital_pdf_checker.git
cd hospital_pdf_checker
```

2. Create and activate a virtual environment (recommended):
```bash
# macOS/Linux
python -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:
```bash
streamlit run ocr.py
```

2. Open your web browser to the URL shown in the terminal (typically http://localhost:8501)

## Troubleshooting

### Tesseract Not Found
If you see a "Tesseract not found" error:
1. Verify Tesseract is installed: `tesseract --version`
2. Check if the Tesseract executable is in your PATH
3. On Windows, you may need to set the TESSDATA_PREFIX environment variable:
   ```python
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```

### PDF to Image Conversion Fails
1. Verify Poppler is installed and in your PATH
2. On Windows, ensure the poppler bin directory is in your PATH
3. Try reinstalling the pdf2image package:
   ```bash
   pip uninstall pdf2image
   pip install pdf2image
   ```

## License

MIT License
