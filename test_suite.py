import requests
import time

BASE_URL = "http://localhost:8000"

def test_workflow():
    print("Starting e2e test workflow...")
    
    # 1. Register Users
    users = [
        {"username": "emp1", "password": "password123", "role": "employee"},
        {"username": "hr1", "password": "password123", "role": "hr"},
        {"username": "it1", "password": "password123", "role": "it"},
        {"username": "mgr1", "password": "password123", "role": "manager"}
    ]
    
    tokens = {}
    for u in users:
        r = requests.post(f"{BASE_URL}/auth/register", json=u)
        if r.status_code == 200 and r.json().get("success"):
            tokens[u["role"]] = r.json()["token"]
            print(f"Registered {u['username']} ({u['role']})")
        else:
            # Maybe already exists, try login
            r = requests.post(f"{BASE_URL}/auth/login", json={"username": u["username"], "password": u["password"]})
            tokens[u["role"]] = r.json()["token"]
            print(f"Logged in {u['username']} ({u['role']})")

    emp_token = tokens["employee"]
    hr_token = tokens["hr"]
    it_token = tokens["it"]
    mgr_token = tokens["manager"]

    def chat(token, query, session_id="test_session"):
        # We need to know the user_id, but the backend extracts it from token.
        # Let's check the /api/chat endpoint payload
        # chat req: user_id, role, query, session_id, model_preference
        # Actually /auth/me gets user details
        headers = {"Authorization": f"Bearer {token}"}
        user_info = requests.get(f"{BASE_URL}/auth/me", headers=headers).json()
        
        req = {
            "user_id": str(user_info["user_id"]),
            "role": user_info["role"],
            "query": query,
            "session_id": session_id
        }
        r = requests.post(f"{BASE_URL}/api/chat", json=req, headers=headers)
        return r.json()

    print("\n--- Testing RAG & Intent ---")
    r = chat(emp_token, "What is the notice period policy?")
    print("RAG Response:", r["response"])

    print("\n--- Testing HR Leave Workflow ---")
    # 1. Check balance
    r = chat(emp_token, "What is my leave balance?")
    print("Balance Response:", r["response"])
    
    # 2. Apply leave
    # Need HR user available. Let's see if hr1 is in the list.
    r = chat(emp_token, "Apply casual leave from 2026-06-10 to 2026-06-12 for vacation hr hr1")
    print("Apply Leave Response:", r["response"])
    
    # 3. Get pending approvals for HR
    headers_hr = {"Authorization": f"Bearer {hr_token}"}
    r = requests.get(f"{BASE_URL}/api/approvals/pending", headers=headers_hr)
    approvals = r.json().get("approvals", [])
    print("HR Pending Approvals:", len(approvals))
    
    if approvals:
        app_id = approvals[0]["id"]
        # 4. Approve leave
        r = requests.post(f"{BASE_URL}/api/approvals/{app_id}/decide", json={"status": "approved"}, headers=headers_hr)
        print("Leave Approve Response:", r.json())
        
        # 5. Check balance again
        r = chat(emp_token, "What is my leave balance?")
        print("Balance After Approval:", r["response"])

    print("\n--- Testing IT Ticket Workflow ---")
    # 1. Create ticket
    r = chat(emp_token, "My laptop screen is flickering")
    print("Create Ticket Response:", r["response"])
    
    # 2. View tickets (Employee)
    r = chat(emp_token, "View my tickets")
    print("View My Tickets:", r["response"])
    
    # 3. View all tickets (IT)
    r = chat(it_token, "View all tickets")
    print("View All Tickets (IT):", r["response"])
    
    # 4. Resolve ticket (IT)
    # Get ticket ID from IT view
    headers_it = {"Authorization": f"Bearer {it_token}"}
    r = requests.get(f"{BASE_URL}/api/tickets", headers=headers_it)
    tickets = r.json().get("tickets", [])
    if tickets:
        t_id = tickets[0]["id"]
        # Resolve via chat agent for IT
        r = chat(it_token, f"resolve ticket {t_id}")
        print(f"Resolve Ticket {t_id} Response:", r["response"])

    print("\n--- Testing IT Asset Workflow ---")
    r = chat(emp_token, "I need a new monitor for video editing")
    print("Request Asset Response:", r["response"])
    
    print("\n--- Testing RBAC Restrictions ---")
    # Employee trying to view all tickets
    r = chat(emp_token, "View all tickets")
    print("Employee View All Tickets:", r["response"])

if __name__ == '__main__':
    test_workflow()
