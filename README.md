(MADE BY AI)

# Website Screenshot & OCR Automation

Automates clicking through website questions/pages, capturing screenshots, and extracting text using OCR.

## Features

- 🖱️ Automatic button clicking to cycle through content
- 📸 Full-screen screenshot capture
- 📝 OCR text extraction from screenshots
- ⚙️ Easy configuration via config file
- 🔄 Automatic ChromeDriver management

## Prerequisites

- Python 3.7 or higher
- Google Chrome browser
- Tesseract OCR

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/screenshot-ocr-automation.git
cd screenshot-ocr-automation
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Tesseract OCR

#### Windows
1. Download installer: https://github.com/UB-Mannheim/tesseract/wiki
2. Run installer (use default path: `C:\Program Files\Tesseract-OCR`)

#### Mac
```bash
brew install tesseract
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

## Configuration

### Option 1: Interactive Setup Wizard (Recommended)

Run the setup wizard for easy configuration:

```bash
python setup.py
```

The wizard will ask you:
- Website URL
- Button selector details
- Number of clicks
- Wait time between clicks
- Output settings
- Tesseract OCR path (if needed)

### Option 2: Manual Configuration

Edit `config.py` to customize for your website:

```python
# Your target website
WEBSITE_URL = "https://your-website.com"

# Button selector (see "Finding Selectors" below)
BUTTON_SELECTOR = "button.next"
SELECTOR_TYPE = "css"  # Options: 'css', 'id', 'class', 'xpath'

# Automation settings
MAX_CLICKS = 10        # Number of questions/pages
WAIT_TIME = 2          # Seconds between clicks
```

### Finding Button Selectors

1. Open your website in Chrome
2. Right-click the button → **Inspect**
3. Look at the HTML element

**Examples:**

```html
<!-- Example 1: ID -->
<button id="nextBtn">Next</button>
<!-- Use: BUTTON_SELECTOR = "nextBtn", SELECTOR_TYPE = "id" -->

<!-- Example 2: Class -->
<button class="next-question">Next</button>
<!-- Use: BUTTON_SELECTOR = "next-question", SELECTOR_TYPE = "class" -->

<!-- Example 3: CSS -->
<button class="btn primary next">Next</button>
<!-- Use: BUTTON_SELECTOR = "button.btn.next", SELECTOR_TYPE = "css" -->

<!-- Example 4: XPath -->
<!-- Use: BUTTON_SELECTOR = "//button[text()='Next']", SELECTOR_TYPE = "xpath" -->
```

## Usage

```bash
python screenshot_automation.py
```

## Output

- **screenshots/** - Folder containing all captured screenshots
- **ocr_results.txt** - Extracted text from all screenshots

## Troubleshooting

### "tesseract is not recognized"

**Windows:** Edit `config.py`:
```python
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

**Mac/Linux:** Make sure Tesseract is installed and in PATH

### "Button not found"

Double-check your button selector using Chrome DevTools (F12)

### "ChromeDriver version mismatch"

The script automatically downloads the correct ChromeDriver. If issues persist:
```bash
pip install --upgrade webdriver-manager
```

## Example Output

```
Navigating to: https://example.com
Looking for button: button.next
Will click 10 times with 2s wait time
Capturing screenshot 1...
Capturing screenshot 2...
...
=== Summary ===
Screenshots saved in: screenshots/
OCR results saved to: ocr_results.txt
Total captures: 10
Browser closed.
```

## License

MIT License - feel free to use and modify!

## Contributing

Pull requests welcome! Please open an issue first to discuss changes.

## Support

If you encounter issues:
1. Check the Troubleshooting section
2. Open an issue with error details
3. Include your Python version and OS
