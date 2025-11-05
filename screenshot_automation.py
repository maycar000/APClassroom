from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import pytesseract
import time
import os

# Try to import config, prompt user to run setup if not found
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
    print("\n⚠ ERROR: config.py not found!")
    print("\nPlease run the setup wizard first:")
    print("  python setup.py")
    print("\nOr manually create config.py with your settings.")
    import sys
    sys.exit(1)

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
        
        # Set up Chrome driver
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        
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
    
    def click_button_and_capture(self, button_selector, selector_type='css', 
                                  max_clicks=10, wait_time=1, output_folder='screenshots'):
        """
        Click button repeatedly and capture screenshots
        
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
                print(f"Capturing screenshot {i + 1}...")
                
                # Take screenshot
                screenshot_path = os.path.join(output_folder, f"screenshot_{i + 1}.png")
                self.driver.save_screenshot(screenshot_path)
                self.screenshots.append(screenshot_path)
                
                # Perform OCR on screenshot
                ocr_text = self.perform_ocr(screenshot_path)
                self.ocr_results.append({
                    'screenshot': screenshot_path,
                    'text': ocr_text,
                    'iteration': i + 1
                })
                
                # Click the button to go to next question
                try:
                    button.click()
                    time.sleep(wait_time)  # Wait for content to update
                except Exception as e:
                    print(f"Error clicking button: {e}")
                    break
                
        except TimeoutException:
            print(f"Timeout: Could not find button with selector '{button_selector}'")
        except Exception as e:
            print(f"Error: {e}")
    
    def perform_ocr(self, image_path):
        """
        Perform OCR on a screenshot
        
        Args:
            image_path: Path to the screenshot image
            
        Returns:
            Extracted text from the image
        """
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            print(f"OCR error for {image_path}: {e}")
            return ""
    
    def save_results(self, output_file='ocr_results.txt'):
        """Save all OCR results to a text file"""
        with open(output_file, 'w', encoding='utf-8') as f:
            for result in self.ocr_results:
                f.write(f"=== Screenshot {result['iteration']} ===\n")
                f.write(f"File: {result['screenshot']}\n")
                f.write(f"Text:\n{result['text']}\n")
                f.write("\n" + "="*50 + "\n\n")
        
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
        
        # PAUSE FOR LOGIN
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
    finally:
        # Clean up
        automation.cleanup()
        print("Browser closed.")
