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
    """Fetch vocational attendance for a specific date — race-free.

    Uses a single JS read (execute_script) to both wait for and extract rows,
    so there is no gap between the wait predicate and the parse predicate.
    """
    max_retries = 2
    for attempt in range(max_retries):
        try:
            formatted_date_input = search_date.strftime("%d/%m/%Y")
            day_name = search_date.strftime("%A")
            print(f"  🔍 Checking {formatted_date_input} ({day_name})...", end=" ", flush=True)

            driver.get(f"{BASE_URL}{url_path}")

            # Wait for the date field
            try:
                date_field = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.ID, "lessonDate"))
                )
            except Exception:
                print("date field error", end=" ")
                return []

            date_field.clear()
            date_field.send_keys(formatted_date_input)
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
                driver.find_element(By.ID, "mySearchButton").click()
            except Exception:
                try:
                    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
                except Exception:
                    print("no button", end=" ")
                    return []

            # === Single JS routine: wait until terminal, then extract rows ===
            # Returns:
            #   {"state": "rows",  "records": [...]}   -> parse succeeded
            #   {"state": "empty", "records": []}      -> authoritative no-rows
            #   {"state": "stale"|"none", "records": []} -> keep waiting
            JS_EXTRACT = r"""
            var target = arguments[0];
            var tbody = document.querySelector('#myClassListTable tbody');
            if (!tbody) return {state: 'none', records: []};

            var rows = tbody.querySelectorAll('tr');
            var sawEmpty = false;
            var sawOtherReal = false;
            var records = [];

            function norm(s) {
                // Strip ALL whitespace incl. NBSP (\u00A0)
                return (s || '').replace(/[\s\u00A0]+/g, '');
            }

            for (var i = 0; i < rows.length; i++) {
                var tds = rows[i].querySelectorAll('td');

                // Empty-state row
                if (tds.length === 1 && tds[0].getAttribute('colspan')) {
                    sawEmpty = true;
                    continue;
                }

                // Real data row needs >= 7 cells (Booking..Out)
                if (tds.length < 7) {
                    sawOtherReal = true;
                    continue;
                }
                sawOtherReal = true;

                var booking  = norm(tds[0].textContent);
                var process  = (tds[1].textContent || '').trim();
                var dtext    = norm(tds[2].textContent);
                var cname    = (tds[3].textContent || '').trim();
                var booked   = norm(tds[4].textContent);
                var incnt    = norm(tds[5].textContent);
                var outcnt   = norm(tds[6].textContent);

                if (!/^\d+$/.test(booking)) continue;
                if (!/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(dtext)) continue;
                if (dtext !== target) continue;

                records.push({
                    date: dtext,
                    class_id: booking,
                    class_code: process,
                    class_name: cname,
                    present_count: incnt || '0',
                    booked_count: booked || '0',
                    out_count: outcnt || '0'
                });
            }

            if (records.length > 0) {
                return {state: 'rows', records: records};
            }
            if (sawEmpty && !sawOtherReal) {
                return {state: 'empty', records: []};
            }
            // Either still loading, or rows exist for other dates
            return {state: 'stale', records: []};
            """

            # Poll the same JS until it returns rows/empty
            final = None
            try:
                def _poll(d):
                    nonlocal final
                    try:
                        r = d.execute_script(JS_EXTRACT, formatted_date_input)
                    except Exception:
                        return False
                    if r and r.get("state") in ("rows", "empty"):
                        final = r
                        return True
                    return False

                WebDriverWait(driver, 25, poll_frequency=0.4).until(_poll)
            except TimeoutException:
                try:
                    r = driver.execute_script(JS_EXTRACT, formatted_date_input)
                    state = (r or {}).get("state", "none")
                except Exception:
                    state = "none"
                print(f"table never resolved (state={state})", end=" ")
                try:
                    with open(f"debug_{search_date.strftime('%Y%m%d')}.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    driver.save_screenshot(f"debug_{search_date.strftime('%Y%m%d')}.png")
                    print("(saved debug_*.html/png)", end=" ")
                except Exception:
                    pass
                return []

            if final["state"] == "empty":
                print("📭 No classes")
                return []

            # === final["state"] == "rows": build records from JS output ===
            records = []
            for r in final["records"]:
                def to_int(s):
                    s = (s or "").strip()
                    return int(s) if s.isdigit() else 0

                records.append({
                    "date": r["date"],
                    "class_id": r["class_id"],
                    "class_code": r["class_code"],
                    "class_name": r["class_name"],
                    "present_count": str(to_int(r["present_count"])),
                    "booked_count": str(to_int(r["booked_count"])),
                    "out_count": str(to_int(r["out_count"])),
                    "total_students": str(VOCATIONAL_CAPACITY),
                })

            if records:
                print(f"✅ Found {len(records)} class(es)")
            else:
                # Should be truly unreachable now
                print(f"⚠️ BUG: JS returned 'rows' with 0 records")
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
                    booked    = int(record['booked_count'])
                    total_cap = int(record['total_students'])
    
                    # Parse date to show day name
                    try:
                        date_obj = datetime.strptime(record['date'], '%d/%m/%Y')
                        day_name = date_obj.strftime('%A')
                        date_display = f"{record['date']} ({day_name})"
                    except Exception:
                        date_display = record['date']
    
                    status = f"{booked}/{total_cap}"
                    if booked >= total_cap and total_cap > 0:
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
