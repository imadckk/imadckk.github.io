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
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import sys

# Get credentials from GitHub Secrets
USERNAME = os.environ.get('COMPANY_USERNAME')
PASSWORD = os.environ.get('COMPANY_PASSWORD')
BASE_URL = "http://adcdriving.dyndns.biz"

# Class capacity for vocational (all 50)
VOCATIONAL_CAPACITY = 50

# Configuration
MONTHS_AHEAD = 1  # Check current month + 1 month ahead
WEEKDAYS_ONLY = True  # Only check Monday-Friday (vocational classes on weekdays)

def is_weekday(date):
    """Check if date is Monday-Friday (0-4, where Monday=0, Sunday=6)"""
    return date.weekday() < 5  # 0-4 are weekdays

def get_dates_to_check():
    """
    Get all weekdays from today through X months ahead
    Returns list of dates to check
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Calculate end date (first day of month X months ahead, minus 1 day)
    end_date = today
    for _ in range(MONTHS_AHEAD):
        # Move to next month
        if end_date.month == 12:
            end_date = end_date.replace(year=end_date.year + 1, month=1)
        else:
            end_date = end_date.replace(month=end_date.month + 1)
    
    # Go to the last day of that month
    if end_date.month == 12:
        end_date = datetime(end_date.year, 12, 31)
    else:
        end_date = datetime(end_date.year, end_date.month + 1, 1) - timedelta(days=1)
    
    # Generate all weekdays to check
    dates_to_check = []
    current_date = today
    
    while current_date <= end_date:
        if WEEKDAYS_ONLY and is_weekday(current_date):
            dates_to_check.append(current_date)
        current_date += timedelta(days=1)
    
    return dates_to_check, today, end_date

def setup_driver():
    """Setup Chrome driver - FIXED for HTTP-only site (no HTTPS upgrade)."""
    options = webdriver.ChromeOptions()

    # Critical for GitHub Actions
    options.add_argument('--headless=new')          # modern headless, behaves like real Chrome
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--lang=en-US,en')

    # === CRITICAL: stop Chrome from upgrading HTTP → HTTPS ===
    # The site is HTTP-only; without these, Chrome tries https:// and fails
    # with net::ERR_BLOCKED_BY_CLIENT, leaving an empty page.
    options.add_argument(
        '--disable-features=HttpsUpgrades,HttpsFirstBalancedModeAutoEnable,HttpsFirstModeV2'
    )
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--ignore-certificate-errors')

    # Realistic UA + anti-automation
    options.add_argument(
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)

    # === CRITICAL: prefs that disable HTTPS-first/upgrade at the profile level ===
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "https_upgrades_enabled": False,     # <-- the key pref
        "https_first_mode_enabled": False,
    })

    # Network logging (useful for debugging; harmless in production)
    options.set_capability("goog:loggingPrefs", {"browser": "ALL", "performance": "ALL"})

    # Note: removed options.binary_location = '/usr/bin/chromium-browser'
    # That path often doesn't exist on GitHub Actions Ubuntu runners, which
    # ship Google Chrome at /usr/bin/google-chrome or via the webdriver-manager
    # downloaded Chrome. Let webdriver-manager pick the binary.

    try:
        print("   Installing ChromeDriver...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(45)

        # Patch navigator.webdriver and friends
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                window.chrome = window.chrome || {runtime: {}};
            """}
        )

        print("   ✅ ChromeDriver initialized successfully")
        return driver
    except Exception as e:
        print(f"   ⚠️ WebDriver-manager failed: {e}")
        try:
            print("   Trying system ChromeDriver...")
            service = Service('/usr/bin/chromedriver')
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(45)
            print("   ✅ System ChromeDriver initialized successfully")
            return driver
        except Exception as e2:
            print(f"   ❌ All driver initialization failed: {e2}")
            raise

def login_with_selenium(driver):
    """Login using Selenium with improved error handling"""
    print("🔐 Attempting login with Selenium...")
    
    try:
        # Set page load timeout
        driver.set_page_load_timeout(30)
        
        print(f"   Navigating to {BASE_URL}/star/User/Login...")
        driver.get(f"{BASE_URL}/star/User/Login")
        print(f"   Page loaded: {driver.title}")

        try:
            perf = driver.get_log("performance")
            for entry in perf:
                try:
                    msg = json.loads(entry["message"])["message"]
                except Exception:
                    continue
                if msg.get("method") == "Network.requestWillBeSent":
                    url = msg["params"]["request"]["url"]
                    if "User/Login" in url:
                        print(f"   🌐 Navigated to: {url}")
                elif msg.get("method") == "Network.loadingFailed":
                    params = msg["params"]
                    print(f"   ❌ FAIL {params.get('errorText')}")
        except Exception:
            pass
        
        # Wait for page to be ready
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "UserName"))
        )
        
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
        
        # Wait for navigation to complete
        time.sleep(3)
        
        # Check if login was successful
        current_url = driver.current_url
        print(f"   Current URL: {current_url}")
        
        if "login" not in current_url.lower():
            print("✅ Login successful!")
            return True
        else:
            print("❌ Login failed - still on login page")
            # Take screenshot for debugging
            try:
                driver.save_screenshot('login_failed.png')
                print("   📸 Screenshot saved: login_failed.png")
            except:
                pass
            return False
            
    except TimeoutException as e:
        print(f"❌ Login timeout: {e}")
        return False
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False

def get_vocational_attendance_for_date(driver, search_date, url_path):
    """Fetch vocational attendance for a specific date with date-aware AJAX wait."""
    max_retries = 2
    for attempt in range(max_retries):
        try:
            formatted_date_input = search_date.strftime("%d/%m/%Y")
            day_name = search_date.strftime("%A")
            print(f"  🔍 Checking {formatted_date_input} ({day_name})...", end=" ", flush=True)

            # Navigate to the page
            driver.get(f"{BASE_URL}{url_path}")

            # Wait for the date field
            try:
                date_field = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.ID, "lessonDate"))
                )
            except Exception:
                print("date field error", end=" ")
                return []

            # Fill the date (works whether it's a native input or a picker)
            date_field.clear()
            date_field.send_keys(formatted_date_input)

            # Some ASP.NET MVC date pickers only commit on blur/change.
            try:
                date_field.send_keys(Keys.TAB)
            except Exception:
                pass
            try:
                driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                    date_field,
                )
            except Exception:
                pass

            # Click search
            try:
                search_button = driver.find_element(By.ID, "mySearchButton")
                search_button.click()
            except Exception:
                try:
                    search_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                    search_button.click()
                except Exception:
                    print("no button", end=" ")
                    return []

            # === Date-aware wait helpers (closures over formatted_date_input) ===
            def table_has_rows_for_date(d):
                """True only when tbody has a real row whose date cell == target."""
                return d.execute_script("""
                    var target = arguments[0];
                    var tbody = document.querySelector('#myClassListTable tbody');
                    if (!tbody) return false;
                    var rows = tbody.querySelectorAll('tr');
                    if (rows.length === 0) return false;
                    for (var i = 0; i < rows.length; i++) {
                        var tds = rows[i].querySelectorAll('td');
                        // Skip empty-state row
                        if (tds.length === 1 && tds[0].getAttribute('colspan')) continue;
                        for (var j = 0; j < tds.length; j++) {
                            var t = (tds[j].textContent || '').replace(/\\s+/g, '');
                            if (t === target) return true;
                        }
                    }
                    return false;
                """, formatted_date_input)

            def table_shows_empty_state(d):
                """True only when DataTables has rendered its 'No data' row."""
                return d.execute_script("""
                    var tbody = document.querySelector('#myClassListTable tbody');
                    if (!tbody) return false;
                    var rows = tbody.querySelectorAll('tr');
                    if (rows.length === 0) return false;
                    for (var i = 0; i < rows.length; i++) {
                        var tds = rows[i].querySelectorAll('td');
                        if (tds.length === 1 && tds[0].getAttribute('colspan')) return true;
                    }
                    return false;
                """)

            # Wait for AJAX to actually replace the table for THIS date
            try:
                WebDriverWait(driver, 25).until(
                    lambda d: table_has_rows_for_date(d) or table_shows_empty_state(d)
                )
            except TimeoutException:
                print("table never populated (no rows or empty-state)", end=" ")
                try:
                    with open(f"debug_{search_date.strftime('%Y%m%d')}.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    driver.save_screenshot(f"debug_{search_date.strftime('%Y%m%d')}.png")
                    print("(saved debug_*.html/png)", end=" ")
                except Exception:
                    pass
                return []

            # Settle time so DataTables finishes rendering the matched rows
            time.sleep(0.4)

            # === Parse the populated table ===
            soup = BeautifulSoup(driver.page_source, "html.parser")
            records = []

            table = soup.find("table", id="myClassListTable")
            tables = [table] if table else soup.find_all("table")

            for tbl in tables:
                body = tbl.find("tbody")
                if not body:
                    continue
                for row in body.find_all("tr"):
                    cells = row.find_all("td")
                    # Need Booking ID..Out = 7 columns (Detail is optional 8th)
                    if len(cells) < 7:
                        continue

                    booking_id  = cells[0].get_text(strip=True)
                    process     = cells[1].get_text(strip=True)
                    date_str    = cells[2].get_text(strip=True)
                    class_name  = cells[3].get_text(strip=True)
                    booking_cnt = cells[4].get_text(strip=True)
                    in_cnt      = cells[5].get_text(strip=True)
                    out_cnt     = cells[6].get_text(strip=True)

                    # Normalize & validate
                    date_str_clean = re.sub(r"\s+", "", date_str)
                    if not booking_id or not booking_id.isdigit():
                        continue
                    if not re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", date_str_clean):
                        continue
                    # Defensive: only accept rows for the date we searched
                    if date_str_clean != formatted_date_input:
                        continue

                    def to_int(s):
                        s = (s or "").strip()
                        return int(s) if s.isdigit() else 0

                    records.append({
                        "date": date_str_clean,
                        "class_id": booking_id,
                        "class_code": process,            # "PSV II" / "GDL II"
                        "class_name": class_name,         # "E-hailing ll" etc.
                        "present_count": str(to_int(in_cnt)),      # In (present)
                        "booked_count": str(to_int(booking_cnt)),  # Booking
                        "out_count": str(to_int(out_cnt)),
                        "total_students": str(VOCATIONAL_CAPACITY),
                    })

            if records:
                print(f"✅ Found {len(records)} class(es)")
            else:
                # The wait matched "rows exist for this date" but parse dropped them
                # -> would indicate a real regression worth investigating
                print(f"⚠️ Wait matched but parse yielded 0 (check debug)")
                try:
                    with open(f"debug_parse_{search_date.strftime('%Y%m%d')}.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                except Exception:
                    pass
            return records

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Attempt {attempt + 1} failed ({e}), retrying...")
                time.sleep(2)
            else:
                print(f"❌ Error: {e}")
                return []

def get_vocational_attendance_for_range(driver, url_path, page_name):
    """Fetch vocational attendance for all configured dates (weekdays only, 1 month ahead)"""
    dates_to_check, start_date, end_date = get_dates_to_check()
    
    print(f"\n📅 {page_name}")
    print(f"   Checking from {start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')}")
    print(f"   Total weekdays to check: {len(dates_to_check)}")
    print("-" * 50)
    
    all_records = []
    
    for i, date in enumerate(dates_to_check):
        records = get_vocational_attendance_for_date(driver, date, url_path)
        all_records.extend(records)
        
        # Add delay between requests (increased for reliability)
        if i < len(dates_to_check) - 1:
            time.sleep(2)
    
    print(f"\n   Total records found: {len(all_records)}")
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
        'date_range_checked': {
            'from': datetime.now().strftime('%d/%m/%Y'),
            'months_ahead': MONTHS_AHEAD,
            'weekdays_only': WEEKDAYS_ONLY
        },
        'vocational_summary': categorized_data
    }
    
    with open('vocational.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Saved vocational data to vocational.json")
    
    # Print summary
    print("\n📊 VOCATIONAL SUMMARY (Weekdays Only, 1 Month Ahead):")
    print("=" * 60)
    total = 0
    for category in ['e-Hailing', 'Bas Mini', 'GDL']:
        count = len(categorized_data[category])
        total += count
        if count > 0:
            print(f"\n🚗 {category.upper()}: {count} class(es)")
            for record in categorized_data[category]:
                present = int(record['present_count'])
                total_cap = int(record['total_students'])
                # Parse date to show day name
                try:
                    date_obj = datetime.strptime(record['date'], '%d/%m/%Y')
                    day_name = date_obj.strftime('%A')
                    date_display = f"{record['date']} ({day_name})"
                except:
                    date_display = record['date']
                
                status = f"{present}/{total_cap}"
                if present == total_cap and total_cap > 0:
                    status += " 🔴 FULL"
                print(f"   📅 {date_display} - {record['class_name']}: {status}")
    
    if total == 0:
        print("\n📭 No upcoming vocational classes found in the next month")

def main():
    print("🚀 Vocational Attendance Scraper (Weekdays Only + 1 Month Ahead)")
    print("=" * 60)
    print(f"Username configured: {'Yes' if USERNAME else 'No'}")
    print(f"Password configured: {'Yes' if PASSWORD else 'No'}")
    print(f"Configuration: {MONTHS_AHEAD} month(s) ahead, Weekdays only")
    print()
    
    if not USERNAME or not PASSWORD:
        print("❌ Missing credentials!")
        sys.exit(1)
    
    driver = None
    all_records = []
    
    try:
        print("📱 Setting up browser...")
        driver = setup_driver()
        print("✅ Browser ready")
        
        if login_with_selenium(driver):
            print("\n✅ Ready to fetch vocational attendance data")
            
            # Scrape PSV II (e-Hailing and Bas Mini classes)
            print("\n" + "="*60)
            print("📌 SCRAPING PSV II (e-Hailing & Bas Mini)")
            print("="*60)
            psv_records = get_vocational_attendance_for_range(driver, "/star/AttendanceRecord/Psv2", "PSV II")
            all_records.extend(psv_records)
            
            # Scrape GDL II (GDL classes)
            print("\n" + "="*60)
            print("📌 SCRAPING GDL II (GDL)")
            print("="*60)
            gdl_records = get_vocational_attendance_for_range(driver, "/star/AttendanceRecord/Gdl2", "GDL II")
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
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if driver:
            try:
                driver.quit()
                print("🔚 Browser closed")
            except:
                pass

if __name__ == "__main__":
    main()
