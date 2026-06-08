import json
import os
import time
import re
from datetime import datetime, timedelta
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

def get_vocational_attendance_for_date(driver, search_date, url_path):
    """Fetch vocational attendance for a specific date"""
    try:
        formatted_date_input = search_date.strftime("%d/%m/%Y")
        print(f"  🔍 Checking {formatted_date_input}...", end=" ", flush=True)
        
        # Navigate to the page
        driver.get(f"{BASE_URL}{url_path}")
        time.sleep(2)
        
        # Find and fill the date field
        try:
            date_field = driver.find_element(By.ID, "lessonDate")
            date_field.clear()
            date_field.send_keys(formatted_date_input)
        except Exception as e:
            print(f"date field error", end=" ")
            return []
        
        # Click search button
        try:
            search_button = driver.find_element(By.ID, "mySearchButton")
            search_button.click()
        except:
            try:
                search_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                search_button.click()
            except:
                print("no button", end=" ")
                return []
        
        time.sleep(3)
        
        # Parse the results
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        records = []
        
        # Find all tables
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                if row.find('th'):
                    continue
                
                cells = row.find_all('td')
                if len(cells) >= 5:
                    class_id = cells[0].get_text(strip=True) if len(cells) > 0 else ""
                    class_code = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    date_str = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    class_name = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                    present_count = cells[4].get_text(strip=True) if len(cells) > 4 else "0"
                    
                    # Skip if no valid class ID
                    if not class_id or not class_id.isdigit():
                        continue
                    
                    # Validate date format (should be DD/MM/YYYY)
                    if not re.match(r'\d{2}/\d{2}/\d{4}', date_str):
                        continue
                    
                    # Parse present count
                    try:
                        present_num = int(present_count) if present_count.isdigit() else 0
                    except:
                        present_num = 0
                    
                    records.append({
                        'date': date_str,
                        'class_id': class_id,
                        'class_name': class_name,
                        'class_code': class_code,
                        'present_count': str(present_num),
                        'total_students': str(VOCATIONAL_CAPACITY)
                    })
        
        if records:
            print(f"✅ Found {len(records)} class(es)")
        else:
            print(f"📭 No classes")
        
        return records
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def get_remaining_days_in_month(driver, url_path):
    """Fetch attendance for remaining days in current month only"""
    now = datetime.now()
    
    # Calculate last day of current month
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1)
    else:
        next_month = datetime(now.year, now.month + 1, 1)
    last_day = next_month - timedelta(days=1)
    
    days_remaining = (last_day - now).days + 1  # +1 to include today
    
    print(f"\n📅 Checking from today ({now.strftime('%d/%m/%Y')}) until end of month ({last_day.strftime('%d/%m/%Y')})")
    print(f"   Total days to check: {days_remaining}")
    
    all_records = []
    
    # Check from today until the end of the month
    for day_offset in range(days_remaining):
        current_date = now + timedelta(days=day_offset)
        records = get_vocational_attendance_for_date(driver, current_date, url_path)
        all_records.extend(records)
        time.sleep(1)  # Be nice to the server
    
    return all_records

def categorize_vocational_records(records):
    """Categorize records into e-Hailing, Bas Mini, or GDL based on class name"""
    categorized = {
        'e-Hailing': [],
        'Bas Mini': [],
        'GDL': []
    }
    
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for record in records:
        class_name_upper = record['class_name'].upper()
        class_code_upper = record['class_code'].upper()
        
        # Determine category based on class name
        # e-Hailing detection
        if "E-HAILING" in class_name_upper or "E HAILING" in class_name_upper:
            category = 'e-Hailing'
        # Bas Mini / PSV detection  
        elif "PSV" in class_name_upper or "BAS MINI" in class_name_upper or "BAS" in class_name_upper:
            category = 'Bas Mini'
        # GDL detection
        elif "GDL" in class_name_upper:
            category = 'GDL'
        else:
            # Try to determine from class code
            if "PSV" in class_code_upper:
                category = 'Bas Mini'
            elif "GDL" in class_code_upper:
                category = 'GDL'
            else:
                # Skip unknown categories
                continue
        
        # Filter to only future dates (including today)
        try:
            date_obj = datetime.strptime(record['date'], '%d/%m/%Y')
            if date_obj >= today:
                categorized[category].append(record)
        except Exception as e:
            continue
    
    return categorized

def save_vocational_data(categorized_data):
    """Save vocational data to JSON file"""
    # Sort each category by date
    for category in categorized_data:
        categorized_data[category].sort(key=lambda x: datetime.strptime(x['date'], '%d/%m/%Y'))
    
    output = {
        'last_updated': datetime.now().isoformat(),
        'vocational_summary': categorized_data
    }
    
    with open('vocational.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Saved vocational data to vocational.json")
    
    # Print summary
    print("\n📊 VOCATIONAL SUMMARY:")
    print("=" * 50)
    total = 0
    for category in ['e-Hailing', 'Bas Mini', 'GDL']:
        count = len(categorized_data[category])
        total += count
        if count > 0:
            print(f"\n🚗 {category.upper()}: {count} class(es)")
            for record in categorized_data[category]:
                present = int(record['present_count'])
                total_cap = int(record['total_students'])
                status = f"{present}/{total_cap}"
                if present == total_cap and total_cap > 0:
                    status += " 🔴 FULL"
                print(f"   📅 {record['date']} - {record['class_name']}: {status}")
    
    if total == 0:
        print("\n📭 No upcoming vocational classes found")

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
    all_records = []
    
    try:
        print("📱 Setting up browser...")
        driver = setup_driver()
        print("✅ Browser ready")
        
        if login_with_selenium(driver):
            print("\n✅ Ready to fetch vocational attendance data")
            
            # Scrape PSV II (e-Hailing and Bas Mini classes)
            print("\n" + "="*50)
            print("📌 SCRAPING PSV II (e-Hailing & Bas Mini)")
            print("="*50)
            psv_records = get_remaining_days_in_month(driver, "/star/AttendanceRecord/Psv2")
            print(f"\n   Total records from PSV II: {len(psv_records)}")
            all_records.extend(psv_records)
            
            # Scrape GDL II (GDL classes)
            print("\n" + "="*50)
            print("📌 SCRAPING GDL II (GDL)")
            print("="*50)
            gdl_records = get_remaining_days_in_month(driver, "/star/AttendanceRecord/Gdl2")
            print(f"\n   Total records from GDL II: {len(gdl_records)}")
            all_records.extend(gdl_records)
            
            print(f"\n📊 Total records found: {len(all_records)}")
            
            if all_records:
                # Categorize the records
                categorized_data = categorize_vocational_records(all_records)
                save_vocational_data(categorized_data)
                
                total_count = sum(len(v) for v in categorized_data.values())
                print(f"\n✅ Successfully processed {total_count} vocational class records")
                print(f"   - e-Hailing: {len(categorized_data['e-Hailing'])}")
                print(f"   - Bas Mini: {len(categorized_data['Bas Mini'])}")
                print(f"   - GDL: {len(categorized_data['GDL'])}")
            else:
                print("\n⚠️ No vocational records found")
                empty_data = {
                    'e-Hailing': [],
                    'Bas Mini': [],
                    'GDL': []
                }
                save_vocational_data(empty_data)
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
