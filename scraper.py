import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import calendar
import re

# Get credentials from GitHub Secrets
USERNAME = os.environ.get('COMPANY_USERNAME')
PASSWORD = os.environ.get('COMPANY_PASSWORD')
BASE_URL = "http://adcdriving.dyndns.biz"

# Create session to maintain cookies
session = requests.Session()

def login():
    """Login to the driving school system"""
    print("🔐 Attempting login...")
    
    login_url = f"{BASE_URL}/star/User/Login"
    
    # Get the login page first
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        # Get the login page to capture ViewState and other hidden fields
        print(f"📄 Fetching login page...")
        response = session.get(login_url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract all hidden fields (ASP.NET ViewState, etc.)
        login_data = {}
        
        # Find all hidden input fields
        hidden_inputs = soup.find_all('input', type='hidden')
        for hidden in hidden_inputs:
            name = hidden.get('name')
            value = hidden.get('value', '')
            if name:
                login_data[name] = value
                print(f"   Found hidden field: {name}")
        
        # Add username and password
        login_data['UserName'] = USERNAME
        login_data['Password'] = PASSWORD
        login_data['RememberMe'] = 'false'
        
        # Find the submit button name
        submit_button = soup.find('input', type='submit')
        if submit_button and submit_button.get('name'):
            login_data[submit_button['name']] = submit_button.get('value', 'Login')
        else:
            login_data['btnLogin'] = 'Login'
        
        print(f"📦 Sending login with fields: {list(login_data.keys())}")
        
        # Updated headers for POST request
        post_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': BASE_URL,
            'Referer': login_url,
            'Connection': 'keep-alive',
        }
        
        # Perform login
        print(f"🔑 Sending login POST...")
        response = session.post(login_url, data=login_data, headers=post_headers, allow_redirects=True)
        print(f"   Response status: {response.status_code}")
        print(f"   Final URL: {response.url}")
        
        # Check if login was successful
        if response.status_code == 200:
            # Check if we're on a page that requires authentication
            if 'logout' in response.text.lower() or 'dashboard' in response.text.lower():
                print("✅ Login successful! (found dashboard)")
                return True
            elif 'login' not in response.url.lower():
                print("✅ Login successful! (redirected)")
                return True
            elif 'attendance' in response.text.lower():
                print("✅ Login successful! (found attendance page)")
                return True
        
        # If we got a 500, maybe we need to try a different approach
        if response.status_code == 500:
            print("⚠️ Server returned 500 error - trying alternative login method...")
            return alternative_login()
        
        print("❌ Login failed")
        return False
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False

def alternative_login():
    """Alternative login method using simpler approach"""
    print("🔄 Attempting alternative login method...")
    
    login_url = f"{BASE_URL}/star/User/Login"
    
    # Simple form data - only username and password
    login_data = {
        'UserName': USERNAME,
        'Password': PASSWORD,
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': login_url,
    }
    
    try:
        # Try direct POST without viewstate
        response = session.post(login_url, data=login_data, headers=headers, allow_redirects=True)
        print(f"   Response status: {response.status_code}")
        print(f"   Final URL: {response.url}")
        
        if response.status_code == 200 or response.status_code == 302:
            # Check if we have access to attendance page
            test_url = f"{BASE_URL}/star/AttendanceRecord/Kpp"
            test_response = session.get(test_url, headers=headers)
            
            if test_response.status_code == 200 and 'Kpp' in test_response.text:
                print("✅ Alternative login successful!")
                return True
        
        print("❌ Alternative login failed")
        return False
        
    except Exception as e:
        print(f"❌ Alternative login error: {e}")
        return False

def check_login_status():
    """Check if we're actually logged in by accessing a protected page"""
    test_url = f"{BASE_URL}/star/AttendanceRecord/Kpp"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    try:
        response = session.get(test_url, headers=headers)
        
        if response.status_code == 200:
            # Check if we got the attendance page (not redirected to login)
            if 'login' not in response.url.lower():
                print("✅ Session is authenticated")
                return True
            else:
                print("❌ Session not authenticated - redirected to login")
                return False
        else:
            print(f"❌ Session check failed with status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Session check error: {e}")
        return False

def get_attendance_for_date(search_date):
    """Fetch attendance data for a specific date"""
    attendance_url = f"{BASE_URL}/star/AttendanceRecord/Kpp"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': attendance_url,
    }
    
    try:
        formatted_date = search_date.strftime("%m/%d/%Y")
        print(f"  🔍 Checking {formatted_date}...", end=" ", flush=True)
        
        # First, get the page to get any necessary tokens
        response = session.get(attendance_url, headers=headers)
        
        if response.status_code != 200:
            print(f"⚠️ Failed to load page")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the search form data
        search_data = {}
        
        # Add any hidden fields
        hidden_inputs = soup.find_all('input', type='hidden')
        for hidden in hidden_inputs:
            name = hidden.get('name')
            value = hidden.get('value', '')
            if name:
                search_data[name] = value
        
        # Add the date
        search_data['lessonDate'] = formatted_date
        
        # Add the search button
        search_data['mySearchButton'] = 'Search'
        
        # Submit the search
        response = session.post(attendance_url, data=search_data, headers=headers)
        
        if response.status_code != 200:
            print(f"⚠️ Search failed")
            return []
        
        # Parse the response for attendance data
        soup = BeautifulSoup(response.text, 'html.parser')
        
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
                    date = cells[2].get_text(strip=True)
                    class_type = cells[3].get_text(strip=True)
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
    
    # For testing, let's just check a few days first
    # Change this to range(1, num_days + 1) for full month
    num_days = calendar.monthrange(year, month)[1]
    all_records = []
    
    # Limit to current and next few days for testing
    current_day = datetime.now().day
    days_to_check = range(max(1, current_day - 2), min(num_days + 1, current_day + 3))
    
    print(f"⚠️ Testing mode: Checking days {list(days_to_check)} only")
    
    for day in days_to_check:
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
    
    if simplified_data:
        simplified_data.sort(key=lambda x: datetime.strptime(x['date'], '%m/%d/%Y'))
    
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
    print("🚀 Driving School Attendance Scraper")
    print("=" * 50)
    print(f"Username configured: {'Yes' if USERNAME else 'No'}")
    print(f"Password configured: {'Yes' if PASSWORD else 'No'}")
    print(f"Base URL: {BASE_URL}")
    print()
    
    if not USERNAME or not PASSWORD:
        print("❌ Missing credentials!")
        exit(1)
    
    if login():
        # Verify session is working
        if check_login_status():
            print("\n✅ Ready to fetch attendance data")
            attendance_data = get_current_month_attendance()
            
            if attendance_data:
                save_data(attendance_data)
            else:
                print("\n⚠️ No attendance records found")
                # Create empty JSON
                output = {
                    'last_updated': datetime.now().isoformat(),
                    'attendance_summary': []
                }
                with open('attendance.json', 'w') as f:
                    json.dump(output, f, indent=2)
        else:
            print("❌ Session verification failed")
            exit(1)
    else:
        print("❌ Login failed")
        exit(1)

if __name__ == "__main__":
    main()
