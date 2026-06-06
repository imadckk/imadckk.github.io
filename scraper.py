import json
import os
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

# Get credentials from GitHub Secrets
USERNAME = os.environ.get('COMPANY_USERNAME')
PASSWORD = os.environ.get('COMPANY_PASSWORD')
BASE_URL = "http://adcdriving.dyndns.biz"

def setup_driver():
    """Setup Chrome driver for GitHub Actions"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in background
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0')
    
    # Try to find Chrome
    chrome_paths = [
        '/usr/bin/chromium-browser',
        '/usr/bin/google-chrome',
        '/usr/bin/chromium',
    ]
    
    for path in chrome_paths:
        if os.path.exists(path):
            options.binary_location = path
            break
    
    driver = webdriver.Chrome(options=options)
    return driver

def login_with_selenium(driver):
    """Login using Selenium - handles JavaScript properly"""
    print("🔐 Attempting login with Selenium...")
    
    try:
        # Navigate to login page
        driver.get(f"{BASE_URL}/star/User/Login")
        print(f"   Page loaded: {driver.title}")
        time.sleep(3)
        
        # Wait for username field to be present
        wait = WebDriverWait(driver, 10)
        
        # Find and fill username
        username_field = wait.until(EC.presence_of_element_located((By.ID, "UserName")))
        username_field.clear()
        username_field.send_keys(USERNAME)
        print("   ✅ Username entered")
        
        # Find and fill password
        password_field = driver.find_element(By.ID, "Password")
        password_field.clear()
        password_field.send_keys(PASSWORD)
        print("   ✅ Password entered")
        
        # Try multiple ways to submit
        try:
            # Method 1: Click login button
            login_button = driver.find_element(By.ID, "btnLogin")
            login_button.click()
            print("   Method 1: Clicked login button")
        except:
            try:
                # Method 2: Find by CSS selector
                login_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
                login_button.click()
                print("   Method 2: Clicked submit input")
            except:
                # Method 3: Press Enter
                password_field.send_keys(Keys.RETURN)
                print("   Method 3: Pressed Enter")
        
        # Wait for redirect or page change
        time.sleep(5)
        
        # Check if login was successful
        current_url = driver.current_url
        print(f"   Current URL after login: {current_url}")
        
        # Check for success indicators
        page_source = driver.page_source.lower()
        
        if "attendance" in current_url.lower():
            print("✅ Login successful! (redirected to attendance)")
            return True
        elif "logout" in page_source:
            print("✅ Login successful! (logout found)")
            return True
        elif "dashboard" in page_source:
            print("✅ Login successful! (dashboard found)")
            return True
        elif "kpp" in page_source:
            print("✅ Login successful! (KPP page found)")
            return True
        elif "login" not in current_url.lower():
            print("✅ Login successful! (redirected)")
            return True
        else:
            print("❌ Login failed - still on login page")
            # Save screenshot for debugging
            driver.save_screenshot("login_failed.png")
            print("   Screenshot saved as login_failed.png")
            return False
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        driver.save_screenshot("login_error.png")
        return False

def get_attendance_for_date(driver, search_date):
    """Fetch attendance data for a specific date"""
    try:
        formatted_date = search_date.strftime("%m/%d/%Y")
        print(f"  🔍 Checking {formatted_date}...", end=" ", flush=True)
        
        # Navigate to attendance page
        driver.get(f"{BASE_URL}/star/AttendanceRecord/Kpp")
        time.sleep(2)
        
        # Wait for page to load
        wait = WebDriverWait(driver, 10)
        
        # Find date field and set value
        try:
            date_field = wait.until(EC.presence_of_element_located((By.ID, "lessonDate")))
            date_field.clear()
            # Use JavaScript to set date (more reliable)
            driver.execute_script(f"arguments[0].value = '{formatted_date}';", date_field)
            print("date set", end=" ")
        except Exception as e:
            print(f"date field error", end=" ")
        
        # Find and click search button
        try:
            search_button = driver.find_element(By.ID, "mySearchButton")
            driver.execute_script("arguments[0].click();", search_button)
            print("search clicked", end=" ")
        except:
            try:
                search_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                driver.execute_script("arguments[0].click();", search_button)
                print("search clicked", end=" ")
            except:
                print("no search button", end=" ")
        
        # Wait for results to load
        time.sleep(3)
        
        # Parse the page source
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        records = []
        
        # Find all tables with attendance data
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
                    date = cells[2].get_text(strip=True)
                    class_type = cells[3].get_text(strip=True)
                    present = cells[4].get_text(strip=True) if len(cells) > 4 else "0"
                    absent = cells[5].get_text(strip=True) if len(cells) > 5 else "0"
                    late = cells[6].get_text(strip=True) if len(cells) > 6 else "0"
                    
                    # Only add if it looks like a valid record
                    if student_id and student_id.isdigit() and len(student_id) > 3:
                        records.append({
                            'date': date,
                            'class_id': student_id,
                            'class_name': class_name,
                            'class_type': class_type,
                            'present_count': present,
                            'absent_count': absent,
                            'late_count': late
                        })
        
        if records:
            print(f"✅ Found {len(records)} class(es)")
        else:
            print(f"📭 No classes")
        
        return records
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def get_month_attendance(driver, year, month):
    """Fetch attendance for entire month"""
    print(f"\n📅 Fetching attendance for {datetime(year, month, 1).strftime('%B')} {year}")
    print("=" * 50)
    
    # Get days in month
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    num_days = (next_month - datetime(year, month, 1)).days
    
    all_records = []
    
    # For GitHub Actions, check all days but be efficient
    print(f"Checking all {num_days} days...")
    
    for day in range(1, num_days + 1):
        current_date = datetime(year, month, day)
        records = get_attendance_for_date(driver, current_date)
        all_records.extend(records)
        time.sleep(1)  # Be nice to the server
    
    return all_records

def get_current_month_attendance(driver):
    """Fetch attendance for current month"""
    now = datetime.now()
    return get_month_attendance(driver, now.year, now.month)

def save_data(attendance_records):
    """Save to JSON file"""
    simplified_data = []
    
    for record in attendance_records:
        present = int(record['present_count']) if record['present_count'].isdigit() else 0
        absent = int(record['absent_count']) if record['absent_count'].isdigit() else 0
        late = int(record['late_count']) if record['late_count'].isdigit() else 0
        total = present + absent + late
        
        simplified_record = {
            'date': record['date'],
            'class_name': record['class_name'],
            'class_type': record['class_type'],
            'present_count': str(present),
            'total_students': str(total)
        }
        simplified_data.append(simplified_record)
    
    if simplified_data:
        # Sort by date
        simplified_data.sort(key=lambda x: datetime.strptime(x['date'], '%m/%d/%Y') if x['date'] else datetime.min)
    
    output = {
        'last_updated': datetime.now().isoformat(),
        'attendance_summary': simplified_data
    }
    
    with open('attendance.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Saved {len(simplified_data)} class records to attendance.json")
    
    if simplified_data:
        print("\n📊 SUMMARY:")
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
