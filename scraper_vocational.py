import json
import os
import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Get credentials from GitHub Secrets
USERNAME = os.environ.get('COMPANY_USERNAME')
PASSWORD = os.environ.get('COMPANY_PASSWORD')
BASE_URL = "http://adcdriving.dyndns.biz"

# Class capacity for vocational (all 50)
VOCATIONAL_CAPACITY = 50

def setup_driver():
    """Setup Chrome driver with automatic version management"""
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
    """Login using Selenium"""
    print("🔐 Attempting login with Selenium...")
    
    try:
        driver.get(f"{BASE_URL}/star/User/Login")
        print(f"   Page loaded: {driver.title}")
        time.sleep(3)
        
        username_field = driver.find_element(By.ID, "UserName")
        username_field.clear()
        username_field.send_keys(USERNAME)
        print("   ✅ Username entered")
        
        password_field = driver.find_element(By.ID, "Password")
        password_field.clear()
        password_field.send_keys(PASSWORD)
        print("   ✅ Password entered")
        
        login_button = driver.find_element(By.ID, "btnLogin")
        login_button.click()
        print("   ✅ Clicked login button")
        
        time.sleep(5)
        
        current_url = driver.current_url
        print(f"   Current URL: {current_url}")
        
        if "login" not in current_url.lower():
            print("✅ Login successful!")
            return True
        else:
            print("❌ Login failed")
            return False
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False

def get_vocational_attendance(driver, url_path, category_filter=None):
    """Fetch vocational attendance from a specific URL"""
    all_records = []
    
    try:
        print(f"  🔍 Scraping {url_path}...")
        driver.get(f"{BASE_URL}{url_path}")
        time.sleep(3)
        
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
                    # Extract data based on the HTML structure
                    class_id = cells[0].get_text(strip=True) if len(cells) > 0 else ""
                    class_code = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    date_str = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    class_name = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                    present_count = cells[4].get_text(strip=True) if len(cells) > 4 else "0"
                    
                    # Skip if no valid class ID
                    if not class_id or not class_id.isdigit():
                        continue
                    
                    # Determine category based on class name or URL
                    category = "Unknown"
                    if category_filter:
                        category = category_filter
                    else:
                        class_name_upper = class_name.upper()
                        if "E-HAILING" in class_name_upper or "E HAILING" in class_name_upper:
                            category = "e-Hailing"
                        elif "PSV" in class_name_upper or "BAS MINI" in class_name_upper:
                            category = "Bas Mini"
                        elif "GDL" in class_name_upper:
                            category = "GDL"
                    
                    # Parse present count
                    try:
                        present_num = int(present_count) if present_count.isdigit() else 0
                    except:
                        present_num = 0
                    
                    # Parse date
                    try:
                        date_obj = datetime.strptime(date_str, '%d/%m/%Y')
                    except:
                        date_obj = None
                    
                    # Only include future dates
                    if date_obj and date_obj > datetime.now():
                        all_records.append({
                            'date': date_str,
                            'class_id': class_id,
                            'class_name': class_name,
                            'class_code': class_code,
                            'category': category,
                            'present_count': str(present_num),
                            'total_students': str(VOCATIONAL_CAPACITY),
                            'timestamp': date_obj.isoformat()
                        })
        
        print(f"     ✅ Found {len(all_records)} class(es)")
        return all_records
        
    except Exception as e:
        print(f"     ❌ Error scraping {url_path}: {e}")
        return []

def scrape_all_vocational(driver):
    """Scrape all vocational categories"""
    print("\n📅 Fetching Vocational Attendance Data")
    print("=" * 50)
    
    all_records = []
    
    # PSV2 URL contains both e-Hailing and Bas Mini
    print("\n📌 Scraping PSV2 (e-Hailing & Bas Mini)...")
    psv2_records = get_vocational_attendance(driver, "/star/AttendanceRecord/Psv2")
    
    # Categorize PSV2 records
    for record in psv2_records:
        class_name_upper = record['class_name'].upper()
        if "E-HAILING" in class_name_upper or "E HAILING" in class_name_upper:
            record['category'] = "e-Hailing"
        elif "PSV" in class_name_upper or "BAS" in class_name_upper:
            record['category'] = "Bas Mini"
        all_records.append(record)
    
    # GDL2 URL contains GDL classes
    print("\n📌 Scraping GDL2 (GDL)...")
    gdl_records = get_vocational_attendance(driver, "/star/AttendanceRecord/Gdl2")
    for record in gdl_records:
        record['category'] = "GDL"
        all_records.append(record)
    
    return all_records

def save_vocational_data(attendance_records):
    """Save vocational data to JSON file"""
    # Sort by date
    attendance_records.sort(key=lambda x: datetime.strptime(x['date'], '%d/%m/%Y'))
    
    # Group by category
    grouped_data = {
        'e-Hailing': [],
        'Bas Mini': [],
        'GDL': []
    }
    
    for record in attendance_records:
        category = record['category']
        if category in grouped_data:
            # Remove timestamp field (used only for sorting)
            clean_record = {k: v for k, v in record.items() if k != 'timestamp'}
            grouped_data[category].append(clean_record)
    
    output = {
        'last_updated': datetime.now().isoformat(),
        'vocational_summary': grouped_data
    }
    
    with open('vocational.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Saved vocational data to vocational.json")
    
    # Print summary
    print("\n📊 VOCATIONAL SUMMARY:")
    print("=" * 50)
    for category in ['e-Hailing', 'Bas Mini', 'GDL']:
        if grouped_data[category]:
            print(f"\n🚗 {category.upper()}:")
            for record in grouped_data[category]:
                present = int(record['present_count'])
                total = int(record['total_students'])
                status = f"{present}/{total}"
                if present == total and total > 0:
                    status += " 🔴 FULL"
                print(f"   📅 {record['date']} - {record['class_name']}: {status}")

def main():
    print("🚀 Vocational Attendance Scraper (Selenium Version)")
    print("=" * 50)
    print(f"Username configured: {'Yes' if USERNAME else 'No'}")
    print(f"Password configured: {'Yes' if PASSWORD else 'No'}")
    print()
    
    if not USERNAME or not PASSWORD:
        print("❌ Missing credentials!")
        exit(1)
    
    driver = None
    try:
        print("📱 Setting up browser...")
        driver = setup_driver()
        print("✅ Browser ready")
        
        if login_with_selenium(driver):
            print("\n✅ Ready to fetch vocational attendance data")
            vocational_data = scrape_all_vocational(driver)
            
            if vocational_data:
                save_vocational_data(vocational_data)
                print(f"\n✅ Successfully processed {len(vocational_data)} vocational class records")
            else:
                print("\n⚠️ No vocational records found")
                output = {
                    'last_updated': datetime.now().isoformat(),
                    'vocational_summary': {
                        'e-Hailing': [],
                        'Bas Mini': [],
                        'GDL': []
                    }
                }
                with open('vocational.json', 'w') as f:
                    json.dump(output, f, indent=2)
        else:
            print("❌ Login failed")
            exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    finally:
        if driver:
            driver.quit()
            print("🔚 Browser closed")

if __name__ == "__main__":
    main()
