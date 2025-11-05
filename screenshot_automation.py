from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import time
import os
import re

# Try to import config, use defaults if not found
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
    # Default values if config.py doesn't exist
    WEBSITE_URL = "https://example.com"
    BUTTON_SELECTOR = "button.next"
    SELECTOR_TYPE = "css"
    MAX_CLICKS = 10
    WAIT_TIME = 2
    TESSERACT_PATH = None
    OUTPUT_FOLDER = "screenshots"
    OCR_RESULTS_FILE = "ocr_results.txt"

class WebsiteScreenshotOCR:
    def __init__(self, driver_path=None, tesseract_path=None):
        """
        Initialize the automation tool with high-quality screenshot settings
        """
        # Set up Tesseract path
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        elif os.name == 'nt':  # Windows
            default_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            if os.path.exists(default_path):
                pytesseract.pytesseract.tesseract_cmd = default_path
        
        # Set up Chrome driver with high-DPI settings for better screenshots
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        options.add_argument('--force-device-scale-factor=2.0')  # 2x resolution for sharper text
        options.add_argument('--high-dpi-support=2.0')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        # Disable GPU acceleration issues
        options.add_argument('--disable-gpu')
        
        if driver_path:
            service = Service(executable_path=driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
        else:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        
        # Set a good window size for consistent screenshots
        self.driver.set_window_size(1920, 1080)
        
        self.screenshots = []
        self.ocr_results = []
    
    def navigate_to_url(self, url):
        """Navigate to the target website"""
        self.driver.get(url)
        time.sleep(3)  # Wait for page to load
    
    def wait_for_page_load(self):
        """Wait for page to be fully loaded"""
        WebDriverWait(self.driver, 10).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )
        time.sleep(1)  # Extra buffer for dynamic content
    
    def preprocess_image_advanced(self, image_path):
        """
        Advanced image preprocessing for better OCR
        """
        # Open image
        image = Image.open(image_path)
        
        # If image is too small, upscale it
        width, height = image.size
        if width < 1920:
            scale_factor = 1920 / width
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            image = image.resize((new_width, new_height), Image.LANCZOS)
        
        # Convert to grayscale
        image = image.convert('L')
        
        # Increase contrast significantly
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.5)
        
        # Increase brightness slightly
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.2)
        
        # Sharpen the image
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(3.0)
        
        return image
    
    def clean_ocr_text(self, text):
        """
        Aggressive text cleaning for AP Classroom content
        """
        # Remove all special characters and symbols at start of lines
        text = re.sub(r'^[^\w\s]+\s*', '', text, flags=re.MULTILINE)
        
        # Remove circled letters and special symbols
        text = re.sub(r'[©®@⊕⊗⊙◉●○◎⦿⓪①②③④⑤⑥⑦⑧⑨⑩ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏ]', '', text)
        
        # Remove standalone numbers/letters in circles or boxes
        text = re.sub(r'\b[A-Z]\b(?=\s+[A-Z])', '', text)  # Remove isolated capital letters
        
        # Fix common OCR mistakes
        text = text.replace('|', 'I')
        text = text.replace('!', 'I')
        text = text.replace('§', 'S')
        text = text.replace('£', 'E')
        text = text.replace('ﬁ', 'fi')
        text = text.replace('ﬂ', 'fl')
        text = text.replace('¢', 'c')
        text = text.replace('$', 'S')
        
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Remove spaces before punctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        
        # Remove trailing special characters
        text = re.sub(r'[^\w\s.!?,;:\'\"-]+$', '', text, flags=re.MULTILINE)
        
        # Remove lines that are mostly garbage (less than 3 real words)
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            words = re.findall(r'\b[a-zA-Z]{2,}\b', line)  # Find real words (2+ letters)
            if len(words) >= 3 or len(line.strip()) > 20:  # Keep if has 3+ words or 20+ chars
                cleaned_lines.append(line.strip())
        
        text = '\n'.join(cleaned_lines)
        
        return text.strip()
    
    def capture_element_screenshot(self, element_selector, output_path):
        """
        Capture screenshot of a specific element for better OCR
        """
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, element_selector)
            element.screenshot(output_path)
            return True
        except:
            return False
    
    def capture_full_page(self, output_folder, iteration):
        """
        Capture full-page screenshot with scrolling
        """
        screenshot_paths = []
        
        # Scroll to top first
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
        # Try to capture the main content area (better than full screen)
        main_content_path = os.path.join(output_folder, f"screenshot_{iteration}_content.png")
        
        # Try to find and capture just the question content area
        content_selectors = [
            'main',  # Main content area
            '[role="main"]',
            '.question-content',
            'article',
            '#question-container'
        ]
        
        content_captured = False
        for selector in content_selectors:
            if self.capture_element_screenshot(selector, main_content_path):
                screenshot_paths.append(main_content_path)
                content_captured = True
                break
        
        # Fallback to full screenshot if element capture failed
        if not content_captured:
            default_path = os.path.join(output_folder, f"screenshot_{iteration}_full.png")
            self.driver.save_screenshot(default_path)
            screenshot_paths.append(default_path)
        
        # Check if page needs scrolling
        page_height = self.driver.execute_script("return document.body.scrollHeight")
        viewport_height = self.driver.execute_script("return window.innerHeight")
        
        if page_height > viewport_height * 1.2:  # If content extends beyond viewport
            # Scroll to middle
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(0.5)
            
            middle_path = os.path.join(output_folder, f"screenshot_{iteration}_middle.png")
            self.driver.save_screenshot(middle_path)
            screenshot_paths.append(middle_path)
            
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)
            
            bottom_path = os.path.join(output_folder, f"screenshot_{iteration}_bottom.png")
            self.driver.save_screenshot(bottom_path)
            screenshot_paths.append(bottom_path)
            
            # Scroll back to top
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
        
        return screenshot_paths
    
    def click_button_and_capture(self, button_selector, selector_type='css', 
                                  max_clicks=10, wait_time=2, output_folder='screenshots'):
        """
        Click button and capture high-quality screenshots with OCR
        """
        # Create output folder
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        # Map selector types
        selector_map = {
            'css': By.CSS_SELECTOR,
            'xpath': By.XPATH,
            'id': By.ID,
            'class': By.CLASS_NAME,
            'name': By.NAME
        }
        
        by_method = selector_map.get(selector_type, By.CSS_SELECTOR)
        
        try:
            for i in range(max_clicks):
                print(f"\nProcessing question {i + 1}/{max_clicks}...")
                
                # Wait for page to fully load
                self.wait_for_page_load()
                time.sleep(wait_time)
                
                # Capture screenshots
                print(f"  📸 Capturing screenshots...")
                screenshot_paths = self.capture_full_page(output_folder, i + 1)
                
                # Perform OCR on all screenshots
                print(f"  🔍 Running OCR...")
                combined_text = ""
                for screenshot_path in screenshot_paths:
                    ocr_text = self.perform_ocr_advanced(screenshot_path)
                    combined_text += ocr_text + "\n\n"
                
                # Clean the text
                cleaned_text = self.clean_ocr_text(combined_text)
                
                # Save results
                self.ocr_results.append({
                    'screenshots': screenshot_paths,
                    'text': cleaned_text,
                    'iteration': i + 1
                })
                
                print(f"  ✓ Question {i + 1} processed")
                
                # Click next button
                try:
                    button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((by_method, button_selector))
                    )
                    button.click()
                    time.sleep(1)
                except Exception as e:
                    print(f"  ⚠ Could not click next button: {e}")
                    if i < max_clicks - 1:  # Not the last question
                        print("  Stopping automation...")
                        break
                
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    def perform_ocr_advanced(self, image_path):
        """
        Perform advanced OCR with multiple passes
        """
        try:
            # Preprocess image
            image = self.preprocess_image_advanced(image_path)
            
            # Try multiple OCR configurations
            configs = [
                r'--oem 3 --psm 6',  # Uniform block of text
                r'--oem 3 --psm 3',  # Fully automatic page segmentation
                r'--oem 3 --psm 4',  # Single column of text
            ]
            
            best_text = ""
            max_words = 0
            
            for config in configs:
                try:
                    text = pytesseract.image_to_string(image, config=config)
                    word_count = len(text.split())
                    if word_count > max_words:
                        max_words = word_count
                        best_text = text
                except:
                    continue
            
            return best_text.strip()
        except Exception as e:
            print(f"  ⚠ OCR error for {image_path}: {e}")
            return ""
    
    def save_results(self, output_file='ocr_results.txt'):
        """Save OCR results with better formatting"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("AP CLASSROOM OCR RESULTS\n")
            f.write("=" * 80 + "\n\n")
            
            for result in self.ocr_results:
                f.write(f"QUESTION {result['iteration']}\n")
                f.write("-" * 80 + "\n")
                
                for screenshot in result['screenshots']:
                    f.write(f"Screenshot: {screenshot}\n")
                
                f.write(f"\nExtracted Text:\n")
                f.write(result['text'])
                f.write("\n\n" + "=" * 80 + "\n\n")
        
        print(f"\n✓ Results saved to {output_file}")
    
    def cleanup(self):
        """Close browser"""
        self.driver.quit()


# Main execution
if __name__ == "__main__":
    automation = WebsiteScreenshotOCR(tesseract_path=TESSERACT_PATH)
    
    try:
        print("=" * 80)
        print("AP CLASSROOM SCREENSHOT & OCR AUTOMATION")
        print("=" * 80)
        print(f"\n🌐 Navigating to: {WEBSITE_URL}")
        automation.navigate_to_url(WEBSITE_URL)
        
        # Pause for login
        print("\n" + "=" * 80)
        print("⚠️  PLEASE LOG IN TO AP CLASSROOM")
        print("⚠️  Navigate to your assignment and the FIRST question")
        print("⚠️  Press ENTER when ready to start automation...")
        print("=" * 80)
        input()
        
        print(f"\n🔘 Button selector: {BUTTON_SELECTOR}")
        print(f"📊 Will process {MAX_CLICKS} questions")
        print(f"⏱️  Wait time: {WAIT_TIME} seconds\n")
        
        # Start automation
        automation.click_button_and_capture(
            button_selector=BUTTON_SELECTOR,
            selector_type=SELECTOR_TYPE,
            max_clicks=MAX_CLICKS,
            wait_time=WAIT_TIME,
            output_folder=OUTPUT_FOLDER
        )
        
        # Save results
        automation.save_results(OCR_RESULTS_FILE)
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"📁 Screenshots: {OUTPUT_FOLDER}/")
        print(f"📄 OCR Results: {OCR_RESULTS_FILE}")
        print(f"✓ Processed: {len(automation.ocr_results)} questions")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        automation.cleanup()
        print("\n🔒 Browser closed.")
