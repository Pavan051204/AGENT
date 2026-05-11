import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def login(username):
    res = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": username})
    if res.status_code == 200 and res.json().get("success"):
        return res.json()["token"], res.json()["role"]
    res = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": "password"})
    if res.status_code == 200 and res.json().get("success"):
        return res.json()["token"], res.json()["role"]
    return None, None

def chat(token, user_id, role, query):
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "user_id": user_id,
        "role": role,
        "query": query,
        "session_id": f"test_session_{user_id}",
        "model_preference": "groq"
    }
    res = requests.post(f"{BASE_URL}/api/chat", json=payload, headers=headers)
    if res.status_code == 200:
        return res.json()["response"]
    return f"Error: {res.text}"

def main():
    token_emp, role_emp = login("testemp")
    token_hr, role_hr = login("testhr")
    token_it, role_it = login("testit")

    test_cases = {
        "RAG_Internal_Policies": [
            "What is the dress code policy?",
            "Explain the background verification policy.",
            "What are the rules for Work from Home?",
            "What is the corporate social responsibility policy?",
            "What is the advance salary policy?" # Expected to NOT use web search, say "not found"
        ],
        "Web_Search_General": [
            "How to make chicken biryani?",
            "Who won the Super Bowl in 2024?",
            "What is the capital of France?",
            "Explain the theory of relativity simply.",
            "What is the latest stock price of Microsoft?"
        ],
        "Leaves_and_HR": [
            "What is my leave balance?",
            "Apply casual leave from 2026-06-01 to 2026-06-03 for family function.",
            "Show my pending leave requests.",
            "Show me all IT tickets." # Should be denied for HR and EMP
        ],
        "IT_Tickets_and_Assets": [
            "Raise IT ticket for VPN issue because it keeps disconnecting.",
            "Show my IT tickets.",
            "Request a laptop for new project.",
            "Show me all leave requests." # Should be denied for IT
        ]
    }

    results = []

    for category, queries in test_cases.items():
        for q in queries:
            # Let's test with testemp by default, except for specific RBAC tests
            user = "testemp"
            role = role_emp
            token = token_emp

            # For RBAC tests, we can test with specific users
            if "IT tickets" in q and category == "Leaves_and_HR":
                user = "testhr"
                role = role_hr
                token = token_hr
            elif "leave requests" in q and category == "IT_Tickets_and_Assets":
                user = "testit"
                role = role_it
                token = token_it

            if not token:
                continue

            print(f"Testing: {q} (User: {user})")
            response = chat(token, user, role, q)
            results.append({
                "Category": category,
                "User": user,
                "Role": role,
                "Query": q,
                "Response": response
            })
            time.sleep(1)

    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
