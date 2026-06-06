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
    """Login to the driving school system"""
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
    
    login_data = {
        'UserName': USERNAME,
        'Password': PASSWORD,
    }
    
    try:
        # Get login page first to capture any CSRF tokens
        response = session.get(login_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for CSRF token
        csrf_token = soup.find('input', {'name': '__RequestVerificationToken'})
        if csrf_token:
            login_data['__RequestVerificationToken'] = csrf_token['value']
            print("✅ CSRF token found")
        
        # Perform login
        response = session.post(login_url, data=login_data, headers=headers, allow_redirects=True)
        
        # Check if login successful
        if "Login" not in response.text or "logout" in response.text.lower():
            print("✅ Login successful!")
            return True
        else:
            print("❌ Login failed - Still on login page")
            return False
            
    except Exception as e:
        print(f"❌ Login error: {e}")
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
        # Format date for the form (MM/DD/YYYY)
        formatted_date = search_date.strftime("%m/%d/%Y")
        
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
        
        # Submit the search form
        response = session.post(attendance_url, data=search_data, headers=headers)
        
        if response.status_code != 200:
            print(f"  ⚠️ Failed to fetch {formatted_date} - Status: {response.status_code}")
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
                # Skip header rows
                if row.find('th'):
                    continue
                
                cells = row.find_all('td')
                if len(cells) >= 5:
                    # Extract data from cells
                    student_id = cells[0].get_text(strip=True) if len(cells) > 0 else ""
                    class_name = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    date = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    class_type = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                    present = cells[4].get_text(strip=True) if len(cells) > 4 else "0"
                    absent = cells[5].get_text(strip=True) if len(cells) > 5 else "0"
                    late = cells[6].get_text(strip=True) if len(cells) > 6 else "0"
                    
                    # Only add if we have valid data
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
            print(f"  ✅ {formatted_date}: Found {len(records)} class(es)")
        else:
            print(f"  📭 {formatted_date}: No classes")
        
        return records
        
    except Exception as e:
        print(f"  ❌ Error fetching {search_date.strftime('%m/%d/%Y')}: {e}")
        return []

def get_month_attendance(year, month):
    """Fetch attendance for entire month"""
    print(f"\n📅 Fetching attendance for {calendar.month_name[month]} {year}")
    print("=" * 50)
    
    # Get number of days in month
    num_days = calendar.monthrange(year, month)[1]
    
    all_records = []
    
    # Loop through each day of the month
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
    """Save to JSON file in the simple format needed for display"""
    
    # Group and simplify the data
    simplified_data = []
    
    for record in attendance_records:
        # Calculate total students
        present = int(record['present_count']) if record['present_count'].isdigit() else 0
        absent = int(record['absent_count']) if record['absent_count'].isdigit() else 0
        late = int(record['late_count']) if record['late_count'].isdigit() else 0
        total = present + absent + late
        
        # Create simplified record
        simplified_record = {
            'date': record['date'],
            'class_name': record['class_name'],
            'class_type': record['class_type'],
            'present_count': str(present),
            'total_students': str(total)
        }
        simplified_data.append(simplified_record)
    
    # Sort by date
    simplified_data.sort(key=lambda x: datetime.strptime(x['date'], '%m/%d/%Y') if x['date'] else datetime.min)
    
    # Prepare final output
    output = {
        'last_updated': datetime.now().isoformat(),
        'attendance_summary': simplified_data
    }
    
    with open('attendance.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Saved {len(simplified_data)} class records to attendance.json")
    
    # Print summary
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
    
    if not USERNAME or not PASSWORD:
        print("❌ Missing credentials!")
        print("Please set COMPANY_USERNAME and COMPANY_PASSWORD in GitHub Secrets")
        exit(1)
    
    if login():
        print("\n✅ Ready to fetch attendance data")
        
        # Get current month attendance
        attendance_data = get_current_month_attendance()
        
        if attendance_data:
            save_data(attendance_data)
            print(f"\n✅ Successfully processed {len(attendance_data)} class records")
        else:
            print("\n⚠️ No attendance records found for this month")
            # Save empty data structure
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
