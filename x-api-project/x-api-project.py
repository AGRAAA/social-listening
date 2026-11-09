import os
import requests
import json
from dotenv import load_dotenv

# Membaca token dari .env
load_dotenv()
TOKEN = os.getenv("X_BEARER_TOKEN")

# Endpoint X API v2
URL = "https://api.x.com/2/tweets/search/recent"

# Header autentikasi
headers = {
    "Authorization": f"Bearer {TOKEN}"
}

# Parameter pencarian
params = {
    "query": "indonesia -is:retweet",
    "max_results": 10,
    "tweet.fields": "created_at,author_id,public_metrics"
}

# Mengirim request
response = requests.get(
    URL,
    headers=headers,
    params=params,
    timeout=30
)

# Memeriksa hasil
print("Status Code:", response.status_code)
print("Response:", response.text)

response.raise_for_status()

# Mengubah response menjadi JSON
data = response.json()

# Menampilkan hasil
print(json.dumps(data, indent=4, ensure_ascii=False))

# Menyimpan hasil ke file
# with open("hasil.json", "w", encoding="utf-8") as file:
#     json.dump(data, file, indent=4, ensure_ascii=False)

print("Data berhasil disimpan!")