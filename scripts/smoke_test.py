import requests

def main():
    base = "http://localhost:8000"
    print("Health:", requests.get(f"{base}/health").json())
    r = requests.post(f"{base}/generate_mock", json={"prompt":"你好", "max_tokens":64})
    print("Mock generate:", r.json())

if __name__ == "__main__":
    main()
