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
        Initialize the automation tool
        
        Args:
            driver_path: Path to ChromeDriver (optional, uses webdriver-manager if not provided)
            tesseract_path: Path to Tesseract executable (optional if in PATH)
        """
        # Set up Tesseract path if provided (Windows default path)
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        elif os.name == 'nt':  # Windows
            default_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            if os.path.exists(default_path):
                pytesseract.pytesseract.tesseract_cmd = default_path
        
        # Set up Chrome driver with maximized window
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        options.add_argument('--force-device-scale-factor=1')  # Prevent scaling issues
        
        if driver_path:
            service = Service(executable_path=driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
        else:
            # Use webdriver-manager to automatically download and manage ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        
        self.screenshots = []
        self.ocr_results = []
    
    def navigate_to_url(self, url):
        """Navigate to the target website"""
        self.driver.get(url)
        time.sleep(2)  # Wait for page to load
    
    def preprocess_image(self, image_path):
        """
        Preprocess image to improve OCR accuracy
        
        Args:
            image_path: Path to the image
            
        Returns:
            Preprocessed PIL Image object
        """
        # Open image
        image = Image.open(image_path)
        
        # Convert to grayscale
        image = image.convert('L')
        
        # Increase contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        
        # Increase sharpness
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)
        
        # Apply slight blur to reduce noise
        image = image.filter(ImageFilter.MedianFilter(size=3))
        
        return image
    
    def clean_ocr_text(self, text):
        """
        Clean OCR text by removing special characters and fixing common OCR errors
        
        Args:
            text: Raw OCR text
            
        Returns:
            Cleaned text
        """
        # Remove circled letters/numbers (common OCR artifacts)
        # Patterns: @, ©, ®, ⓐ, ⓑ, ⓒ, ⓓ, etc.
        text = re.sub(r'[©®@⊕⊗⊙◉●○◎⦿⓪①②③④⑤⑥⑦⑧⑨⑩ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏ]', '', text)
        
        # Remove standalone special characters at start of lines
        text = re.sub(r'^[^\w\s]+\s*', '', text, flags=re.MULTILINE)
        
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Remove spaces before punctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        
        # Fix common OCR errors
        replacements = {
            'l': 'I',  # lowercase L often misread as I in certain contexts
            '0': 'O',  # zero vs letter O (context-dependent)
            '|': 'I',  # pipe character
            '§': 'S',
            '£': 'E',
            'ﬁ': 'fi',
            'ﬂ': 'fl',
        }
        
        # Apply replacements cautiously (only at word boundaries)
        for old, new in replacements.items():
            # Only replace if it looks like a mistake (e.g., |t -> It, but not in numbers)
            if old == '|':
                text = re.sub(r'\|(?=[a-z])', new, text)
        
        # Remove trailing special characters at end of lines
        text = re.sub(r'[^\w\s.!?,;:\'\"-]+$', '', text, flags=re.MULTILINE)
        
        # Trim whitespace
        text = '\n'.join(line.strip() for line in text.split('\n'))
        
        return text.strip()
    
    def scroll_and_capture(self, output_folder, iteration):
        """
        Capture multiple screenshots with scrolling to get complete content
        
        Args:
            output_folder: Folder to save screenshots
            iteration: Current iteration number
            
        Returns:
            List of screenshot paths
        """
        screenshot_paths = []
        
        # Capture at default position
        screenshot_path = os.path.join(output_folder, f"screenshot_{iteration}_default.png")
        self.driver.save_screenshot(screenshot_path)
        screenshot_paths.append(screenshot_path)
        
        # Get page height
        page_height = self.driver.execute_script("return document.body.scrollHeight")
        viewport_height = self.driver.execute_script("return window.innerHeight")
        
        # If page is scrollable, capture scrolled view
        if page_height > viewport_height:
            # Scroll down to capture bottom content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)  # Wait for scroll
            
            screenshot_path_scroll = os.path.join(output_folder, f"screenshot_{iteration}_scrolled.png")
            self.driver.save_screenshot(screenshot_path_scroll)
            screenshot_paths.append(screenshot_path_scroll)
            
            # Scroll back to top
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
        
        return screenshot_paths
    
    def click_button_and_capture(self, button_selector, selector_type='css', 
                                  max_clicks=10, wait_time=1, output_folder='screenshots'):
        """
        Click button repeatedly and capture screenshots with enhanced OCR
        
        Args:
            button_selector: The selector for the button (CSS, XPath, ID, etc.)
            selector_type: Type of selector ('css', 'xpath', 'id', 'class')
            max_clicks: Maximum number of times to click
            wait_time: Seconds to wait between clicks
            output_folder: Folder to save screenshots
        """
        # Create output folder if it doesn't exist
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        # Map selector types to Selenium By methods
        selector_map = {
            'css': By.CSS_SELECTOR,
            'xpath': By.XPATH,
            'id': By.ID,
            'class': By.CLASS_NAME,
            'name': By.NAME
        }
        
        by_method = selector_map.get(selector_type, By.CSS_SELECTOR)
        
        try:
            # Wait for button to be clickable
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((by_method, button_selector))
            )
            
            for i in range(max_clicks):
                print(f"Capturing question {i + 1}/{max_clicks}...")
                
                # Wait for content to load
                time.sleep(wait_time)
                
                # Scroll to top before capturing
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.5)
                
                # Capture screenshots (default + scrolled if needed)
                screenshot_paths = self.scroll_and_capture(output_folder, i + 1)
                
                # Perform OCR on all screenshots and combine results
                combined_text = ""
                for screenshot_path in screenshot_paths:
                    ocr_text = self.perform_ocr(screenshot_path)
                    combined_text += ocr_text + "\n"
                
                # Clean the combined text
                cleaned_text = self.clean_ocr_text(combined_text)
                
                self.ocr_results.append({
                    'screenshots': screenshot_paths,
                    'text': cleaned_text,
                    'iteration': i + 1
                })
                
                # Click the button to go to next question
                try:
                    button.click()
                    time.sleep(0.5)  # Brief pause after click
                except Exception as e:
                    print(f"Error clicking button: {e}")
                    break
                
        except TimeoutException:
            print(f"Timeout: Could not find button with selector '{button_selector}'")
        except Exception as e:
            print(f"Error: {e}")
    
    def perform_ocr(self, image_path):
        """
        Perform OCR on a screenshot with preprocessing
        
        Args:
            image_path: Path to the screenshot image
            
        Returns:
            Extracted text from the image
        """
        try:
            # Preprocess image
            image = self.preprocess_image(image_path)
            
            # Perform OCR with custom config for better accuracy
            custom_config = r'--oem 3 --psm 6'  # Use LSTM engine, assume uniform text block
            text = pytesseract.image_to_string(image, config=custom_config)
            
            return text.strip()
        except Exception as e:
            print(f"OCR error for {image_path}: {e}")
            return ""
    
    def save_results(self, output_file='ocr_results.txt'):
        """Save all OCR results to a text file"""
        with open(output_file, 'w', encoding='utf-8') as f:
            for result in self.ocr_results:
                f.write(f"{'='*60}\n")
                f.write(f"Question {result['iteration']}\n")
                f.write(f"{'='*60}\n")
                for screenshot in result['screenshots']:
                    f.write(f"Screenshot: {screenshot}\n")
                f.write(f"\n{result['text']}\n")
                f.write("\n" + "="*60 + "\n\n")
        
        print(f"Results saved to {output_file}")
    
    def cleanup(self):
        """Close the browser and clean up"""
        self.driver.quit()


# Example usage
if __name__ == "__main__":
    # Initialize the automation tool with config settings
    automation = WebsiteScreenshotOCR(tesseract_path=TESSERACT_PATH)
    
    try:
        print(f"Navigating to: {WEBSITE_URL}")
        automation.navigate_to_url(WEBSITE_URL)
        
        # PAUSE FOR LOGIN (Important for AP Classroom)
        print("\n" + "="*60)
        print("⚠️  PLEASE LOG IN TO AP CLASSROOM NOW")
        print("⚠️  Navigate to your assignment if needed")
        print("⚠️  Press ENTER when you're ready to start automation...")
        print("="*60 + "\n")
        input()  # Wait for user to press Enter
        
        print(f"Looking for button: {BUTTON_SELECTOR}")
        print(f"Will click {MAX_CLICKS} times with {WAIT_TIME}s wait time")
        
        # Click button and capture screenshots
        automation.click_button_and_capture(
            button_selector=BUTTON_SELECTOR,
            selector_type=SELECTOR_TYPE,
            max_clicks=MAX_CLICKS,
            wait_time=WAIT_TIME,
            output_folder=OUTPUT_FOLDER
        )
        
        # Save all OCR results
        automation.save_results(OCR_RESULTS_FILE)
        
        print("\n=== Summary ===")
        print(f"Screenshots saved in: {OUTPUT_FOLDER}/")
        print(f"OCR results saved to: {OCR_RESULTS_FILE}")
        print(f"Total captures: {len(automation.ocr_results)}")
        
    except Exception as e:
        print(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        automation.cleanup()
        print("Browser closed.")
