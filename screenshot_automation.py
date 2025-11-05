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
        options.add_argument('--force-device-scale-factor=1.5')
        
        # Initialize driver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_window_size(1920, 1080)
        
        self.ocr_results = []
        self.last_question_text = None  # Track to avoid duplicates
    
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
    
    def extract_question_and_answers(self):
        """
        Extract question text and answer choices with improved selectors
        """
        try:
            # Wait longer for content to load and stabilize
            time.sleep(2)
            
            script = """
            function extractQuestionData() {
                let result = {question: '', answers: [], rawAnswers: []};
                
                // Method 1: Look for specific AP Classroom structure
                // Find all radio buttons with their labels
                const radioButtons = document.querySelectorAll('input[type="radio"]');
                const answerSet = new Set();
                
                for (let radio of radioButtons) {
                    // Get the label associated with this radio button
                    let label = radio.closest('label');
                    if (!label) {
                        // Try finding label by for attribute
                        label = document.querySelector(`label[for="${radio.id}"]`);
                    }
                    
                    if (label) {
                        let text = label.innerText || label.textContent;
                        text = text.trim();
                        
                        // Clean up the text - remove "Option X," prefix
                        text = text.replace(/^Option [A-E],\s*/i, '');
                        text = text.replace(/^[A-E]\s+/i, '');
                        
                        if (text.length > 2 && !text.match(/^(mcqRadio|Crossout|bookmark)/)) {
                            answerSet.add(text);
                        }
                    }
                }
                
                result.answers = Array.from(answerSet);
                
                // Method 2: Find question text
                // Look for the main question container
                const questionSelectors = [
                    '[class*="question-text"]',
                    '[class*="stem"]',
                    '[data-test*="question"]',
                    'div[class*="Question"] p',
                    'main p'
                ];
                
                for (let selector of questionSelectors) {
                    const elements = document.querySelectorAll(selector);
                    for (let elem of elements) {
                        let text = elem.innerText || elem.textContent;
                        text = text.trim();
                        
                        // Question should have decent length and proper content
                        if (text.length > 30 && text.length < 1000) {
                            // Avoid UI elements
                            if (!text.match(/^(Question|Mark for Review|Highlights|bookmark)/i)) {
                                // Check if it looks like a question
                                if (text.includes('?') || text.includes('following') || text.includes('which')) {
                                    result.question = text;
                                    break;
                                }
                            }
                        }
                    }
                    if (result.question) break;
                }
                
                // Method 3: Fallback - look for answer structure in text
                if (result.answers.length === 0) {
                    const allText = document.body.innerText;
                    const lines = allText.split('\\n');
                    
                    for (let line of lines) {
                        line = line.trim();
                        // Match clean answer patterns: "A Some answer text"
                        const match = line.match(/^([A-E])\\s+(.+)$/);
                        if (match && match[2].length > 3) {
                            const answerText = match[2].trim();
                            // Avoid UI noise
                            if (!answerText.match(/^(Option|mcqRadio|Crossout|bookmark)/)) {
                                result.answers.push(answerText);
                            }
                        }
                    }
                }
                
                return result;
            }
            
            return extractQuestionData();
            """
            
            data = self.driver.execute_script(script)
            
            # Check if we got valid data
            if not data['question'] or not data['answers']:
                return None
            
            # Check if this is a duplicate (same as last question)
            if self.last_question_text and data['question'] == self.last_question_text:
                return None
            
            self.last_question_text = data['question']
            
            # Format the output cleanly
            formatted = f"QUESTION:\n{data['question']}\n\n"
            
            # Add answers with letter labels if not already present
            if data['answers']:
                letters = ['A', 'B', 'C', 'D', 'E']
                for idx, ans in enumerate(data['answers'][:5]):  # Max 5 answers
                    # Check if answer already starts with a letter
                    if re.match(r'^[A-E][\.\)]\s', ans):
                        formatted += f"{ans}\n"
                    else:
                        formatted += f"{letters[idx]}. {ans}\n"
            
            return formatted
            
        except Exception as e:
            print(f"  ⚠ JavaScript extraction failed: {e}")
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
        
        successful_extractions = 0
        
        for i in range(max_clicks):
            print(f"\n📝 Question {i + 1}/{max_clicks}")
            
            # Wait for page to load completely
            self.wait_for_load()
            time.sleep(wait_time)
            
            # Try extraction
            print(f"   🔍 Extracting content...")
            extracted_text = self.extract_question_and_answers()
            
            if extracted_text:
                self.ocr_results.append({
                    'question_num': i + 1,
                    'text': extracted_text,
                    'method': 'JavaScript'
                })
                successful_extractions += 1
                print(f"   ✓ Successfully extracted")
            else:
                print(f"   ⚠ Extraction failed or duplicate detected")
                # Still add a placeholder so question numbers stay in sync
                self.ocr_results.append({
                    'question_num': i + 1,
                    'text': f"QUESTION:\n[Unable to extract question {i + 1}]\n\n",
                    'method': 'Failed'
                })
            
            # Click next (except on last question)
            if i < max_clicks - 1:
                try:
                    print(f"   ⏭ Clicking Next...")
                    next_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((by_method, BUTTON_SELECTOR))
                    )
                    next_btn.click()
                    time.sleep(2)  # Wait for transition
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
    print("AP CLASSROOM - QUESTIONS & ANSWERS EXTRACTOR (IMPROVED)")
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
        print(f"   Extracting via improved JavaScript selectors\n")
        
        # Run automation
        ocr.run_automation(MAX_CLICKS, WAIT_TIME, OUTPUT_FOLDER)
        
        # Save results
        ocr.save_results(OCR_RESULTS_FILE)
        
        # Summary
        successful = sum(1 for r in ocr.ocr_results if r.get('method') == 'JavaScript')
        print("\n" + "=" * 80)
        print("✅ COMPLETE!")
        print("=" * 80)
        print(f"📄 Results: {OCR_RESULTS_FILE}")
        print(f"✓ Successfully extracted: {successful}/{len(ocr.ocr_results)} questions")
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
