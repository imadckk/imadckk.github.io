import json
import os
import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Get credentials from GitHub Secrets
USERNAME = os.environ.get('COMPANY_USERNAME')
PASSWORD = os.environ.get('COMPANY_PASSWORD')
BASE_URL = "http://adcdriving.dyndns.biz"

# Class capacity mapping - ALL set to 50 as requested
CLASS_CAPACITY = {
    "kpp01": 50,
    "e_hailing": 50,
    "bas_mini": 50,
    "gdl": 50
}

def setup_driver():
    """Setup Chrome driver for headless operation"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def login_with_selenium(driver):
    """Login to the system - session persists for all subsequent requests"""
    print("🔐 Attempting login...")
    
    try:
        driver.get(f"{BASE_URL}/star/User/Login")
        print(f"   Page loaded: {driver.title}")
        time.sleep(3)
        
        # Enter username
        username_field = driver.find_element(By.ID, "UserName")
        username_field.clear()
        username_field.send_keys(USERNAME)
        print("   ✅ Username entered")
        
        # Enter password
        password_field = driver.find_element(By.ID, "Password")
        password_field.clear()
        password_field.send_keys(PASSWORD)
        print("   ✅ Password entered")
        
        # Click login button
        login_button = driver.find_element(By.ID, "btnLogin")
        login_button.click()
        print("   ✅ Clicked login button")
        
        time.sleep(5)
        
        # Verify login success
        current_url = driver.current_url
        if "login" not in current_url.lower():
            print("✅ Login successful!")
            return True
        else:
            print("❌ Login failed - still on login page")
            return False
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False

def is_future_date(date_str):
    """Check if a date is in the future (not today or past)"""
    try:
        # Parse date from DD/MM/YYYY format
        date_obj = datetime.strptime(date_str, '%d/%m/%Y')
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # Only include dates strictly in the future (not today)
        return date_obj > today
    except Exception as e:
        print(f"   ⚠️ Date parsing error for {date_str}: {e}")
        return False

def parse_table_row(cells, category_type):
    """Extract data from a table row and return standardized record"""
    try:
        if len(cells) < 5:
            return None
        
        # Extract data from appropriate columns
        # Based on your HTML structure:
        # col0: class_id, col1: class_name, col2: date, col3: class_type, col4: present_count
        class_id = cells[0].get_text(strip=True)
        class_name = cells[1].get_text(strip=True)
        date_str = cells[2].get_text(strip=True)
        class_type = cells[3].get_text(strip=True)
        present_count = cells[4].get_text(strip=True)
        
        # Validate data
        if not class_id or not class_id.isdigit():
            return None
        
        if not date_str or not is_future_date(date_str):
            return None  # Skip past or invalid dates
        
        # Convert present count to integer
        try:
            present_num = int(present_count) if present_count.isdigit() else 0
        except:
            present_num = 0
        
        # Get capacity for this category
        total_capacity = CLASS_CAPACITY.get(category_type, 50)
        
        return {
            'date': date_str,
            'class_id': class_id,
            'class_name': class_name,
            'class_type': class_type,
            'present_count': str(present_num),
            'total_students': str(total_capacity)
        }
    except Exception as e:
        print(f"   ⚠️ Error parsing row: {e}")
        return None

def scrape_kpp01(driver):
    """Scrape KPP01 (regular driving license) attendance"""
    print("\n📚 Scraping KPP01 data...")
    print("=" * 50)
    
    records = []
    
    try:
        # Navigate to KPP01 attendance page
        driver.get(f"{BASE_URL}/star/AttendanceRecord/Kpp")
        time.sleep(3)
        
        # Parse the page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find all tables (the main data table)
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                # Skip header rows
                if row.find('th'):
                    continue
                
                cells = row.find_all('td')
                if len(cells) >= 5:
                    record = parse_table_row(cells, 'kpp01')
                    if record:
                        records.append(record)
        
        print(f"✅ Found {len(records)} future KPP01 classes")
        return records
        
    except Exception as e:
        print(f"❌ Error scraping KPP01: {e}")
        return []

def scrape_psv2(driver):
    """Scrape PSV2 page (contains both e-Hailing and Bas Mini)"""
    print("\n🚐 Scraping Vocational data (e-Hailing & Bas Mini)...")
    print("=" * 50)
    
    e_hailing_records = []
    bas_mini_records = []
    
    try:
        # Navigate to PSV2 attendance page
        driver.get(f"{BASE_URL}/star/AttendanceRecord/Psv2")
        time.sleep(3)
        
        # Parse the page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find all tables
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                # Skip header rows
                if row.find('th'):
                    continue
                
                cells = row.find_all('td')
                if len(cells) >= 5:
                    # Get class_type to determine category
                    class_type = cells[3].get_text(strip=True).lower()
                    
                    # Determine which category this belongs to
                    if 'e-hailing' in class_type:
                        record = parse_table_row(cells, 'e_hailing')
                        if record:
                            e_hailing_records.append(record)
                    elif 'psv' in class_type or 'bas' in class_type:
                        record = parse_table_row(cells, 'bas_mini')
                        if record:
                            bas_mini_records.append(record)
        
        print(f"✅ Found {len(e_hailing_records)} future e-Hailing classes")
        print(f"✅ Found {len(bas_mini_records)} future Bas Mini classes")
        return e_hailing_records, bas_mini_records
        
    except Exception as e:
        print(f"❌ Error scraping PSV2: {e}")
        return [], []

def scrape_gdl2(driver):
    """Scrape GDL (Goods Driving License) attendance"""
    print("\n🚚 Scraping GDL data...")
    print("=" * 50)
    
    records = []
    
    try:
        # Navigate to GDL2 attendance page
        driver.get(f"{BASE_URL}/star/AttendanceRecord/Gdl2")
        time.sleep(3)
        
        # Parse the page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find all tables
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                # Skip header rows
                if row.find('th'):
                    continue
                
                cells = row.find_all('td')
                if len(cells) >= 5:
                    record = parse_table_row(cells, 'gdl')
                    if record:
                        records.append(record)
        
        print(f"✅ Found {len(records)} future GDL classes")
        return records
        
    except Exception as e:
        print(f"❌ Error scraping GDL2: {e}")
        return []

def save_data(kpp01_data, e_hailing_data, bas_mini_data, gdl_data):
    """Save all data to attendance.json in the new structure"""
    
    # Sort records by date for each category
    def sort_by_date(records):
        def parse_date(record):
            try:
                return datetime.strptime(record['date'], '%d/%m/%Y')
            except:
                return datetime.min
        return sorted(records, key=parse_date)
    
    # Organize data into the new structure
    output = {
        'last_updated': datetime.now().isoformat(),
        'kpp01': sort_by_date(kpp01_data),
        'vocational': {
            'e_hailing': sort_by_date(e_hailing_data),
            'bas_mini': sort_by_date(bas_mini_data),
            'gdl': sort_by_date(gdl_data)
        }
    }
    
    # Save to file
    with open('attendance.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 FINAL SUMMARY")
    print("=" * 50)
    print(f"KPP01:        {len(kpp01_data)} future classes")
    print(f"e-Hailing:    {len(e_hailing_data)} future classes")
    print(f"Bas Mini:     {len(bas_mini_data)} future classes")
    print(f"GDL:          {len(gdl_data)} future classes")
    print(f"\n💾 Saved to attendance.json")
    
    # Print detailed breakdown by date
    if any([kpp01_data, e_hailing_data, bas_mini_data, gdl_data]):
        print("\n📅 UPCOMING CLASSES BY DATE:")
        print("=" * 50)
        
        all_classes = []
        for record in kpp01_data:
            all_classes.append(('KPP01', record))
        for record in e_hailing_data:
            all_classes.append(('e-Hailing', record))
        for record in bas_mini_data:
            all_classes.append(('Bas Mini', record))
        for record in gdl_data:
            all_classes.append(('GDL', record))
        
        # Sort by date
        all_classes.sort(key=lambda x: datetime.strptime(x[1]['date'], '%d/%m/%Y'))
        
        current_date = None
        for category, record in all_classes:
            if record['date'] != current_date:
                current_date = record['date']
                print(f"\n📅 {record['date']}")
            print(f"   {category:12} - {record['class_type']:20} ({record['present_count']}/{record['total_students']})")

def main():
    """Main execution function"""
    print("🚀 Driving School Attendance Scraper v2.0")
    print("=" * 50)
    print(f"Username configured: {'Yes' if USERNAME else 'No'}")
    print(f"Password configured: {'Yes' if PASSWORD else 'No'}")
    print()
    
    # Check credentials
    if not USERNAME or not PASSWORD:
        print("❌ Missing credentials! Please set COMPANY_USERNAME and COMPANY_PASSWORD in GitHub Secrets.")
        exit(1)
    
    driver = None
    try:
        # Setup browser
        print("📱 Setting up browser...")
        driver = setup_driver()
        print("✅ Browser ready")
        
        # Login once (session persists for all scraping)
        if not login_with_selenium(driver):
            print("❌ Login failed. Cannot proceed.")
            exit(1)
        
        # Scrape all categories
        print("\n✅ Login successful! Starting data collection...")
        
        kpp01_data = scrape_kpp01(driver)
        e_hailing_data, bas_mini_data = scrape_psv2(driver)
        gdl_data = scrape_gdl2(driver)
        
        # Save combined data
        save_data(kpp01_data, e_hailing_data, bas_mini_data, gdl_data)
        
        print("\n✅ All data collected and saved successfully!")
        
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    finally:
        if driver:
            driver.quit()
            print("🔚 Browser closed")

if __name__ == "__main__":
    main()
