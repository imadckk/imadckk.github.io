import requests

USERNAME = "dale"  # Replace with actual for testing
PASSWORD = "5650"  # Replace with actual for testing
BASE_URL = "http://adcdriving.dyndns.biz"

session = requests.Session()

# Try simple GET first
response = session.get(f"{BASE_URL}/star/User/Login")
print(f"GET status: {response.status_code}")

# Try simple POST
data = {
    'UserName': USERNAME,
    'Password': PASSWORD
}
response = session.post(f"{BASE_URL}/star/User/Login", data=data)
print(f"POST status: {response.status_code}")
print(f"URL after POST: {response.url}")
print(f"Response length: {len(response.text)}")
