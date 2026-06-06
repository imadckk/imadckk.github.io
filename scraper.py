import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import calendar

# Get credentials from GitHub Secrets
USERNAME = os.environ.get('COMPANY_USERNAME')
PASSWORD = os.environ.get('COMPANY_PASSWORD')
BASE_URL = "http://adcdriving.dyndns.biz"

# Create session to maintain cookies
session = requests.Session()

def login():
    """Login to the driving school system with debug output"""
    print("🔐 Attempting login...")
    
    login_url = f"{BASE_URL}/star/User/Login"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': BASE_URL,
        'Referer': login_url
    }
    
    try:
        # First, get the login page to see the form structure
        print(f"📄 Fetching login page: {login_url}")
        response = session.get(login_url, headers=headers)
        print(f"   Status: {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Debug: Save login page HTML to see what's happening
        with open('debug_login.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("   ✅ Saved login page to debug_login.html")
        
        # Find all form inputs
        form = soup.find('form')
        if form:
            print(f"   📋 Found form with action: {form.get('action', 'N/A')}")
        
        # Find all input fields
        inputs = soup.find_all('input')
        print(f"   📝 Found {len(inputs)} input fields")
        
        login_data = {}
        
        for input_field in inputs:
            input_name = input_field.get('name')
            input_type = input_field.get('type', 'text')
            input_id = input_field.get('id', '')
            
            if input_name:
                print(f"      - {input_name} (type: {input_type}, id: {input_id})")
                
                # Handle different field types
                if input_type == 'text' or input_id == 'UserName' or input_name == 'UserName':
                    login_data[input_name] = USERNAME
                elif input_type == 'password' or input_id == 'Password' or input_name == 'Password':
                    login_data[input_name] = PASSWORD
                elif input_type == 'submit':
                    login_data[input_name] = 'Login'
                elif input_name == '__RequestVerificationToken':
                    login_data[input_name] = input_field.get('value', '')
                else:
                    # Keep any hidden fields
                    if input_type == 'hidden':
                        login_data[input_name] = input_field.get('value', '')
        
        print(f"\n📦 Login data prepared: {list(login_data.keys())}")
        
        # Check if we found username and password fields
        has_username = any('user' in k.lower() or k == 'UserName' for k in login_data.keys())
        has_password = any('pass' in k.lower() or k == 'Password' for k in login_data.keys())
        
        if not has_username:
            print("   ⚠️ Warning: No username field found!")
        if not has_password:
            print("   ⚠️ Warning: No password field found!")
        
        # Perform login
        print(f"\n🔑 Sending login POST to: {login_url}")
        response = session.post(login_url, data=login_data, headers=headers, allow_redirects=True)
        print(f"   Response status: {response.status_code}")
        print(f"   Final URL: {response.url}")
        
        # Save the response for debugging
        with open('debug_after_login.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("   ✅ Saved post-login page to debug_after_login.html")
        
        # Check if login was successful
        # Look for indicators of successful login
        success_indicators = ['logout', 'dashboard', 'attendance', 'welcome', 'kpp']
        response_lower = response.text.lower()
        
        login_success = False
        for indicator in success_indicators:
            if indicator in response_lower:
                login_success = True
                print(f"   ✅ Found success indicator: '{indicator}'")
                break
        
        # Also check if we're not on the login page anymore
        if "login" not in response.url.lower() or "user/login" not in response.url.lower():
            login_success = True
            print(f"   ✅ Redirected away from login page")
        
        if login_success:
            print("✅ Login successful!")
            return True
        else:
            print("❌ Login failed - Still on login page or no success indicators")
            print(f"   Response preview: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_attendance_for_date(search_date):
    """Fetch attendance data for a specific date"""
    attendance_url = f"{BASE_URL}/star/AttendanceRecord/Kpp"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': f"{BASE_URL}/star/AttendanceRecord/Kpp"
    }
    
    try:
        formatted_date = search_date.strftime("%m/%d/%Y")
        print(f"  🔍 Checking {formatted_date}...", end=" ")
        
        # Get the page first to capture CSRF token
        response = session.get(attendance_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find CSRF token
        csrf_token = soup.find('input', {'name': '__RequestVerificationToken'})
        
        # Prepare search data
        search_data = {
            'lessonDate': formatted_date,
        }
        
        if csrf_token:
            search_data['__RequestVerificationToken'] = csrf_token['value']
        
        # Also try to find the search button name
        search_button = soup.find('button', {'id': 'mySearchButton'})
        if search_button and search_button.get('name'):
            search_data[search_button['name']] = 'Search'
        elif search_button:
            search_data['mySearchButton'] = 'Search'
        
        # Submit the search form
        response = session.post(attendance_url, data=search_data, headers=headers)
        
        if response.status_code != 200:
            print(f"⚠️ Failed - Status: {response.status_code}")
            return []
        
        # Parse the response
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all tables with class data
        records = []
        
        # Look for table rows with student data
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                if row.find('th'):
                    continue
                
                cells = row.find_all('td')
                if len(cells) >= 5:
                    student_id = cells[0].get_text(strip=True) if len(cells) > 0 else ""
                    class_name = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    date = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    class_type = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                    present = cells[4].get_text(strip=True) if len(cells) > 4 else "0"
                    absent = cells[5].get_text(strip=True) if len(cells) > 5 else "0"
                    late = cells[6].get_text(strip=True) if len(cells) > 6 else "0"
                    
                    if student_id and student_id.isdigit():
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

def get_month_attendance(year, month):
    """Fetch attendance for entire month"""
    print(f"\n📅 Fetching attendance for {calendar.month_name[month]} {year}")
    print("=" * 50)
    
    num_days = calendar.monthrange(year, month)[1]
    all_records = []
    
    for day in range(1, num_days + 1):
        current_date = datetime(year, month, day)
        records = get_attendance_for_date(current_date)
        all_records.extend(records)
    
    return all_records

def get_current_month_attendance():
    """Fetch attendance for current month"""
    now = datetime.now()
    return get_month_attendance(now.year, now.month)

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
    
    simplified_data.sort(key=lambda x: datetime.strptime(x['date'], '%m/%d/%Y') if x['date'] else datetime.min)
    
    output = {
        'last_updated': datetime.now().isoformat(),
        'attendance_summary': simplified_data
    }
    
    with open('attendance.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Saved {len(simplified_data)} class records to attendance.json")
    
    print("\n📊 SUMMARY:")
    print("=" * 50)
    current_date = None
    for record in simplified_data:
        if record['date'] != current_date:
            current_date = record['date']
            print(f"\n📅 {record['date']}")
        print(f"   {record['class_type']} {record['class_name']} ({record['present_count']}/{record['total_students']})")

def main():
    print("🚀 Driving School Attendance Scraper")
    print("=" * 50)
    print(f"Username configured: {'Yes' if USERNAME else 'No'}")
    print(f"Password configured: {'Yes' if PASSWORD else 'No'}")
    print(f"Base URL: {BASE_URL}")
    print()
    
    if not USERNAME or not PASSWORD:
        print("❌ Missing credentials!")
        print("Please set COMPANY_USERNAME and COMPANY_PASSWORD in GitHub Secrets")
        exit(1)
    
    if login():
        print("\n✅ Ready to fetch attendance data")
        
        # Optional: Test with just today first (uncomment to test)
        # print("\n🧪 Testing with today only...")
        # today = datetime.now()
        # test_records = get_attendance_for_date(today)
        # if test_records:
        #     print(f"✅ Test successful! Found {len(test_records)} records")
        #     save_data(test_records)
        # else:
        #     print("⚠️ Test found no records for today")
        
        # Get current month attendance
        attendance_data = get_current_month_attendance()
        
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
        print("❌ Login failed - Cannot fetch attendance")
        exit(1)

if __name__ == "__main__":
    main()
