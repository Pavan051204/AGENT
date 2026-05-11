import requests
import time

BASE_URL = "http://127.0.0.1:8000"

def login(username):
    # In case the user isn't registered, we should try login first.
    # We don't have the exact passwords, but the user says "i will give u usaer name it the password too testit,testemp,testhr".
    # This implies the password is the same as the username or they forgot to provide the password explicitly. Let's try username as password.
    res = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": username})
    if res.status_code == 200 and res.json().get("success"):
        return res.json()["token"], res.json()["role"]
    
    # Maybe the password is "password"? Or "admin"?
    res = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": "password"})
    if res.status_code == 200 and res.json().get("success"):
        return res.json()["token"], res.json()["role"]

    print(f"Failed to login with {username}")
    return None, None

def chat(token, user_id, role, query):
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "user_id": user_id,
        "role": role,
        "query": query,
        "session_id": "test_session_123",
        "model_preference": "groq"
    }
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=headers)
    if res.status_code == 200:
        return res.json()["response"]
    return f"Error: {res.text}"

def test_rag_and_rbac():
    users = ["testemp", "testhr", "testit"]
    prompts = [
        "What is the company leave policy?",  # Internal PDF test
        "Who won the Super Bowl in 2024?",    # Web search fallback test
        "Show me all IT tickets",             # RBAC test (emp vs it)
    ]
    
    for u in users:
        print(f"\\n--- Testing User: {u} ---")
        token, role = login(u)
        if not token:
            continue
            
        print(f"Role: {role}")
        for p in prompts:
            print(f"\\nPrompt: {p}")
            response = chat(token, u, role, p)
            print(f"Response:\\n{response}".encode('ascii', 'ignore').decode('ascii'))
            time.sleep(1)

if __name__ == "__main__":
    test_rag_and_rbac()
