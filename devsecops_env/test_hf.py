import requests
import sys

URL = "https://khushmagrawal-devsecops-env.hf.space/reset"

print(f"Pinging {URL} ...")
try:
    response = requests.post(URL, json={})
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("✅ SUCCESS! The Space is live and properly responding to agent resets.")
        print(response.json())
    else:
        print(f"❌ Failed. Returns: {response.text}")
except Exception as e:
    print(f"❌ Request failed: {e}")
