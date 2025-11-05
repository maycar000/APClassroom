import os
import platform

def setup_config():
    """Interactive setup wizard for AP Classroom automation"""
    
    print("=" * 60)
    print("  AP CLASSROOM - Simple Setup")
    print("=" * 60)
    
    # Website URL
    print("\n--- Website URL ---")
    website_url = input("Enter your AP Classroom assignment URL: ").strip()
    
    if not website_url:
        print("❌ URL is required!")
        return
    
    # Number of questions
    print("\n--- Number of Questions ---")
    max_clicks = input("How many questions to capture? [78]: ").strip() or "78"
    
    # Wait time
    print("\n--- Speed Settings ---")
    wait_time = input("Seconds to wait between questions? [3]: ").strip() or "3"
    
    # Tesseract path detection
    print("\n--- Tesseract OCR Detection ---")
    tesseract_path = None
    
    if platform.system() == 'Windows':
        default_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.exists(default_path):
            print(f"✓ Found Tesseract at: {default_path}")
            tesseract_path = default_path
        else:
            custom_path = input("Enter Tesseract path (or press Enter to skip): ").strip()
            if custom_path and os.path.exists(custom_path):
                tesseract_path = custom_path
    
    # Auto-configure for AP Classroom
    button_selector = "[data-test-id='next-button']"
    selector_type = "css"
    output_folder = "os.path.join(os.path.expanduser('~'), 'Documents', 'APClassroom_Screenshots')"
    ocr_results_file = "os.path.join(os.path.expanduser('~'), 'Documents', 'APClassroom_Results.txt')"
    
    # Format tesseract path
    if tesseract_path:
        tesseract_repr = f'r"{tesseract_path}"'
    else:
        tesseract_repr = "None"
    
    # Summary
    print("\n" + "=" * 60)
    print("  Configuration Summary")
    print("=" * 60)
    print(f"Website:          {website_url}")
    print(f"Questions:        {max_clicks}")
    print(f"Wait Time:        {wait_time} seconds")
    print(f"Button:           Next (auto-configured)")
    print(f"Output Folder:    Documents/APClassroom_Screenshots/")
    print(f"Results File:     Documents/APClassroom_Results.txt")
    if tesseract_path:
        print(f"Tesseract:        {tesseract_path}")
    print("=" * 60)
    
    confirm = input("\nCreate config.py with these settings? [Y/n]: ").strip().lower()
    
    if confirm == 'n':
        print("Setup cancelled.")
        return
    
    # Write config file
    config_content = f"""import os

# AP Classroom Configuration (Auto-generated)

# Website settings
WEBSITE_URL = "{website_url}"

# Button settings (Auto-configured for AP Classroom)
BUTTON_SELECTOR = "{button_selector}"
SELECTOR_TYPE = "{selector_type}"

# Automation settings
MAX_CLICKS = {max_clicks}
WAIT_TIME = {wait_time}

# Tesseract OCR path
TESSERACT_PATH = {tesseract_repr}

# Output settings (Saved to Documents folder)
OUTPUT_FOLDER = {output_folder}
OCR_RESULTS_FILE = {ocr_results_file}
"""
    
    try:
        with open('config.py', 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        print("\n✓ Configuration saved to config.py")
        print("\n" + "=" * 60)
        print("Next steps:")
        print("  1. Make sure Tesseract OCR is installed")
        print("  2. Run: python screenshot_automation.py")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error saving config: {e}")

if __name__ == "__main__":
    setup_config()
