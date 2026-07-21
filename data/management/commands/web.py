import requests
url = "https://chartink.com/screener/50ma-setup"
response = requests.get(url)
html = response.text
print(html)
