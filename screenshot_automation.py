from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image, ImageEnhance
import pytesseract
import time
import os
import re

# Import config
try:
    import config
    WEBSITE_URL = config.WEBSITE_URL
    BUTTON_SELECTOR = config.BUTTON_SELECTOR
    SELECTOR_TYPE = config.SELECTOR_TYPE
    MAX_CLICKS = config.MAX_CLICKS
    WAIT_TIME = config.WAIT_TIME
    TESSERACT_PATH = config.TESSERACT_PATH
    OUTPUT_FOLDER = config.OUTPUT_FOLDER
    OCR_RESULTS_FILE = config.OCR_RESULTS_FILE
except ImportError:
    print("❌ config.py not found! Run setup.py first.")
    exit(1)

class APClassroomOCR:
    def __init__(self, tesseract_path=None):
        """Initialize with settings optimized for text extraction"""
        
        # Set up Tesseract
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        elif os.name == 'nt':
            default_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            if os.path.exists(default_path):
                pytesseract.pytesseract.tesseract_cmd = default_path
        
        # Chrome options
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        options.add_argument('--force-device-scale-factor=1.5')  # Higher DPI
        
        # Initialize driver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_window_size(1920, 1080)
        
        self.ocr_results = []
    
    def navigate_to_url(self, url):
        """Navigate to website"""
        self.driver.get(url)
        time.sleep(3)
    
    def wait_for_load(self):
        """Wait for page to fully load"""
        WebDriverWait(self.driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(1)
    
    def enhance_image(self, image_path):
        """Enhance image for OCR"""
        img = Image.open(image_path)
        
        # Convert to RGB then grayscale
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img = img.convert('L')
        
        # Scale up
        width, height = img.size
        scale = 2.5
        img = img.resize((int(width * scale), int(height * scale)), Image.LANCZOS)
        
        # Enhance
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.5)
        
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(2.0)
        
        return img
    
    def perform_ocr(self, image_path):
        """Perform OCR"""
        try:
            img = self.enhance_image(image_path)
            config = '--oem 3 --psm 6'
            text = pytesseract.image_to_string(img, config=config, lang='eng')
            return text
        except Exception as e:
            print(f"  ⚠ OCR error: {e}")
            return ""
    
    def clean_text(self, text):
        """Clean OCR output aggressively"""
        # Remove circled letters
        symbols_to_remove = ['©', '®', '⊕', '⊗', '◉', '●', '○', '◎']
        for symbol in symbols_to_remove:
            text = text.replace(symbol, '')
        
        # Fix common errors
        text = text.replace('|', 'I')
        text = text.replace('§', 'S')
        
        # Remove multiple spaces
        text = re.sub(r' +', ' ', text)
        
        # Keep only meaningful lines
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            # Filter out garbage
            words = re.findall(r'\b[A-Za-z]{3,}\b', line)
            if len(words) >= 3:  # At least 3 real words
                lines.append(line)
        
        return '\n'.join(lines)
    
    def extract_question_and_answers(self):
        """
        Extract ONLY the question text and answer choices using JavaScript
        This avoids capturing images, headers, footers
        """
        try:
            # Wait a bit for content to load
            time.sleep(2)
            
            # JavaScript to extract text content
            script = """
            function extractQuestionData() {
                let result = {question: '', answers: []};
                
                // Find the question text (usually in a div or p tag near the top)
                // Look for elements that contain the actual question
                const possibleQuestions = document.querySelectorAll('div, p, span');
                for (let elem of possibleQuestions) {
                    const text = elem.innerText || elem.textContent;
                    // Question usually has a question mark or is substantial text
                    if (text.includes('?') && text.length > 20 && text.length < 500) {
                        // Make sure it's visible
                        const rect = elem.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            result.question = text.trim();
                            break;
                        }
                    }
                }
                
                // Find answer choices (look for A, B, C, D buttons or divs)
                const answerButtons = document.querySelectorAll('[role="radio"], button[class*="answer"], div[class*="choice"]');
                for (let btn of answerButtons) {
                    const text = btn.innerText || btn.textContent;
                    if (text.trim().length > 5) {  // Must have content
                        result.answers.push(text.trim());
                    }
                }
                
                // Fallback: look for any text starting with A, B, C, D
                if (result.answers.length === 0) {
                    const allText = document.body.innerText;
                    const lines = allText.split('\\n');
                    for (let line of lines) {
                        line = line.trim();
                        // Match lines that start with A, B, C, D, E followed by text
                        if (/^[A-E]\\s+/.test(line) && line.length > 10) {
                            result.answers.push(line);
                        }
                    }
                }
                
                return result;
            }
            
            return extractQuestionData();
            """
            
            data = self.driver.execute_script(script)
            
            # Format the output
            formatted = ""
            if data['question']:
                formatted += f"QUESTION:\n{data['question']}\n\n"
            
            if data['answers']:
                formatted += "ANSWERS:\n"
                for ans in data['answers']:
                    formatted += f"{ans}\n"
            
            return formatted if formatted else None
            
        except Exception as e:
            print(f"  ⚠ JavaScript extraction failed: {e}")
            return None
    
    def capture_right_panel(self, iteration, output_folder):
        """Capture only the right panel where questions/answers appear"""
        try:
            # Scroll the right panel to see all answers
            scroll_script = """
            const rightPanel = document.querySelector('[class*="question"]') || 
                              document.querySelector('main') || 
                              document.querySelector('[role="main"]');
            if (rightPanel) {
                rightPanel.scrollTop = 0;
                return true;
            }
            return false;
            """
            self.driver.execute_script(scroll_script)
            time.sleep(0.5)
            
            # Take screenshot
            screenshot_path = os.path.join(output_folder, f"q{iteration}.png")
            self.driver.save_screenshot(screenshot_path)
            
            return screenshot_path
            
        except Exception as e:
            print(f"  ⚠ Screenshot error: {e}")
            return None
    
    def run_automation(self, max_clicks, wait_time, output_folder):
        """Main automation loop"""
        
        # Create output folder
        os.makedirs(output_folder, exist_ok=True)
        
        selector_map = {
            'css': By.CSS_SELECTOR,
            'xpath': By.XPATH,
            'id': By.ID,
            'class': By.CLASS_NAME,
        }
        by_method = selector_map.get(SELECTOR_TYPE, By.CSS_SELECTOR)
        
        for i in range(max_clicks):
            print(f"\n📝 Question {i + 1}/{max_clicks}")
            
            # Wait for page to load
            self.wait_for_load()
            time.sleep(wait_time)
            
            # Method 1: Try JavaScript extraction (fastest and cleanest)
            print(f"   🔍 Extracting text...")
            extracted_text = self.extract_question_and_answers()
            
            if extracted_text:
                # Successfully extracted with JavaScript
                self.ocr_results.append({
                    'question_num': i + 1,
                    'text': extracted_text,
                    'method': 'JavaScript'
                })
                print(f"   ✓ Extracted via JavaScript")
            else:
                # Fallback: OCR from screenshot
                print(f"   📸 Capturing screenshot...")
                screenshot_path = self.capture_right_panel(i + 1, output_folder)
                
                if screenshot_path:
                    print(f"   🔍 Running OCR...")
                    text = self.perform_ocr(screenshot_path)
                    cleaned = self.clean_text(text)
                    
                    self.ocr_results.append({
                        'question_num': i + 1,
                        'text': cleaned,
                        'method': 'OCR'
                    })
                    print(f"   ✓ Extracted via OCR")
                else:
                    print(f"   ⚠ Failed to capture")
            
            # Click next (except on last question)
            if i < max_clicks - 1:
                try:
                    next_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((by_method, BUTTON_SELECTOR))
                    )
                    next_btn.click()
                    time.sleep(1)
                except Exception as e:
                    print(f"   ⚠ Cannot click Next: {e}")
                    break
    
    def save_results(self, output_file):
        """Save results in clean format"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("AP CLASSROOM - QUESTIONS & ANSWERS\n")
            f.write("=" * 80 + "\n\n")
            
            for result in self.ocr_results:
                f.write(f"\n{'='*80}\n")
                f.write(f"QUESTION {result['question_num']}\n")
                f.write(f"{'='*80}\n\n")
                f.write(result['text'])
                f.write("\n")
        
        print(f"\n💾 Saved to: {output_file}")
    
    def cleanup(self):
        """Close browser"""
        self.driver.quit()


def main():
    print("=" * 80)
    print("AP CLASSROOM - QUESTIONS & ANSWERS EXTRACTOR")
    print("=" * 80)
    
    ocr = APClassroomOCR(tesseract_path=TESSERACT_PATH)
    
    try:
        print(f"\n🌐 Opening: {WEBSITE_URL}")
        ocr.navigate_to_url(WEBSITE_URL)
        
        # Pause for login
        print("\n" + "=" * 80)
        print("⚠️  PLEASE:")
        print("    1. Log in to AP Classroom")
        print("    2. Navigate to the FIRST question")
        print("    3. Make sure you can see the question and all answer choices")
        print("    4. Press ENTER to start")
        print("=" * 80)
        input()
        
        print(f"\n▶ Starting extraction...")
        print(f"   Questions: {MAX_CLICKS}")
        print(f"   Wait time: {WAIT_TIME}s")
        print(f"\n   Trying JavaScript extraction first (cleanest)")
        print(f"   Will fall back to OCR if needed\n")
        
        # Run automation
        ocr.run_automation(MAX_CLICKS, WAIT_TIME, OUTPUT_FOLDER)
        
        # Save results
        ocr.save_results(OCR_RESULTS_FILE)
        
        # Summary
        print("\n" + "=" * 80)
        print("✅ COMPLETE!")
        print("=" * 80)
        print(f"📄 Results: {OCR_RESULTS_FILE}")
        print(f"✓ Processed: {len(ocr.ocr_results)} questions")
        
        js_count = sum(1 for r in ocr.ocr_results if r.get('method') == 'JavaScript')
        ocr_count = sum(1 for r in ocr.ocr_results if r.get('method') == 'OCR')
        print(f"   - JavaScript: {js_count} questions")
        print(f"   - OCR: {ocr_count} questions")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        ocr.cleanup()
        print("\n👋 Browser closed")

if __name__ == "__main__":
    main()
