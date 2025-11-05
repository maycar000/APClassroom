from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image, ImageEnhance, ImageFilter
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
        """Initialize with high-quality settings for AP Classroom"""
        
        # Set up Tesseract
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        elif os.name == 'nt':
            default_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            if os.path.exists(default_path):
                pytesseract.pytesseract.tesseract_cmd = default_path
        
        # Chrome options for best screenshot quality
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
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
        time.sleep(1.5)
    
    def enhance_image_for_ocr(self, image_path):
        """Enhance image for better OCR - aggressive preprocessing"""
        img = Image.open(image_path)
        
        # Convert to RGB first, then grayscale for better processing
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize if too small (scale up for better OCR)
        width, height = img.size
        if width < 2000:
            scale = 2000 / width
            img = img.resize((int(width * scale), int(height * scale)), Image.LANCZOS)
        
        # Convert to grayscale
        img = img.convert('L')
        
        # Aggressive contrast enhancement
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(3.0)
        
        # Brightness adjustment
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.3)
        
        # Heavy sharpening
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(4.0)
        
        return img
    
    def perform_ocr(self, image_path):
        """Perform OCR with best settings"""
        try:
            img = self.enhance_image_for_ocr(image_path)
            
            # Use best Tesseract config
            config = '--oem 3 --psm 6 -c preserve_interword_spaces=1'
            text = pytesseract.image_to_string(img, config=config, lang='eng')
            
            return text
        except Exception as e:
            print(f"  ⚠ OCR error: {e}")
            return ""
    
    def clean_text(self, text):
        """Clean OCR output"""
        # Remove special symbols and circled letters
        text = re.sub(r'[©®@⊕⊗◉●○◎⓪-⑨Ⓐ-Ⓩⓐ-ⓩ]', '', text)
        
        # Fix common OCR errors
        text = text.replace('|', 'I')
        text = text.replace('!', 'I')
        text = text.replace('§', 'S')
        text = text.replace('ﬁ', 'fi')
        text = text.replace('ﬂ', 'fl')
        
        # Remove multiple spaces
        text = re.sub(r' +', ' ', text)
        
        # Clean up lines
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            # Keep lines with actual content (at least 10 chars or has 2+ words)
            words = re.findall(r'\b[A-Za-z]{2,}\b', line)
            if len(line) >= 10 or len(words) >= 2:
                lines.append(line)
        
        return '\n'.join(lines)
    
    def capture_question_area(self, iteration, output_folder):
        """Capture the actual question content area with scrolling"""
        
        # Scroll to top
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        
        screenshots = []
        
        # Take full page screenshot
        full_path = os.path.join(output_folder, f"q{iteration}_full.png")
        self.driver.save_screenshot(full_path)
        screenshots.append(full_path)
        
        # Get page dimensions
        total_height = self.driver.execute_script("return document.body.scrollHeight")
        viewport_height = self.driver.execute_script("return window.innerHeight")
        
        # If content is long, capture in sections
        if total_height > viewport_height * 1.3:
            scroll_positions = [
                viewport_height * 0.5,  # Middle
                total_height - viewport_height  # Bottom
            ]
            
            for i, pos in enumerate(scroll_positions):
                self.driver.execute_script(f"window.scrollTo(0, {pos});")
                time.sleep(0.5)
                
                path = os.path.join(output_folder, f"q{iteration}_part{i+2}.png")
                self.driver.save_screenshot(path)
                screenshots.append(path)
        
        # Scroll back to top
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        
        return screenshots
    
    def extract_text_from_screenshots(self, screenshot_paths):
        """Extract and combine text from multiple screenshots"""
        all_text = []
        
        for path in screenshot_paths:
            text = self.perform_ocr(path)
            if text.strip():
                all_text.append(text)
        
        # Combine all text
        combined = '\n\n'.join(all_text)
        
        # Clean it
        cleaned = self.clean_text(combined)
        
        return cleaned
    
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
            
            # Capture screenshots
            print(f"   📸 Capturing...")
            screenshots = self.capture_question_area(i + 1, output_folder)
            
            # Extract text
            print(f"   🔍 Extracting text...")
            text = self.extract_text_from_screenshots(screenshots)
            
            # Save result
            self.ocr_results.append({
                'question_num': i + 1,
                'screenshots': screenshots,
                'text': text
            })
            
            print(f"   ✓ Done ({len(text)} characters)")
            
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
        """Save all results to file"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("AP CLASSROOM - OCR RESULTS\n")
            f.write("=" * 80 + "\n\n")
            
            for result in self.ocr_results:
                f.write(f"\nQUESTION {result['question_num']}\n")
                f.write("-" * 80 + "\n\n")
                f.write(result['text'])
                f.write("\n\n" + "=" * 80 + "\n")
        
        print(f"\n💾 Saved to: {output_file}")
    
    def cleanup(self):
        """Close browser"""
        self.driver.quit()


def main():
    print("=" * 80)
    print("AP CLASSROOM - SCREENSHOT & OCR AUTOMATION")
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
        print("    3. Press ENTER to start")
        print("=" * 80)
        input()
        
        print(f"\n▶ Starting automation...")
        print(f"   Questions: {MAX_CLICKS}")
        print(f"   Wait time: {WAIT_TIME}s")
        
        # Run automation
        ocr.run_automation(MAX_CLICKS, WAIT_TIME, OUTPUT_FOLDER)
        
        # Save results
        ocr.save_results(OCR_RESULTS_FILE)
        
        # Summary
        print("\n" + "=" * 80)
        print("✅ COMPLETE!")
        print("=" * 80)
        print(f"📁 Screenshots: {OUTPUT_FOLDER}")
        print(f"📄 Results: {OCR_RESULTS_FILE}")
        print(f"✓ Processed: {len(ocr.ocr_results)} questions")
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
