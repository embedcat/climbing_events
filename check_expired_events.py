import time
import requests

BASE_URL = "http://127.0.0.1:8000"
ENDPOINT = "check_expired_events"


def main():
    cnt = 10
    while cnt > 0:
        response = requests.get(url=f"{BASE_URL}/{ENDPOINT}/")
        if response.status_code == 200:
            return
        time.sleep(3)
        cnt -= 1


if __name__=="__main__":
    main()