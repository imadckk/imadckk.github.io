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

# Class capacity mapping (you can adjust these values)
# Format: "class_name_keyword": capacity
CLASS_CAPACITY = {
    "KPP01": 50,
    "KPP02": 50,
    "KPP03": 50,
    "KPP04": 50,
    "default": 50  # Default capacity if not found
}

def is_weekend(date):
    """Check if date is Saturday (5) or Sunday (6)"""
    # Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
    return date.weekday() in [5, 6]

def get_weekend_dates(start_date, end_date):
    """Get all weekend dates between start_date and end_date (inclusive)"""
    weekend_dates = []
    current_date = start_date
    
    while current_date <= end_date:
        if is_weekend(current_date):
            weekend_dates.append(current_date)
        current_date += timedelta(days=1)
    
    return weekend_dates

def get_upcoming_weekends(months_ahead=1):
    """
    Get all weekend dates from current date through next X months
    Returns list of dates to check
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Calculate end date (first day of month X months ahead)
    end_date = today
    for _ in range(months_ahead):
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
    
    weekend_dates = get_weekend_dates(today, end_date)
    
    print(f"📅 Found {len(weekend_dates)} weekend dates to check:")
    print(f"   From: {today.strftime('%Y-%m-%d')}")
    print(f"   To: {end_date.strftime('%Y-%m-%d')}")
    
    # Show first few dates as preview
    for i, date in enumerate(weekend_dates[:5]):
        print(f"   {date.strftime('%Y-%m-%d')} ({date.strftime('%A')})")
    if len(weekend_dates) > 5:
        print(f"   ... and {len(weekend_dates) - 5} more")
    
    return weekend_dates


def setup_driver():
    """Setup Chrome driver with a realistic fingerprint and modern headless mode."""
    options = webdriver.ChromeOptions()

    # Use NEW headless mode (Chrome 109+) — behaves like real Chrome
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--lang=en-US,en')

    # Prevent Chrome from trying HTTPS upgrades on an HTTP-only site
    options.add_argument('--disable-features=HttpsUpgrades,HttpsFirstModeV2')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--ignore-certificate-errors')

    # Realistic UA
    options.add_argument(
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )

    # Anti-automation-detection
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
    })

    # Log Chrome's network to a file so we can see redirects/errors
    options.set_capability("goog:loggingPrefs", {"browser": "ALL", "performance": "ALL"})

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(45)

    # Patch navigator.webdriver + related fingerprint properties
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                window.chrome = window.chrome || {runtime: {}};
            """
        },
    )
    return driver


def debug_page(driver):
    """
    Dump page structure to diagnose missing elements.
    Saves debug_page.html and debug_page.png for offline inspection.
    """
    print("\n🔬 Running page diagnostic...")

    try:
        driver.get(f"{BASE_URL}/star/User/Login")

        # Wait for full document load
        try:
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except Exception as e:
            print(f"   ⚠️ readyState wait timed out: {e}")

        print("=== DEBUG DUMP ===")
        print(f"Title: {driver.title!r}")
        print(f"URL: {driver.current_url}")
        source = driver.page_source
        print(f"Source length: {len(source)}")

        # Save page source for offline inspection
        try:
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(source)
            print("   💾 Saved debug_page.html")
        except Exception as e:
            print(f"   ⚠️ Could not save debug_page.html: {e}")

        # Save screenshot
        try:
            driver.save_screenshot("debug_page.png")
            print("   💾 Saved debug_page.png")
        except Exception as e:
            print(f"   ⚠️ Could not save debug_page.png: {e}")

        # Count common elements
        for tag in ["input", "form", "iframe", "button", "select", "a"]:
            try:
                els = driver.find_elements(By.TAG_NAME, tag)
                print(f"  <{tag}>: {len(els)} found")
                for e in els[:10]:
                    try:
                        eid = e.get_attribute('id')
                        ename = e.get_attribute('name')
                        etype = e.get_attribute('type')
                        etext = (e.text or "")[:40].replace("\n", " ")
                        print(f"    - id={eid!r} name={ename!r} type={etype!r} text={etext!r}")
                    except Exception:
                        pass
            except Exception as e:
                print(f"  ⚠️ Error enumerating <{tag}>: {e}")

        # Try a few selectors
        print("  --- Selector probes ---")
        probes = [
            (By.ID, "UserName"),
            (By.CSS_SELECTOR, "#UserName"),
            (By.CSS_SELECTOR, "input[name='UserName']"),
            (By.CSS_SELECTOR, "input[id='UserName']"),
            (By.NAME, "UserName"),
            (By.XPATH, "//input[@id='UserName']"),
            (By.CSS_SELECTOR, "input[type='text']"),
            (By.ID, "Password"),
            (By.ID, "btnLogin"),
            (By.ID, "login-form"),
        ]
        for method, sel in probes:
            try:
                found = driver.find_elements(method, sel)
                print(f"  {method}={sel!r}: {len(found)} match(es)")
            except Exception as e:
                print(f"  {method}={sel!r}: ERROR {e}")

        # Iframes (likely culprit if count > 0)
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for i, ifr in enumerate(iframes):
                print(f"  iframe[{i}] src={ifr.get_attribute('src')!r} id={ifr.get_attribute('id')!r} name={ifr.get_attribute('name')!r}")
        except Exception as e:
            print(f"  ⚠️ iframe enumeration error: {e}")

        # Body text (first 500 chars) to confirm page rendered content
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            body_text = (body.text or "")[:500]
            print(f"  Body text (first 500 chars): {body_text!r}")
        except Exception as e:
            print(f"  ⚠️ Body read error: {e}")

        # Detect common JS framework markers
        for marker in ["react", "vue", "angular", "next", "nuxt"]:
            try:
                has = driver.execute_script(
                    f"return !!document.querySelector('[class*=\"{marker}\"], [id*=\"{marker}\"]')"
                )
                if has:
                    print(f"  JS framework hint: {marker}")
            except Exception:
                pass

        print("=== END DEBUG DUMP ===\n")

    except Exception as e:
        print(f"❌ Diagnostic error: {e}")
        import traceback
        traceback.print_exc()
        try:
            driver.save_screenshot("debug_page.png")
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("   💾 Saved debug artifacts (with errors)")
        except Exception:
            pass

def dump_network_logs(driver, label="network"):
    """Print Chrome's network + browser console logs."""
    try:
        perf = driver.get_log("performance")
    except Exception:
        perf = []
    try:
        browser = driver.get_log("browser")
    except Exception:
        browser = []

    print(f"\n--- {label} (browser console) ---")
    for entry in browser:
        print(f"  [{entry.get('level')}] {entry.get('message')}")

    print(f"--- {label} (network events) ---")
    for entry in perf:
        try:
            msg = json.loads(entry["message"])["message"]
        except Exception:
            continue
        method = msg.get("method")
        params = msg.get("params", {})
        if method == "Network.responseReceived":
            resp = params.get("response", {})
            print(f"  RESP {resp.get('status')} {resp.get('url')}")
        elif method == "Network.requestWillBeSent":
            req = params.get("request", {})
            print(f"  REQ  {req.get('method')} {req.get('url')}")
        elif method == "Network.loadingFailed":
            print(f"  FAIL {params.get('errorText')} (type={params.get('type')})")
    print("--- end ---\n")


def login_with_selenium(driver):
    """Login using Selenium with robust element waiting and diagnostics."""
    print("🔐 Attempting login with Selenium...")

    try:
        login_url = f"{BASE_URL}/star/User/Login"
        print(f"   Navigating to: {login_url}")
        driver.get(login_url)

        # Wait until document is complete
        try:
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except Exception:
            pass

        print(f"   Page loaded: {driver.title}")
        print(f"   Current URL: {driver.current_url}")

        dump_network_logs(driver, "after-navigation")
        print(f"   Page source length in Selenium: {len(driver.page_source)}")
        print(f"   First 200 chars: {driver.page_source[:200]!r}")

        # Give client-side rendering a short grace period
        time.sleep(2)

        # Handle possible iframes (if form is embedded)
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                print(f"   ⚠️ Found {len(iframes)} iframe(s) - switching into first frame")
                WebDriverWait(driver, 10).until(
                    EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe"))
                )
        except Exception as e:
            print(f"   ⚠️ Iframe handling skipped: {e}")

        # Wait for username field (presence, not visibility - more lenient)
        print("   Waiting for login form (up to 30s)...")
        try:
            username_field = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "UserName"))
            )
        except Exception:
            # Fallback selectors if ID doesn't match
            print("   ⚠️ #UserName not found, trying fallback selectors...")
            fallback_selectors = [
                (By.NAME, "UserName"),
                (By.CSS_SELECTOR, "input[name='UserName']"),
                (By.CSS_SELECTOR, "input[type='text']"),
                (By.CSS_SELECTOR, "form#login-form input[type='text']"),
            ]
            username_field = None
            for method, sel in fallback_selectors:
                try:
                    els = driver.find_elements(method, sel)
                    if els:
                        username_field = els[0]
                        print(f"   ✅ Using fallback selector {method}={sel!r}")
                        break
                except Exception:
                    continue
            if username_field is None:
                # Run diagnostic to capture state before raising
                print("   ❌ Could not locate username field - running diagnostic")
                debug_page(driver)
                return False

        print("   ✅ Login form found")

        # Fill username
        try:
            username_field.clear()
            username_field.send_keys(USERNAME)
            print("   ✅ Username entered")
        except Exception as e:
            print(f"   ❌ Username entry failed: {e}")
            return False

        # Fill password
        try:
            password_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "Password"))
            )
        except Exception:
            try:
                password_field = driver.find_element(By.NAME, "Password")
            except Exception:
                password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        password_field.clear()
        password_field.send_keys(PASSWORD)
        print("   ✅ Password entered")

        # Click login button (try multiple selectors)
        login_button = None
        for method, sel in [
            (By.ID, "btnLogin"),
            (By.CSS_SELECTOR, "input#btnLogin"),
            (By.CSS_SELECTOR, "input[type='submit']"),
            (By.CSS_SELECTOR, "button[type='submit']"),
        ]:
            try:
                els = driver.find_elements(method, sel)
                if els:
                    login_button = els[0]
                    break
            except Exception:
                continue
        if login_button is None:
            print("   ❌ Login button not found")
            debug_page(driver)
            return False

        login_button.click()
        print("   ✅ Clicked login button")

        # Wait for URL to change away from login
        try:
            WebDriverWait(driver, 20).until(
                lambda d: "login" not in d.current_url.lower()
            )
        except Exception:
            print("   ⚠️ URL still contains 'login' after timeout")
            print(f"   Current URL: {driver.current_url}")

        current_url = driver.current_url
        print(f"   Current URL after login: {current_url}")

        if "login" not in current_url.lower():
            print("✅ Login successful!")
            return True
        else:
            print("❌ Login failed - still on login page")
            try:
                driver.save_screenshot("login_error.png")
                with open("login_error.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print("   💾 Debug files saved: login_error.png, login_error.html")
            except Exception:
                pass
            return False

    except Exception as e:
        print(f"❌ Login error: {e}")
        import traceback
        traceback.print_exc()
        try:
            driver.save_screenshot("login_error.png")
            with open("login_error.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("   💾 Debug files saved: login_error.png, login_error.html")
        except Exception:
            pass
        return False
    finally:
        # Always switch back to default content in case we entered an iframe
        try:
            driver.switch_to.default_content()
        except Exception:
            pass


def get_class_capacity(class_name, class_type):
    """Determine class capacity based on class name/type"""
    # Combine class_name and class_type for matching
    full_name = f"{class_type} {class_name}".upper()
    
    # Look for capacity in mapping
    for key, capacity in CLASS_CAPACITY.items():
        if key.upper() in full_name:
            return capacity
    
    # Try to extract number from class name (e.g., "CLASS 1" might have capacity 50)
    numbers = re.findall(r'\d+', class_name)
    if numbers:
        # If class name has a number, use default capacity
        return CLASS_CAPACITY["default"]
    
    return CLASS_CAPACITY["default"]

def get_attendance_for_date(driver, search_date):
    """Fetch attendance for a specific date"""
    try:
        formatted_date_input = search_date.strftime("%d/%m/%Y")
        print(f"  🔍 Checking {formatted_date_input} ({search_date.strftime('%A')})...", end=" ", flush=True)
        
        driver.get(f"{BASE_URL}/star/AttendanceRecord/Kpp")
        time.sleep(2)
        
        try:
            date_field = driver.find_element(By.ID, "lessonDate")
            date_field.clear()
            date_field.send_keys(formatted_date_input)
        except:
            print("date error", end=" ")
            return []
        
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
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        records = []
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                if row.find('th'):
                    continue
                
                cells = row.find_all('td')
                if len(cells) >= 5:
                    student_id = cells[0].get_text(strip=True)
                    class_name = cells[1].get_text(strip=True)
                    date_str = cells[2].get_text(strip=True)
                    class_type = cells[3].get_text(strip=True)
                    present = cells[4].get_text(strip=True) if len(cells) > 4 else "0"
                    
                    if student_id and student_id.isdigit():
                        present_num = int(present) if present.isdigit() else 0
                        
                        # Get class capacity
                        total_capacity = get_class_capacity(class_name, class_type)
                        
                        records.append({
                            'date': date_str,
                            'class_id': student_id,
                            'class_name': class_name,
                            'class_type': class_type,
                            'present_count': str(present_num),
                            'total_students': str(total_capacity)
                        })
        
        if records:
            print(f"✅ Found {len(records)} class(es)")
        else:
            print(f"📭 No classes")
        
        return records
        
    except Exception as e:
        print(f"❌ Error")
        return []

def get_attendance_for_weekends(driver, months_ahead=1):
    """Fetch attendance only for weekend dates"""
    weekend_dates = get_upcoming_weekends(months_ahead)
    
    print(f"\n📅 Fetching attendance for {len(weekend_dates)} weekend dates")
    print("=" * 50)
    
    all_records = []
    
    for date in weekend_dates:
        records = get_attendance_for_date(driver, date)
        all_records.extend(records)
        time.sleep(1)  # Be nice to the server
    
    return all_records

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
    
    def parse_date(date_str):
        try:
            return datetime.strptime(date_str, '%d/%m/%Y')
        except:
            try:
                return datetime.strptime(date_str, '%m/%d/%Y')
            except:
                return datetime.min
    
    if simplified_data:
        simplified_data.sort(key=lambda x: parse_date(x['date']))
    
    output = {
        'last_updated': datetime.now().isoformat(),
        'scrape_date_range': {
            'from': simplified_data[0]['date'] if simplified_data else None,
            'to': simplified_data[-1]['date'] if simplified_data else None,
            'weekends_only': True
        },
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
                # Parse and show day of week
                try:
                    date_obj = datetime.strptime(record['date'], '%d/%m/%Y')
                    day_name = date_obj.strftime('%A')
                    print(f"\n📅 {record['date']} ({day_name})")
                except:
                    print(f"\n📅 {record['date']}")
            print(f"   {record['class_type']} {record['class_name']} ({record['present_count']}/{record['total_students']})")

def raw_http_probe():
    """Print the raw HTTP response so we can see what the server sends."""
    import urllib.request, urllib.error
    url = f"{BASE_URL}/star/User/Login"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    }
    print(f"🌐 Raw HTTP probe: {url}")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read()
            print(f"   Status: {resp.status}")
            print(f"   Headers: {dict(resp.headers)}")
            print(f"   Body length: {len(body)}")
            print(f"   Body repr (first 1000): {body[:1000]!r}")
    except urllib.error.HTTPError as e:
        print(f"   HTTPError: {e.code} {e.reason}")
        print(f"   Body: {e.read()[:1000]!r}")
    except Exception as e:
        print(f"   Error: {e!r}")

def main():
    print("🚀 Driving School Attendance Scraper (Weekend-Optimized Version)")
    print("=" * 50)
    print(f"Username configured: {'Yes' if USERNAME else 'No'}")
    print(f"Password configured: {'Yes' if PASSWORD else 'No'}")
    print()
    
    if not USERNAME or not PASSWORD:
        print("❌ Missing credentials!")
        exit(1)

    raw_http_probe()
    print()
    
    driver = None
    try:
        print("📱 Setting up browser...")
        driver = setup_driver()
        print("✅ Browser ready")
        
        if login_with_selenium(driver):
            print("\n✅ Ready to fetch attendance data (weekends only)")
            
            # Check weekends for current month + next 2 months (adjustable)
            attendance_data = get_attendance_for_weekends(driver, months_ahead=1)
            
            if attendance_data:
                save_data(attendance_data)
                print(f"\n✅ Successfully processed {len(attendance_data)} class records")
            else:
                print("\n⚠️ No attendance records found")
                output = {
                    'last_updated': datetime.now().isoformat(),
                    'scrape_date_range': {
                        'weekends_only': True
                    },
                    'attendance_summary': []
                }
                with open('attendance.json', 'w') as f:
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
