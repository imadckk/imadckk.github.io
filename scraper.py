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

# Class capacity mapping
CLASS_CAPACITY = {
    "KPP01": 50,
    "KPP02": 50,
    "KPP03": 50,
    "KPP04": 50,
    "PSV": 50,        # For vocational classes
    "GDL": 50,        # For vocational classes
    "default": 50
}

# Endpoints configuration
ENDPOINTS = {
    "kpp01": {
        "url": "/star/AttendanceRecord/Kpp",
        "license_type": "KPP01"
    },
    "e_hailing": {
        "url": "/star/AttendanceRecord/Psv2",
        "license_type": "e-Hailing"
    },
    "bas_mini": {
        "url": "/star/AttendanceRecord/Psv2",
        "license_type": "Bas Mini"
    },
    "gdl": {
        "url": "/star/AttendanceRecord/Gdl2",
        "license_type": "GDL"
    }
}

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

def get_class_capacity(class_name, class_type, license_type):
    """Determine class capacity based on class name/type"""
    full_name = f"{class_type} {class_name} {license_type}".upper()
    
    # Look for capacity in mapping
    for key, capacity in CLASS_CAPACITY.items():
        if key.upper() in full_name:
            return capacity
    
    return CLASS_CAPACITY["default"]

def scrape_attendance_data(driver, endpoint_url, license_type):
    """Scrape attendance data from a specific endpoint WITHOUT date filtering"""
    try:
        print(f"\n📍 Scraping {license_type}...")
        print(f"   URL: {endpoint_url}")
        
        driver.get(f"{BASE_URL}{endpoint_url}")
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        records = []
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                if row.find('th'):
                    continue
                
                cells = row.find_all('td')
                # Table structure: ID, License, Date, Class Type, Present, ...
                if len(cells) >= 5:
                    class_id = cells[0].get_text(strip=True)
                    license_name = cells[1].get_text(strip=True)
                    date_str = cells[2].get_text(strip=True)
                    class_type = cells[3].get_text(strip=True)
                    present = cells[4].get_text(strip=True) if len(cells) > 4 else "0"
                    
                    # Validate date format (DD/MM/YYYY) and check if it's in future
                    try:
                        date_obj = datetime.strptime(date_str, '%d/%m/%Y')
                        today = datetime.now()
                        today.setHours(0, 0, 0, 0) if hasattr(today, 'setHours') else today.replace(hour=0, minute=0, second=0, microsecond=0)
                        
                        # Only include future dates
                        if date_obj.replace(hour=0, minute=0, second=0, microsecond=0) <= today:
                            continue
                    except:
                        continue
                    
                    if class_id and class_id.isdigit():
                        present_num = int(present) if present.isdigit() else 0
                        total_capacity = get_class_capacity(class_type, license_name, license_type)
                        
                        records.append({
                            'date': date_str,
                            'class_id': class_id,
                            'class_name': class_type,
                            'class_type': license_name,
                            'license_type': license_type,
                            'present_count': str(present_num),
                            'total_students': str(total_capacity)
                        })
        
        print(f"   ✅ Found {len(records)} future class(es)")
        return records
        
    except Exception as e:
        print(f"   ❌ Error scraping {license_type}: {e}")
        return []

def scrape_all_endpoints(driver):
    """Scrape all endpoints"""
    print("\n" + "=" * 60)
    print("📊 SCRAPING ALL ATTENDANCE DATA")
    print("=" * 60)
    
    all_data = {
        "kpp01": [],
        "vocational": {
            "e_hailing": [],
            "bas_mini": [],
            "gdl": []
        }
    }
    
    # Scrape KPP01
    kpp01_data = scrape_attendance_data(driver, ENDPOINTS["kpp01"]["url"], ENDPOINTS["kpp01"]["license_type"])
    all_data["kpp01"] = kpp01_data
    
    # Scrape Vocational - e-Hailing
    e_hailing_data = scrape_attendance_data(driver, ENDPOINTS["e_hailing"]["url"], ENDPOINTS["e_hailing"]["license_type"])
    all_data["vocational"]["e_hailing"] = e_hailing_data
    
    # Scrape Vocational - Bas Mini
    bas_mini_data = scrape_attendance_data(driver, ENDPOINTS["bas_mini"]["url"], ENDPOINTS["bas_mini"]["license_type"])
    all_data["vocational"]["bas_mini"] = bas_mini_data
    
    # Scrape Vocational - GDL
    gdl_data = scrape_attendance_data(driver, ENDPOINTS["gdl"]["url"], ENDPOINTS["gdl"]["license_type"])
    all_data["vocational"]["gdl"] = gdl_data
    
    return all_data

def save_data(all_data):
    """Save to JSON file with organized structure"""
    
    # Count total records
    kpp01_count = len(all_data.get("kpp01", []))
    e_hailing_count = len(all_data.get("vocational", {}).get("e_hailing", []))
    bas_mini_count = len(all_data.get("vocational", {}).get("bas_mini", []))
    gdl_count = len(all_data.get("vocational", {}).get("gdl", []))
    
    output = {
        'last_updated': datetime.now().isoformat(),
        'kpp01': all_data.get("kpp01", []),
        'vocational': all_data.get("vocational", {})
    }
    
    with open('attendance.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 60)
    print("💾 DATA SAVED TO attendance.json")
    print("=" * 60)
    print(f"KPP01:        {kpp01_count} future class(es)")
    print(f"e-Hailing:    {e_hailing_count} future class(es)")
    print(f"Bas Mini:     {bas_mini_count} future class(es)")
    print(f"GDL:          {gdl_count} future class(es)")
    print(f"─" * 60)
    print(f"TOTAL:        {kpp01_count + e_hailing_count + bas_mini_count + gdl_count} future class(es)")
    print("=" * 60)
    
    # Print detailed summary by license type
    if all_data.get("kpp01"):
        print("\n📋 KPP01 CLASSES:")
        print("-" * 60)
        current_date = None
        for record in all_data["kpp01"]:
            if record['date'] != current_date:
                current_date = record['date']
                print(f"📅 {record['date']}")
            print(f"   {record['class_type']} {record['class_name']} ({record['present_count']}/{record['total_students']})")
    
    vocational = all_data.get("vocational", {})
    
    if vocational.get("e_hailing"):
        print("\n🚕 E-HAILING CLASSES:")
        print("-" * 60)
        current_date = None
        for record in vocational["e_hailing"]:
            if record['date'] != current_date:
                current_date = record['date']
                print(f"📅 {record['date']}")
            print(f"   {record['class_name']} ({record['present_count']}/{record['total_students']})")
    
    if vocational.get("bas_mini"):
        print("\n🚌 BAS MINI CLASSES:")
        print("-" * 60)
        current_date = None
        for record in vocational["bas_mini"]:
            if record['date'] != current_date:
                current_date = record['date']
                print(f"📅 {record['date']}")
            print(f"   {record['class_name']} ({record['present_count']}/{record['total_students']})")
    
    if vocational.get("gdl"):
        print("\n🚚 GDL CLASSES:")
        print("-" * 60)
        current_date = None
        for record in vocational["gdl"]:
            if record['date'] != current_date:
                current_date = record['date']
                print(f"📅 {record['date']}")
            print(f"   {record['class_name']} ({record['present_count']}/{record['total_students']})")

def main():
    print("\n🚀 Driving School Attendance Scraper (Multi-Category)")
    print("=" * 60)
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
            print("\n✅ Login successful - ready to fetch all attendance data")
            all_data = scrape_all_endpoints(driver)
            save_data(all_data)
            
            total = (len(all_data.get("kpp01", [])) + 
                    len(all_data.get("vocational", {}).get("e_hailing", [])) +
                    len(all_data.get("vocational", {}).get("bas_mini", [])) +
                    len(all_data.get("vocational", {}).get("gdl", [])))
            
            print(f"\n✅ Successfully processed {total} total class records")
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
            print("\n🔚 Browser closed")

if __name__ == "__main__":
    main()
