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
        Extract ONLY the currently visible question and answers
        """
        try:
            # Wait for content to load
            time.sleep(2)
            
            script = """
            function extractCurrentQuestionData() {
                let result = {question: '', answers: [], debug: {}};
                
                // DIRECT APPROACH: Find the currently visible question container
                const allQuestionContainers = document.querySelectorAll('.learnosity-item, [class*="question"], .lrn-assessment-wrapper, .lrn_assessment');
                let activeContainer = null;
                
                console.log("Total containers found:", allQuestionContainers.length);
                
                for (let container of allQuestionContainers) {
                    const style = window.getComputedStyle(container);
                    const rect = container.getBoundingClientRect();
                    
                    // Check if container is actually visible and has substantial size
                    const isVisible = style.display !== 'none' && 
                                     style.visibility !== 'hidden' && 
                                     style.opacity !== '0' &&
                                     rect.width > 100 && 
                                     rect.height > 100 &&
                                     rect.top >= 0 &&
                                     rect.top < window.innerHeight;
                    
                    console.log("Container check:", {
                        display: style.display,
                        visibility: style.visibility,
                        opacity: style.opacity,
                        width: rect.width,
                        height: rect.height,
                        top: rect.top,
                        isVisible: isVisible
                    });
                    
                    if (isVisible) {
                        // Additional check: container should have question content
                        const hasStimulus = container.querySelector('.lrn_stimulus_content');
                        const hasRadioInputs = container.querySelector('input[type="radio"]');
                        
                        if (hasStimulus || hasRadioInputs) {
                            activeContainer = container;
                            console.log("Found active container!");
                            break;
                        }
                    }
                }
                
                result.debug.containerFound = !!activeContainer;
                result.debug.totalContainers = allQuestionContainers.length;
                
                if (activeContainer) {
                    // Extract question text
                    const stimulusContent = activeContainer.querySelector('.lrn_stimulus_content');
                    
                    if (stimulusContent) {
                        const paragraphs = stimulusContent.querySelectorAll('p');
                        
                        for (let p of paragraphs) {
                            const text = p.innerText || p.textContent || '';
                            if (text.trim().length > 20) {
                                if (text.includes('?') || text.includes('following')) {
                                    result.question = text.trim();
                                    break;
                                } else if (!result.question) {
                                    result.question = text.trim();
                                }
                            }
                        }
                        
                        // Fallback: get any text from stimulus
                        if (!result.question) {
                            result.question = stimulusContent.innerText || stimulusContent.textContent || '';
                            result.question = result.question.trim().substring(0, 200); // Limit length
                        }
                        
                        result.debug.foundStimulus = true;
                        result.debug.paragraphCount = paragraphs.length;
                    }
                    
                    // Extract answers from this container only
                    const radioInputs = activeContainer.querySelectorAll('input[type="radio"]');
                    result.debug.foundInputs = radioInputs.length;
                    
                    const seenAnswers = new Set();
                    
                    for (let input of radioInputs) {
                        const label = document.querySelector(`label[for="${input.id}"]`);
                        
                        if (label) {
                            const possibleAnswer = label.querySelector('.lrn-possible-answer');
                            
                            if (possibleAnswer) {
                                const contentWrappers = possibleAnswer.querySelectorAll('.lrn_contentWrapper');
                                
                                for (let wrapper of contentWrappers) {
                                    if (wrapper.closest('.sr-only')) {
                                        continue;
                                    }
                                    
                                    const p = wrapper.querySelector('p');
                                    if (p) {
                                        const text = (p.innerText || p.textContent || '').trim();
                                        
                                        if (text.length > 2 && !seenAnswers.has(text) && !/^[A-E]$/.test(text)) {
                                            seenAnswers.add(text);
                                            result.answers.push(text);
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                    
                    result.answers = result.answers.slice(0, 5);
                    result.debug.answerCount = result.answers.length;
                    result.debug.questionLength = result.question.length;
                    
                    // Try to find question number
                    const questionNumElement = activeContainer.querySelector('.item-number');
                    if (questionNumElement) {
                        const numText = questionNumElement.innerText.trim();
                        if (numText && !isNaN(numText)) {
                            result.debug.currentQuestion = parseInt(numText);
                        }
                    }
                } else {
                    result.debug.error = "No active container found";
                    // Debug: log all containers for analysis
                    result.debug.allContainers = Array.from(allQuestionContainers).map(container => {
                        const style = window.getComputedStyle(container);
                        const rect = container.getBoundingClientRect();
                        return {
                            classes: container.className,
                            display: style.display,
                            visibility: style.visibility,
                            opacity: style.opacity,
                            size: `${rect.width}x${rect.height}`,
                            position: `top: ${rect.top}`,
                            hasStimulus: !!container.querySelector('.lrn_stimulus_content'),
                            hasRadio: !!container.querySelector('input[type="radio"]')
                        };
                    });
                }
                
                return result;
            }
            
            return extractCurrentQuestionData();
            """
            
            data = self.driver.execute_script(script)
            
            # Debug output
            print(f"   [DEBUG] Total containers: {data['debug'].get('totalContainers', 0)}")
            print(f"   [DEBUG] Container found: {data['debug'].get('containerFound', False)}")
            print(f"   [DEBUG] Current question: {data['debug'].get('currentQuestion', 'Unknown')}")
            print(f"   [DEBUG] Stimulus: {data['debug'].get('foundStimulus', False)}")
            print(f"   [DEBUG] Radio inputs: {data['debug'].get('foundInputs', 0)}")
            print(f"   [DEBUG] Answers: {data['debug'].get('answerCount', 0)}")
            print(f"   [DEBUG] Q length: {data['debug'].get('questionLength', 0)}")
            
            if 'error' in data['debug']:
                print(f"   ❌ {data['debug']['error']}")
                # Log detailed container info for debugging
                if 'allContainers' in data['debug']:
                    print(f"   [DEBUG] Container details:")
                    for i, container in enumerate(data['debug']['allContainers'][:5]):  # Show first 5
                        print(f"     Container {i}: {container}")
            
            # Validate data with more lenient criteria
            if not data['question'] or len(data['question']) < 10:  # Reduced from 20 to 10
                print(f"   ❌ Question too short or missing")
                return None
                
            if not data['answers'] or len(data['answers']) < 2:
                print(f"   ❌ Need at least 2 answers (found {len(data['answers'])})")
                return None
            
            # Format output
            question_num = data['debug'].get('currentQuestion', 'Unknown')
            formatted = f"{data['question']}\n\n"
            
            # Add answers with letters
            letters = ['A', 'B', 'C', 'D', 'E']
            for idx, ans in enumerate(data['answers'][:5]):
                formatted += f"{letters[idx]}. {ans}\n"
            
            return formatted
            
        except Exception as e:
            print(f"  ⚠ Extraction error: {e}")
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
        
        for i in range(max_clicks):
            print(f"\n{'='*70}")
            print(f"📝 QUESTION {i + 1}/{max_clicks}")
            print(f"{'='*70}")
            
            # Wait for page load
            self.wait_for_load()
            time.sleep(wait_time)
            
            # Extract content
            print(f"   🔍 Extracting content...")
            extracted_text = self.extract_question_and_answers()
            
            if extracted_text:
                self.ocr_results.append({
                    'question_num': i + 1,
                    'text': extracted_text
                })
                print(f"   ✅ Successfully extracted!")
                
                # Show preview
                lines = extracted_text.split('\n')
                preview = lines[0][:60] + "..." if len(lines[0]) > 60 else lines[0]
                print(f"   📄 {preview}")
            else:
                print(f"   ❌ Extraction failed")
                self.ocr_results.append({
                    'question_num': i + 1,
                    'text': f"[Question {i + 1} - Extraction Failed]\n\n"
                })
            
            # Click next
            if i < max_clicks - 1:
                try:
                    print(f"   ⏭  Clicking Next...")
                    next_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((by_method, BUTTON_SELECTOR))
                    )
                    next_btn.click()
                    time.sleep(2)
                    print(f"   ✓ Next question loaded")
                except Exception as e:
                    print(f"   ⚠ Cannot click Next: {e}")
                    print(f"   Stopping...")
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
        
        print(f"\n💾 Saved: {output_file}")
    
    def cleanup(self):
        """Close browser"""
        self.driver.quit()


def main():
    print("=" * 80)
    print("AP CLASSROOM EXTRACTOR - FIXED VERSION")
    print("=" * 80)
    
    ocr = APClassroomOCR(tesseract_path=TESSERACT_PATH)
    
    try:
        print(f"\n🌐 Opening: {WEBSITE_URL}")
        ocr.navigate_to_url(WEBSITE_URL)
        
        # Pause for login
        print("\n" + "=" * 80)
        print("⚠️  SETUP:")
        print("    1. Log in to AP Classroom")
        print("    2. Go to the FIRST question")
        print("    3. Wait for it to fully load")
        print("    4. Press ENTER to start")
        print("=" * 80)
        input()
        
        print(f"\n▶  Starting...")
        print(f"    Questions: {MAX_CLICKS}")
        print(f"    Wait: {WAIT_TIME}s\n")
        
        # Run automation
        ocr.run_automation(MAX_CLICKS, WAIT_TIME, OUTPUT_FOLDER)
        
        # Save results
        ocr.save_results(OCR_RESULTS_FILE)
        
        # Summary
        successful = len([r for r in ocr.ocr_results if not r['text'].startswith('[Question')])
        failed = len(ocr.ocr_results) - successful
        
        print("\n" + "=" * 80)
        print("✅ DONE!")
        print("=" * 80)
        print(f"📄 File: {OCR_RESULTS_FILE}")
        print(f"✓ Success: {successful}/{len(ocr.ocr_results)}")
        if failed > 0:
            print(f"⚠ Failed: {failed}")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\n⚠ Cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        ocr.cleanup()
        print("\n👋 Closed")

if __name__ == "__main__":
    main()
