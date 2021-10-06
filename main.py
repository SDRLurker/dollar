import os
import requests

if __name__ == "__main__":
    periods = ("1mo","3mo","6mo","1y")
    for p in periods:
        url = os.environ.get('URL','') if os.environ.get('URL','') else 'http://127.0.0.1:5000'
        url = url + "/dollar/%s" % p
        r = requests.post(url, {})
        print(url, r.json())
