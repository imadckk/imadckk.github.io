import json
import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# Get credentials from GitHub Secrets
USERNAME = os.environ.get('COMPANY_USERNAME')
PASSWORD = os.environ.get('COMPANY_PASSWORD')
BASE_URL = "http://adcdriving.dyndns.biz"

def setup_driver():
    """Setup Chrome driver for GitHub Actions"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    driver = webdriver.Chrome(options=options)
    return driver

def login_with_selenium(driver):
    """Login using Selenium"""
    print("🔐 Attempting login with Selenium...")
    
    try:
        driver.get(f"{BASE_URL}/star/User/Login")
        print(f"   Page loaded: {driver.title}")
        time.sleep(3)
        
        # Find and fill username
        username_field = driver.find_element(By.ID, "UserName")
        username_field.clear()
        username_field.send_keys(USERNAME)
        print("   ✅ Username entered")
        
        # Find and fill password
        password_field = driver.find_element(By.ID, "Password")
        password_field.clear()
        password_field.send_keys(PASSWORD)
        print("   ✅ Password entered")
        
        # Click login button
        login_button = driver.find_element(By.ID, "btnLogin")
        login_button.click()
        print("   ✅ Clicked login button")
        
        # Wait for redirect
        time.sleep(5)
        
        # Check if login successful
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

def get_attendance_for_date(driver, search_date):
    """Fetch attendance for a specific date"""
    try:
        # Use DD/MM/YYYY format for input (matching the system)
        formatted_date_input = search_date.strftime("%d/%m/%Y")
        print(f"  🔍 Checking {formatted_date_input}...", end=" ", flush=True)
        
        # Navigate to attendance page
        driver.get(f"{BASE_URL}/star/AttendanceRecord/Kpp")
        time.sleep(2)
        
        # Find and set date field
        try:
            date_field = driver.find_element(By.ID, "lessonDate")
            date_field.clear()
            date_field.send_keys(formatted_date_input)
        except:
            print("date field error", end=" ")
            return []
        
        # Find and click search button
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
        
        # Wait for results
        time.sleep(3)
        
        # Parse the page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        records = []
        
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
                    student_id = cells[0].get_text(strip=True)
                    class_name = cells[1].get_text(strip=True)
                    date_str = cells[2].get_text(strip=True)
                    class_type = cells[3].get_text(strip=True)
                    present = cells[4].get_text(strip=True) if len(cells) > 4 else "0"
                    absent = cells[5].get_text(strip=True) if len(cells) > 5 else "0"
                    late = cells[6].get_text(strip=True) if len(cells) > 6 else "0"
                    
                    if student_id and student_id.isdigit():
                        # Calculate total students
                        total = int(present) + int(absent) + int(late) if present.isdigit() and absent.isdigit() and late.isdigit() else 0
                        
                        # Store date as-is (already in DD/MM/YYYY format from the system)
                        records.append({
                            'date': date_str,
                            'class_id': student_id,
                            'class_name': class_name,
                            'class_type': class_type,
                            'present_count': present,
                            'total_students': str(total) if total > 0 else "0"
                        })
        
        if records:
            print(f"✅ Found {len(records)} class(es)")
        else:
            print(f"📭 No classes")
        
        return records
        
    except Exception as e:
        print(f"❌ Error")
        return []

def get_month_attendance(driver):
    """Fetch attendance for current month"""
    now = datetime.now()
    print(f"\n📅 Fetching attendance for {now.strftime('%B %Y')}")
    print("=" * 50)
    
    # Get days in current month
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1)
    else:
        next_month = datetime(now.year, now.month + 1, 1)
    num_days = (next_month - datetime(now.year, now.month, 1)).days
    
    all_records = []
    
    # Check all days in the month
    for day in range(1, num_days + 1):
        current_date = datetime(now.year, now.month, day)
        records = get_attendance_for_date(driver, current_date)
        all_records.extend(records)
        time.sleep(1)  # Be nice to the server
    
    return all_records

def get_current_month_attendance(driver):
    """Fetch attendance for current month"""
    return get_month_attendance(driver)

def save_data(attendance_records):
    """Save to JSON file"""
    simplified_data = []
    
    for record in attendance_records:
        simplified_record = {
            'date': record['date'],
            'class_name': record['class_name'],
            'class_type': record['class_type'],
            'present_count': record['present_count'],
            'total_students': record['total_students']
        }
        simplified_data.append(simplified_record)
    
    # Sort by date (parse DD/MM/YYYY format)
    def parse_date(date_str):
        try:
            # Try DD/MM/YYYY format
            return datetime.strptime(date_str, '%d/%m/%Y')
        except:
            try:
                # Try MM/DD/YYYY format as fallback
                return datetime.strptime(date_str, '%m/%d/%Y')
            except:
                return datetime.min
    
    if simplified_data:
        simplified_data.sort(key=lambda x: parse_date(x['date']))
    
    output = {
        'last_updated': datetime.now().isoformat(),
        'attendance_summary': simplified_data
    }
    
    with open('attendance.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Saved {len(simplified_data)} class records to attendance.json")
    
    if simplified_data:
        print("\n📊 ATTENDANCE SUMMARY:")
        print("=" * 50)
        current_date = None
        for record in simplified_data:
            if record['date'] != current_date:
                current_date = record['date']
                print(f"\n📅 {record['date']}")
            print(f"   {record['class_type']} {record['class_name']} ({record['present_count']}/{record['total_students']})")

def main():
    print("🚀 Driving School Attendance Scraper (Selenium Version)")
    print("=" * 50)
    print(f"Username configured: {'Yes' if USERNAME else 'No'}")
    print(f"Password configured: {'Yes' if PASSWORD else 'No'}")
    print()
    
    if not USERNAME or not PASSWORD:
        print("❌ Missing credentials!")
        print("Please set COMPANY_USERNAME and COMPANY_PASSWORD in GitHub Secrets")
        exit(1)
    
    driver = None
    try:
        print("📱 Setting up browser...")
        driver = setup_driver()
        print("✅ Browser ready")
        
        if login_with_selenium(driver):
            print("\n✅ Ready to fetch attendance data")
            attendance_data = get_current_month_attendance(driver)
            
            if attendance_data:
                save_data(attendance_data)
                print(f"\n✅ Successfully processed {len(attendance_data)} class records")
            else:
                print("\n⚠️ No attendance records found for this month")
                output = {
                    'last_updated': datetime.now().isoformat(),
                    'attendance_summary': []
                }
                with open('attendance.json', 'w') as f:
                    json.dump(output, f, indent=2)
        else:
            print("❌ Login failed - cannot proceed")
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
