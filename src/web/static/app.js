// ===========================================================================
// NOVI PILOT — Modern Dashboard UI with Profile & Analytics
// ===========================================================================

const AUTH_TOKEN = localStorage.getItem("auth.token");
const AUTH_USERNAME = localStorage.getItem("auth.username");
const AUTH_USER_ID = localStorage.getItem("auth.user_id");
const AUTH_ROLE = localStorage.getItem("auth.role");

if (!AUTH_TOKEN) {
  window.location.href = "/";
}

// ---- DOM Elements --------------------------------------------------------

const chatLog = document.getElementById("chatLog");
const messageInput = document.getElementById("message");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearChat");
const sessionIdInput = document.getElementById("sessionId");
const modelSelect = document.getElementById("modelSelect");
const currentModelSpan = document.getElementById("currentModel");
const modelStatusText = document.getElementById("modelStatusText");
const typingIndicator = document.getElementById("typingIndicator");
const logoutBtn = document.getElementById("logoutBtn");
const displayUsername = document.getElementById("displayUsername");
const displayRole = document.getElementById("displayRole");
const profileAvatar = document.getElementById("profileAvatar");
const profileAvatarLarge = document.getElementById("profileAvatarLarge");
const profileFullName = document.getElementById("profileFullName");
const profileRoleFull = document.getElementById("profileRoleFull");
const profileEmail = document.getElementById("profileEmail");
const balanceList = document.getElementById("balanceList");
const ticketsList = document.getElementById("ticketsList");
const pendingList = document.getElementById("pendingList");
const refreshTicketsBtn = document.getElementById("refreshTicketsBtn");
const toastContainer = document.getElementById("toastContainer");

const STORAGE_KEYS = {
  sessionId: "rag.sessionId",
  model: "rag.model",
};

let isLoading = false;
let conversationHistory = [];
let messageCount = 0;

const ROLE_META = {
  employee:  { label: "Employee",   icon: "fa-user",            color: "#667eea" },
  manager:   { label: "Manager",    icon: "fa-user-tie",        color: "#8b5cf6" },
  hr:        { label: "HR Team",    icon: "fa-people-group",    color: "#ec4899" },
  it:        { label: "IT Team",    icon: "fa-laptop-code",     color: "#06b6d4" },
  finance:   { label: "Finance",    icon: "fa-coins",           color: "#f59e0b" },
  admin:     { label: "Admin",      icon: "fa-shield-halved",   color: "#ef4444" },
};

const LEAVE_TYPE_LABELS = {
  casual: "Casual Leave",
  sick: "Sick Leave",
  earned: "Earned Leave",
  comp_off: "Compensatory Off",
};

// ---- Initialize ----------------------------------------------------------

function init() {
  populateUserInfo();
  setDefaultIds();
  setupEventListeners();
  autoResizeTextarea();
  setupNavigation();
  loadLeaveBalances();
  loadITTickets();

  if (["hr", "manager", "admin"].includes(AUTH_ROLE)) {
    document.getElementById("pendingApprovalPanel").style.display = "block";
    loadPendingApprovals();
    setInterval(loadPendingApprovals, 15000);
  }

  setInterval(updateModelStatus, 5000);
}

// ---- User Info Population ------------------------------------------------

function populateUserInfo() {
  const meta = ROLE_META[AUTH_ROLE] || ROLE_META.employee;

  if (displayUsername) displayUsername.textContent = AUTH_USERNAME || "User";
  if (displayRole) displayRole.textContent = meta.label;
  if (profileFullName) profileFullName.textContent = AUTH_USERNAME || "User";
  if (profileRoleFull) profileRoleFull.textContent = meta.label;
  if (profileEmail) profileEmail.textContent = `${AUTH_USERNAME}@novigo.com`;

  // Update avatars
  [profileAvatar, profileAvatarLarge].forEach(avatar => {
    if (avatar) {
      avatar.innerHTML = `<i class="fas ${meta.icon}"></i>`;
      avatar.style.background = meta.color;
    }
  });
}

// ---- Navigation Setup ----------------------------------------------------

function setupNavigation() {
  document.querySelectorAll(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const view = tab.dataset.view;
      switchView(view);
    });
  });
}

function switchView(viewName) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`[data-view="${viewName}"]`)?.classList.add('active');
  
  document.querySelectorAll('.nav-panel').forEach(p => p.classList.remove('active'));
  document.getElementById(`${viewName}Panel`)?.classList.add('active');

  // Toggle main views
  const chatView = document.getElementById('chatMainView');
  const dashView = document.getElementById('dashboardMainView');
  
  if (viewName === 'dashboard') {
    if (chatView) chatView.style.display = 'none';
    if (dashView) dashView.style.display = 'block';
  } else {
    if (chatView) chatView.style.display = 'flex';
    if (dashView) dashView.style.display = 'none';
  }

  // Update header subtitle
  const subtitles = {
    chat: "Chat with AI agents for HR, IT & Finance",
    dashboard: "View your activity and statistics",
    profile: "Manage your profile and preferences",
    settings: "Configure your settings"
  };
  
  const headerSubtitle = document.getElementById("headerSubtitle");
  if (headerSubtitle) {
    headerSubtitle.textContent = subtitles[viewName] || "Novi Pilot";
  }
}

// ---- Event Listeners -----------------------------------------------------

function setupEventListeners() {
  sendBtn.addEventListener("click", handleSendMessage);
  clearBtn.addEventListener("click", () => {
    if (confirm("Clear chat history?")) {
      chatLog.innerHTML = `
        <div class="welcome-section">
          <div class="welcome-animation"><i class="fas fa-brain"></i></div>
          <h2>Welcome to Novi Pilot</h2>
          <p>Your intelligent assistant for HR, IT, and Finance operations</p>
        </div>
      `;
      conversationHistory = [];
      messageCount = 0;
    }
  });

  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  logoutBtn.addEventListener("click", logout);

  document.querySelectorAll(".quick-action-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const query = btn.dataset.query;
      messageInput.value = query;
      autoResizeTextarea();
      setTimeout(handleSendMessage, 100);
    });
  });

  if (refreshTicketsBtn) {
    refreshTicketsBtn.addEventListener("click", loadITTickets);
  }
}

// ---- Message Handling ----------------------------------------------------

async function handleSendMessage() {
  const query = messageInput.value.trim();
  if (!query || isLoading) return;

  messageInput.value = "";
  autoResizeTextarea();
  isLoading = true;

  const welcome = document.querySelector(".welcome-section");
  if (welcome) welcome.style.display = "none";

  appendMessage("user", query);
  showTypingIndicator(true);

  const sessionId = sessionIdInput.value;
  const modelPref = modelSelect.value;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + AUTH_TOKEN,
      },
      body: JSON.stringify({
        user_id: AUTH_USER_ID || AUTH_USERNAME,
        role: AUTH_ROLE,
        query: query,
        session_id: sessionId,
        model_preference: modelPref,
      }),
    });

    if (response.status === 401) {
      handleAuthExpired();
      return;
    }

    const data = await response.json();
    appendMessage("assistant", data.response);
    
    conversationHistory.push({ role: "user", query });
    conversationHistory.push({ role: "assistant", response: data.response });
    messageCount++;

    updateDashboardStats();

    if (data.trace_id) {
      console.log("Trace ID:", data.trace_id);
    }
  } catch (error) {
    showToast("Error: " + error.message, "error");
    appendMessage("assistant", "Error: Failed to get response. Please try again.");
  } finally {
    isLoading = false;
    showTypingIndicator(false);
  }
}

function appendMessage(role, text) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${role}`;
  
  const avatarDiv = document.createElement("div");
  avatarDiv.className = "message-avatar";
  
  if (role === "assistant") {
    avatarDiv.innerHTML = '<i class="fas fa-brain"></i>';
  } else {
    avatarDiv.innerHTML = '<i class="fas fa-user"></i>';
  }
  
  const contentDiv = document.createElement("div");
  contentDiv.className = "message-content";
  contentDiv.innerHTML = text.replace(/\n/g, "<br>");
  
  messageDiv.appendChild(avatarDiv);
  messageDiv.appendChild(contentDiv);
  
  chatLog.appendChild(messageDiv);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function showTypingIndicator(show) {
  typingIndicator.style.display = show ? "flex" : "none";
  if (show) {
    chatLog.scrollTop = chatLog.scrollHeight;
  }
}

// Dashboard panel removed — stats tracking kept in memory only
function updateDashboardStats() {
  // no-op — dashboard panel removed for enterprise simplification
}

// ---- Leave Balances ------------------------------------------------------

async function loadLeaveBalances() {
  try {
    const res = await fetch("/api/leaves/balance", {
      headers: { Authorization: "Bearer " + AUTH_TOKEN },
    });
    if (res.status === 401) return handleAuthExpired();
    const data = await res.json();

    if (!data.balance || Object.keys(data.balance).length === 0) {
      balanceList.innerHTML = '<p class="placeholder-text">No leave data available</p>';
      return;
    }

    balanceList.innerHTML = Object.entries(data.balance)
      .map(([type, dataObj]) => {
        const remaining = typeof dataObj === 'object' ? dataObj.remaining : dataObj;
        const total = typeof dataObj === 'object' ? dataObj.total : 12;
        return `
        <div class="balance-item">
          <div class="balance-header">
            <span class="balance-label">${LEAVE_TYPE_LABELS[type] || type}</span>
            <span class="balance-days">${remaining} days</span>
          </div>
          <div class="balance-bar">
            <div class="balance-fill" style="width: ${Math.min((remaining / total) * 100, 100)}%"></div>
          </div>
        </div>
      `})
      .join("");
  } catch (error) {
    balanceList.innerHTML = '<p class="placeholder-text">Error loading balance</p>';
  }
}

// ---- IT Tickets ----------------------------------------------------------

async function loadITTickets() {
  try {
    const res = await fetch("/api/tickets", {
      headers: { Authorization: "Bearer " + AUTH_TOKEN },
    });
    if (res.status === 401) return handleAuthExpired();
    const data = await res.json();

    const tickets = data.tickets || [];
    if (tickets.length === 0) {
      ticketsList.innerHTML = '<p class="placeholder-text">No tickets</p>';
      return;
    }

    ticketsList.innerHTML = tickets.slice(0, 5).map(ticket => `
      <div class="ticket-item">
        <div class="ticket-header">
          <span class="ticket-id">#${ticket.id}</span>
          <span class="ticket-priority priority-${ticket.priority || 'medium'}">${(ticket.priority || 'medium').toUpperCase()}</span>
        </div>
        <p class="ticket-description">${ticket.description || ticket.issue_type}</p>
        <span class="ticket-status">${ticket.status || 'open'}</span>
      </div>
    `).join("");
  } catch (error) {
    ticketsList.innerHTML = '<p class="placeholder-text">Error loading tickets</p>';
  }
}

// ---- Pending Approvals ---------------------------------------------------

async function loadPendingApprovals() {
  try {
    const res = await fetch("/api/approvals/pending", {
      headers: { Authorization: "Bearer " + AUTH_TOKEN },
    });
    if (res.status === 401) return handleAuthExpired();
    const data = await res.json();

    const approvals = data.approvals || [];
    if (approvals.length === 0) {
      pendingList.innerHTML = '<p class="placeholder-text">✅ No pending approvals</p>';
      return;
    }

    pendingList.innerHTML = approvals.slice(0, 3).map(approval => `
      <div class="approval-card">
        <div class="approval-header">
          <span class="approval-id">#${approval.id}</span>
          <span class="approval-type">${approval.request_type}</span>
        </div>
        <p class="approval-details">${approval.request_type === 'leave' ? 
          `Leave: ${approval.leave_details?.leave_type || 'Unknown'}` : 
          `Ticket: ${approval.ticket_details?.issue_type || 'Support'}`}</p>
      </div>
    `).join("");
  } catch (error) {
    console.error("Failed to load approvals:", error);
  }
}

// ---- Utility Functions ---------------------------------------------------

function autoResizeTextarea() {
  messageInput.style.height = "auto";
  messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + "px";
}

function setDefaultIds() {
  let sessionId = localStorage.getItem(STORAGE_KEYS.sessionId);
  if (!sessionId) {
    sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem(STORAGE_KEYS.sessionId, sessionId);
  }
  sessionIdInput.value = sessionId;

  const savedModel = localStorage.getItem(STORAGE_KEYS.model);
  if (savedModel) {
    modelSelect.value = savedModel;
  }
}

function updateModelStatus() {
  const model = modelSelect.value;
  currentModelSpan.textContent = model === "gemini" ? "Gemini" : "Groq Llama 3.3";
  modelStatusText.textContent = "Ready";
  modelStatusText.className = "status-ready";
}

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  toastContainer.appendChild(toast);
  
  setTimeout(() => {
    toast.remove();
  }, 3000);
}

function handleAuthExpired() {
  localStorage.clear();
  window.location.href = "/";
}

function logout() {
  if (confirm("Sign out?")) {
    localStorage.clear();
    window.location.href = "/";
  }
}

// ---- Start ---

init();
