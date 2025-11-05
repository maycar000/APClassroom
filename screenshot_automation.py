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
        self.last_question_hash = None  # Track to avoid duplicates
    
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
        Extract question text and answer choices using multiple strategies
        """
        try:
            # Wait for content to load
            time.sleep(2.5)
            
            script = """
            function extractQuestionData() {
                let result = {question: '', answers: [], debug: []};
                
                // Strategy 1: Find all buttons/divs that contain answer choices
                // AP Classroom typically wraps answers in clickable divs/buttons
                const answerElements = [];
                
                // Look for elements with letters A, B, C, D in circles
                const allElements = document.querySelectorAll('button, div[role="button"], label, div');
                
                for (let elem of allElements) {
                    const text = (elem.innerText || elem.textContent || '').trim();
                    
                    // Check if element starts with a circled letter or just A, B, C, D
                    const hasAnswerPattern = /^[ⒶⒷⒸⒹⒺABCDEⒶⒷⒸⒹⒺ]\s+/.test(text) || 
                                           /^\([A-E]\)\s+/.test(text) ||
                                           /^[A-E]\s{2,}/.test(text);
                    
                    if (hasAnswerPattern && text.length > 5 && text.length < 500) {
                        // Make sure it's visible
                        const rect = elem.getBoundingClientRect();
                        if (rect.width > 100 && rect.height > 20) {
                            answerElements.push({
                                text: text,
                                elem: elem
                            });
                        }
                    }
                }
                
                // Strategy 2: If Strategy 1 didn't work, look for specific AP Classroom structure
                if (answerElements.length === 0) {
                    // Look for divs that contain both a letter indicator and text
                    const containers = document.querySelectorAll('div, button');
                    
                    for (let container of containers) {
                        // Check if it has children with letter + text structure
                        const children = container.children;
                        if (children.length >= 2) {
                            const firstChild = children[0];
                            const text = container.innerText || container.textContent || '';
                            
                            // Check if first child might be a letter indicator
                            const firstText = (firstChild.innerText || firstChild.textContent || '').trim();
                            
                            if (/^[A-E]$/.test(firstText) && text.length > 10 && text.length < 500) {
                                const rect = container.getBoundingClientRect();
                                if (rect.width > 100 && rect.height > 20) {
                                    answerElements.push({
                                        text: text.trim(),
                                        elem: container
                                    });
                                }
                            }
                        }
                    }
                }
                
                // Clean and deduplicate answers
                const seenTexts = new Set();
                for (let item of answerElements) {
                    let cleanText = item.text;
                    
                    // Remove circled letters and clean up
                    cleanText = cleanText.replace(/^[ⒶⒷⒸⒹⒺⒶⒷⒸⒹⒺ]\s*/g, '');
                    cleanText = cleanText.replace(/^\([A-E]\)\s*/g, '');
                    cleanText = cleanText.replace(/^[A-E]\s+/g, '');
                    cleanText = cleanText.trim();
                    
                    // Only add if we haven't seen this text and it's substantial
                    if (cleanText.length > 5 && !seenTexts.has(cleanText)) {
                        seenTexts.add(cleanText);
                        result.answers.push(cleanText);
                    }
                }
                
                // Limit to 5 answers (A-E)
                result.answers = result.answers.slice(0, 5);
                
                // Strategy 3: Find the question text
                // Look for question container - usually a div/p with substantial text
                const questionCandidates = [];
                const textElements = document.querySelectorAll('p, div, span, h1, h2, h3');
                
                for (let elem of textElements) {
                    const text = (elem.innerText || elem.textContent || '').trim();
                    
                    // Question characteristics:
                    // - Contains question mark OR words like "which", "what", "following"
                    // - Longer than 30 chars but not too long
                    // - Doesn't contain UI noise
                    const hasQuestionMarkers = text.includes('?') || 
                                              /\\b(which|what|how|who|when|where|following)\\b/i.test(text);
                    
                    const isNotUIElement = !text.match(/^(Question|Mark for Review|Highlights|Notes|More|Option|Bookmark)/i);
                    
                    if (hasQuestionMarkers && 
                        text.length > 30 && 
                        text.length < 1000 && 
                        isNotUIElement) {
                        
                        const rect = elem.getBoundingClientRect();
                        if (rect.width > 200) {
                            questionCandidates.push({
                                text: text,
                                length: text.length,
                                hasQuestion: text.includes('?')
                            });
                        }
                    }
                }
                
                // Pick the best question candidate (prefer ones with ? and reasonable length)
                questionCandidates.sort((a, b) => {
                    if (a.hasQuestion && !b.hasQuestion) return -1;
                    if (!a.hasQuestion && b.hasQuestion) return 1;
                    return Math.abs(a.length - 150) - Math.abs(b.length - 150);
                });
                
                if (questionCandidates.length > 0) {
                    result.question = questionCandidates[0].text;
                }
                
                result.debug = {
                    answerCount: result.answers.length,
                    questionLength: result.question.length,
                    foundAnswers: answerElements.length
                };
                
                return result;
            }
            
            return extractQuestionData();
            """
            
            data = self.driver.execute_script(script)
            
            # Debug output
            print(f"   [DEBUG] Found {data['debug']['answerCount']} answers, question length: {data['debug']['questionLength']}")
            
            # Check if we got valid data
            if not data['question'] or len(data['question']) < 20:
                print(f"   [DEBUG] Question too short or missing")
                return None
                
            if not data['answers'] or len(data['answers']) < 2:
                print(f"   [DEBUG] Not enough answers found ({len(data['answers'])})")
                return None
            
            # Create a simple hash to detect duplicates
            question_hash = hash(data['question'][:100])
            if self.last_question_hash and question_hash == self.last_question_hash:
                print(f"   [DEBUG] Duplicate question detected")
                return None
            
            self.last_question_hash = question_hash
            
            # Format the output cleanly
            formatted = f"{data['question']}\n\n"
            
            # Add answers with letter labels
            letters = ['A', 'B', 'C', 'D', 'E']
            for idx, ans in enumerate(data['answers'][:5]):
                formatted += f"{letters[idx]}. {ans}\n"
            
            return formatted
            
        except Exception as e:
            print(f"  ⚠ JavaScript extraction error: {e}")
            import traceback
            traceback.print_exc()
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
            print(f"\n{'='*60}")
            print(f"📝 Question {i + 1}/{max_clicks}")
            print(f"{'='*60}")
            
            # Wait for page to load completely
            self.wait_for_load()
            time.sleep(wait_time)
            
            # Try extraction
            print(f"   🔍 Extracting content...")
            extracted_text = self.extract_question_and_answers()
            
            if extracted_text:
                self.ocr_results.append({
                    'question_num': i + 1,
                    'text': extracted_text
                })
                successful_extractions += 1
                print(f"   ✅ Successfully extracted")
                # Show preview of what was extracted
                preview = extracted_text.split('\n')[0][:80]
                print(f"   Preview: {preview}...")
            else:
                print(f"   ❌ Extraction failed")
                # Add placeholder
                self.ocr_results.append({
                    'question_num': i + 1,
                    'text': f"[Unable to extract question {i + 1} - please check manually]\n\n"
                })
            
            # Click next (except on last question)
            if i < max_clicks - 1:
                try:
                    print(f"   ⏭  Clicking Next button...")
                    next_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((by_method, BUTTON_SELECTOR))
                    )
                    next_btn.click()
                    time.sleep(2.5)  # Wait for page transition
                    print(f"   ✓ Navigated to next question")
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
                f.write(f"QUESTION {result['question_num']}\n")
                f.write("-" * 80 + "\n")
                f.write(result['text'])
                f.write("\n")
        
        print(f"\n💾 Results saved to: {output_file}")
    
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
        print("⚠️  SETUP INSTRUCTIONS:")
        print("    1. Log in to AP Classroom")
        print("    2. Navigate to the FIRST question")
        print("    3. Make sure the question and ALL answer choices are visible")
        print("    4. Press ENTER when ready to start extraction")
        print("=" * 80)
        input()
        
        print(f"\n▶  Starting extraction...")
        print(f"    Total questions: {MAX_CLICKS}")
        print(f"    Wait time: {WAIT_TIME} seconds between questions\n")
        
        # Run automation
        ocr.run_automation(MAX_CLICKS, WAIT_TIME, OUTPUT_FOLDER)
        
        # Save results
        ocr.save_results(OCR_RESULTS_FILE)
        
        # Summary
        successful = len([r for r in ocr.ocr_results if not r['text'].startswith('[Unable')])
        failed = MAX_CLICKS - successful
        
        print("\n" + "=" * 80)
        print("✅ EXTRACTION COMPLETE!")
        print("=" * 80)
        print(f"📄 Results file: {OCR_RESULTS_FILE}")
        print(f"✓ Successful: {successful}/{MAX_CLICKS} questions")
        if failed > 0:
            print(f"⚠ Failed: {failed} questions (marked in file)")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        ocr.cleanup()
        print("\n👋 Browser closed")

if __name__ == "__main__":
    main()
