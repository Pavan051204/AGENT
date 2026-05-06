// ===========================================================================
// Enterprise AI Copilot — Chat UI (Authenticated)
// Full leave management with adaptive cards, HR picker, and approval panel
// ===========================================================================

// ---- Auth guard ----------------------------------------------------------

const AUTH_TOKEN = localStorage.getItem("auth.token");
const AUTH_USERNAME = localStorage.getItem("auth.username");
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
const userAvatar = document.getElementById("userAvatar");
const pendingTabBtn = document.getElementById("pendingTabBtn");
const pendingBadge = document.getElementById("pendingBadge");
const pendingList = document.getElementById("pendingList");
const balanceList = document.getElementById("balanceList");
const refreshPendingBtn = document.getElementById("refreshPendingBtn");
const toastContainer = document.getElementById("toastContainer");

// ---- Storage Keys --------------------------------------------------------

const STORAGE_KEYS = {
  sessionId: "rag.sessionId",
  model: "rag.model",
};

// ---- State ---------------------------------------------------------------

let isLoading = false;
let conversationHistory = [];
let cachedHrUsers = [];

// ---- Role meta -----------------------------------------------------------

const ROLE_META = {
  employee:  { label: "Employee",   icon: "fa-user",        color: "#6366f1" },
  manager:   { label: "Manager",    icon: "fa-user-tie",    color: "#8b5cf6" },
  hr:        { label: "HR Team",    icon: "fa-people-group", color: "#ec4899" },
  it:        { label: "IT Team",    icon: "fa-laptop-code", color: "#06b6d4" },
  finance:   { label: "Finance",    icon: "fa-coins",       color: "#f59e0b" },
  admin:     { label: "Admin",      icon: "fa-shield-halved", color: "#ef4444" },
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
  setupSidebarTabs();
  loadHrUsers();
  loadLeaveBalances();

  // Show pending tab for HR/Manager/Admin
  if (["hr", "manager", "admin"].includes(AUTH_ROLE)) {
    pendingTabBtn.style.display = "";
    loadPendingApprovals();
    setInterval(loadPendingApprovals, 15000); // Auto-refresh every 15s
  }

  setInterval(updateModelStatus, 5000);
}

function populateUserInfo() {
  const meta = ROLE_META[AUTH_ROLE] || ROLE_META.employee;

  if (displayUsername) displayUsername.textContent = AUTH_USERNAME || "User";
  if (displayRole) {
    displayRole.textContent = meta.label;
    displayRole.style.background = meta.color + "22";
    displayRole.style.color = meta.color;
  }
  if (userAvatar) {
    userAvatar.innerHTML = `<i class="fas ${meta.icon}"></i>`;
    userAvatar.style.background = meta.color + "22";
    userAvatar.style.color = meta.color;
  }
}

// ---- Sidebar Tabs --------------------------------------------------------

function setupSidebarTabs() {
  document.querySelectorAll(".sidebar-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const panel = tab.dataset.panel;

      document.querySelectorAll(".sidebar-tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".sidebar-panel").forEach((p) => p.classList.remove("active"));

      tab.classList.add("active");
      const targetPanel = document.getElementById(panel + "Panel");
      if (targetPanel) targetPanel.classList.add("active");

      // Refresh data when panel is activated
      if (panel === "pending") loadPendingApprovals();
      if (panel === "balance") loadLeaveBalances();
    });
  });
}

// ---- Pending Approvals (HR/Manager/Admin) --------------------------------

async function loadPendingApprovals() {
  try {
    const res = await fetch("/api/approvals/pending", {
      headers: { Authorization: "Bearer " + AUTH_TOKEN },
    });
    if (res.status === 401) return handleAuthExpired();
    const data = await res.json();

    if (data.error) {
      pendingList.innerHTML = `<p class="pending-empty">${data.error}</p>`;
      return;
    }

    const approvals = data.approvals || [];

    // Update badge
    if (approvals.length > 0) {
      pendingBadge.textContent = approvals.length;
      pendingBadge.style.display = "";
    } else {
      pendingBadge.style.display = "none";
    }

    if (approvals.length === 0) {
      pendingList.innerHTML = '<p class="pending-empty">✅ No pending approvals</p>';
      return;
    }

    pendingList.innerHTML = approvals.map((a) => {
      const leave = a.leave_details || {};
      const leaveType = leave.leave_type || "casual";
      return `
        <div class="pending-card" id="pending-${a.id}">
          <div class="pending-card-header">
            <span class="pending-card-id">#${a.id}</span>
            <span class="pending-card-type">${a.request_type || "leave"}</span>
          </div>
          <div class="pending-card-info">
            <strong>Employee:</strong> ${leave.user_id || "N/A"}<br>
            <strong>Type:</strong> ${LEAVE_TYPE_LABELS[leaveType] || leaveType}<br>
            <strong>Dates:</strong> ${leave.start_date || "?"} → ${leave.end_date || "?"}<br>
            <strong>Reason:</strong> ${leave.reason || "Not specified"}
          </div>
          <div class="pending-card-actions">
            <button class="approve-btn" onclick="handleApproval(${a.id}, 'approved')">
              <i class="fas fa-check"></i> Approve
            </button>
            <button class="reject-btn" onclick="handleApproval(${a.id}, 'rejected')">
              <i class="fas fa-times"></i> Reject
            </button>
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    pendingList.innerHTML = `<p class="pending-empty">Error loading approvals</p>`;
  }
}

async function handleApproval(approvalId, status) {
  const card = document.getElementById(`pending-${approvalId}`);
  const buttons = card?.querySelectorAll("button");
  buttons?.forEach((b) => (b.disabled = true));

  try {
    const res = await fetch(`/api/approvals/${approvalId}/decide`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + AUTH_TOKEN,
      },
      body: JSON.stringify({ status }),
    });

    if (res.status === 401) return handleAuthExpired();
    const data = await res.json();

    if (data.error) {
      showToast(data.error, "error");
      buttons?.forEach((b) => (b.disabled = false));
      return;
    }

    showToast(
      `Leave ${status === "approved" ? "approved ✅" : "rejected ❌"} by ${data.approved_by}`,
      status === "approved" ? "success" : "error"
    );

    // Remove the card with animation
    if (card) {
      card.style.opacity = "0";
      card.style.transform = "translateX(-20px)";
      card.style.transition = "all 0.3s";
      setTimeout(() => {
        card.remove();
        loadPendingApprovals(); // Refresh
      }, 300);
    }
  } catch (err) {
    showToast("Error processing approval", "error");
    buttons?.forEach((b) => (b.disabled = false));
  }
}

// ---- Leave Balances Panel ------------------------------------------------

async function loadLeaveBalances() {
  try {
    const res = await fetch("/api/leaves/balance", {
      headers: { Authorization: "Bearer " + AUTH_TOKEN },
    });
    if (res.status === 401) return handleAuthExpired();
    const data = await res.json();

    const balance = data.balance;
    if (!balance || typeof balance !== "object") {
      balanceList.innerHTML = '<p class="pending-empty">No balance data available</p>';
      return;
    }

    const typeOrder = ["casual", "sick", "earned", "comp_off"];
    const typeColors = {
      casual: "#6366f1",
      sick: "#ef4444",
      earned: "#10b981",
      comp_off: "#f59e0b",
    };

    balanceList.innerHTML = typeOrder
      .filter((t) => balance[t])
      .map((t) => {
        const info = balance[t];
        const pct = info.total > 0 ? (info.remaining / info.total) * 100 : 0;
        const barClass = pct > 50 ? "high" : pct > 20 ? "medium" : "low";
        return `
          <div class="balance-card">
            <div class="balance-card-header">
              <span class="balance-card-type">${LEAVE_TYPE_LABELS[t] || t}</span>
              <span class="balance-card-count">${info.remaining}/${info.total}</span>
            </div>
            <div class="balance-bar">
              <div class="balance-bar-fill ${barClass}" style="width: ${pct}%; background: ${typeColors[t]}"></div>
            </div>
          </div>
        `;
      })
      .join("");
  } catch {
    balanceList.innerHTML = '<p class="pending-empty">Error loading balances</p>';
  }
}

// ---- HR Users Cache ------------------------------------------------------

async function loadHrUsers() {
  try {
    const res = await fetch("/api/hr-users");
    const data = await res.json();
    cachedHrUsers = data.hr_users || [];
  } catch {
    cachedHrUsers = [];
  }
}

// ---- Default IDs ---------------------------------------------------------

function setDefaultIds() {
  const storedSession = localStorage.getItem(STORAGE_KEYS.sessionId);
  const storedModel = localStorage.getItem(STORAGE_KEYS.model);

  if (sessionIdInput) {
    sessionIdInput.value = storedSession || `session-${crypto.randomUUID().slice(0, 8)}`;
  }
  if (modelSelect) {
    modelSelect.value = storedModel || "gemini";
  }
  persistInputs();
}

function persistInputs() {
  if (sessionIdInput) localStorage.setItem(STORAGE_KEYS.sessionId, sessionIdInput.value.trim());
  if (modelSelect) localStorage.setItem(STORAGE_KEYS.model, modelSelect.value);
}

// ---- Model Status --------------------------------------------------------

function updateModelStatus() {
  const label = modelSelect?.value === "groq" ? "🟣 Groq Llama 3.3" : "🔵 Gemini";
  if (currentModelSpan) currentModelSpan.textContent = label;
  if (modelStatusText) modelStatusText.textContent = "Ready";
}

// ---- Chat Bubbles --------------------------------------------------------

function createBubble(text, type, meta) {
  const wrapper = document.createElement("div");
  wrapper.className = `chat-bubble ${type}`;

  const content = document.createElement("div");
  if (type === "agent") {
    content.innerHTML = parseMessageContent(text);
  } else {
    content.textContent = text;
  }
  wrapper.appendChild(content);

  if (meta) {
    const metaEl = document.createElement("div");
    metaEl.className = "chat-meta";
    metaEl.textContent = meta;
    wrapper.appendChild(metaEl);
  }

  return wrapper;
}

function parseMessageContent(text) {
  // Convert markdown-style formatting
  let html = text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");

  // Convert markdown tables to HTML tables
  html = convertMarkdownTables(html);

  return html;
}

function convertMarkdownTables(html) {
  // Simple markdown table conversion
  const lines = html.split("<br>");
  let inTable = false;
  let tableHtml = "";
  const result = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      if (trimmed.replace(/[|\-\s]/g, "") === "") {
        // Separator row — skip
        continue;
      }
      if (!inTable) {
        inTable = true;
        tableHtml = '<table style="border-collapse:collapse;width:100%;font-size:12px;margin:8px 0;">';
        // First row is header
        const cells = trimmed.split("|").filter(Boolean).map((c) => c.trim());
        tableHtml += "<tr>" + cells.map((c) =>
          `<th style="border:1px solid #e2e8f0;padding:6px 8px;background:#f0f4ff;text-align:left;font-weight:600;">${c}</th>`
        ).join("") + "</tr>";
      } else {
        const cells = trimmed.split("|").filter(Boolean).map((c) => c.trim());
        tableHtml += "<tr>" + cells.map((c) =>
          `<td style="border:1px solid #e2e8f0;padding:5px 8px;">${c}</td>`
        ).join("") + "</tr>";
      }
    } else {
      if (inTable) {
        tableHtml += "</table>";
        result.push(tableHtml);
        tableHtml = "";
        inTable = false;
      }
      result.push(line);
    }
  }
  if (inTable) {
    tableHtml += "</table>";
    result.push(tableHtml);
  }
  return result.join("<br>");
}

function addMessage(text, type, meta, toolCalls) {
  const bubble = createBubble(text, type, meta);

  // Render adaptive cards if present
  if (toolCalls && type === "agent") {
    for (const tc of toolCalls) {
      if (tc.type === "adaptive_card") {
        const card = renderAdaptiveCard(tc);
        if (card) bubble.appendChild(card);
      }
    }
  }

  chatLog.appendChild(bubble);
  conversationHistory.push({ text, type, meta, timestamp: new Date() });
  chatLog.scrollTop = chatLog.scrollHeight;
}

// ---- Adaptive Cards (Interactive Dropdowns) ------------------------------

function renderAdaptiveCard(toolCall) {
  const { card_type, data } = toolCall;

  if (card_type === "leave_form") {
    return buildLeaveFormCard(data);
  }
  if (card_type === "hr_picker") {
    return buildHrPickerCard(data);
  }
  if (card_type === "show_pending_tab") {
    // Auto-switch to pending tab
    if (pendingTabBtn) pendingTabBtn.click();
    return null;
  }
  return null;
}

function buildLeaveFormCard(data) {
  const card = document.createElement("div");
  card.className = "adaptive-card";

  const hrOptions = (data.hr_users || cachedHrUsers)
    .map((h) => `<option value="${h.username}">${h.username}</option>`)
    .join("");

  const typeOptions = Object.entries(LEAVE_TYPE_LABELS)
    .map(([val, label]) => `<option value="${val}">${label}</option>`)
    .join("");

  card.innerHTML = `
    <div class="adaptive-card-title">
      <i class="fas fa-calendar-plus"></i> Apply for Leave
    </div>
    <div class="form-group">
      <label>Leave Type</label>
      <select id="card-leave-type">${typeOptions}</select>
    </div>
    <div class="form-group">
      <label>Start Date</label>
      <input type="date" id="card-start-date" />
    </div>
    <div class="form-group">
      <label>End Date</label>
      <input type="date" id="card-end-date" />
    </div>
    <div class="form-group">
      <label>Reason</label>
      <input type="text" id="card-reason" placeholder="e.g. Family function" />
    </div>
    <div class="form-group">
      <label>Assign to HR</label>
      <select id="card-hr-select">
        <option value="">-- Select HR --</option>
        ${hrOptions}
      </select>
    </div>
    <button class="adaptive-card-submit" onclick="submitLeaveCard()">
      <i class="fas fa-paper-plane"></i> Submit Leave Request
    </button>
  `;

  return card;
}

function buildHrPickerCard(data) {
  const card = document.createElement("div");
  card.className = "adaptive-card";

  const hrOptions = (data.hr_users || cachedHrUsers)
    .map((h) => `<option value="${h.username}">${h.username}</option>`)
    .join("");

  card.innerHTML = `
    <div class="adaptive-card-title">
      <i class="fas fa-user-check"></i> Select HR for Approval
    </div>
    <div class="form-group">
      <label>Leave: ${LEAVE_TYPE_LABELS[data.leave_type] || data.leave_type}</label>
      <p style="font-size:12px;color:#64748b;margin-top:2px;">
        ${data.start_date} → ${data.end_date} (${data.working_days} working days)
      </p>
    </div>
    <div class="form-group">
      <label>Send approval request to:</label>
      <select id="card-hr-picker">
        <option value="">-- Choose HR --</option>
        ${hrOptions}
      </select>
    </div>
    <button class="adaptive-card-submit" onclick="submitHrPicker('${data.leave_type}', '${data.start_date}', '${data.end_date}', '${data.reason || ""}')">
      <i class="fas fa-paper-plane"></i> Submit
    </button>
  `;

  return card;
}

function submitLeaveCard() {
  const leaveType = document.getElementById("card-leave-type")?.value || "casual";
  const startDate = document.getElementById("card-start-date")?.value;
  const endDate = document.getElementById("card-end-date")?.value;
  const reason = document.getElementById("card-reason")?.value || "";
  const hr = document.getElementById("card-hr-select")?.value || "";

  if (!startDate || !endDate) {
    showToast("Please select start and end dates", "error");
    return;
  }

  let msg = `Apply ${leaveType} leave from ${startDate} to ${endDate}`;
  if (reason) msg += ` for ${reason}`;
  if (hr) msg += ` hr ${hr}`;

  messageInput.value = msg;
  sendMessage();
}

function submitHrPicker(leaveType, startDate, endDate, reason) {
  const hr = document.getElementById("card-hr-picker")?.value;
  if (!hr) {
    showToast("Please select an HR person", "error");
    return;
  }

  let msg = `Apply ${leaveType} leave from ${startDate} to ${endDate}`;
  if (reason) msg += ` for ${reason}`;
  msg += ` hr ${hr}`;

  messageInput.value = msg;
  sendMessage();
}

// ---- Send Message --------------------------------------------------------

async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || isLoading) return;

  persistInputs();
  addMessage(text, "user", getTimestamp());
  messageInput.value = "";
  autoResizeTextarea();

  const payload = {
    user_id: AUTH_USERNAME,
    role: AUTH_ROLE,
    query: text,
    session_id: sessionIdInput.value.trim(),
    model_preference: modelSelect.value,
  };

  isLoading = true;
  if (sendBtn) sendBtn.disabled = true;
  if (typingIndicator) typingIndicator.style.display = "flex";

  const startTime = performance.now();

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + AUTH_TOKEN,
      },
      body: JSON.stringify(payload),
    });

    const responseTime = performance.now() - startTime;

    if (response.status === 401) return handleAuthExpired();
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    if (typingIndicator) typingIndicator.style.display = "none";

    const modelName = data.model_used || "Unknown";
    let meta = `${getTimestamp()} | ${modelName} | ${Math.round(responseTime)}ms`;
    if (data.trace_id) {
      meta += ` | ${data.trace_id.slice(0, 12)}`;
    }

    // Extract tool_calls from response if present
    // The agent may include adaptive card data
    let toolCalls = null;
    // Check if the response contains card hints
    if (data.response && data.response.includes("Apply") && data.response.includes("leave")) {
      // If HR users available and response asks to select HR, show picker card
      if (data.response.includes("Select HR") || data.response.includes("select an HR") ||
          data.response.includes("Available HR")) {
        toolCalls = [{
          type: "adaptive_card",
          card_type: "leave_form",
          data: { hr_users: cachedHrUsers, balance: {} }
        }];
      }
    }

    addMessage(data.response, "agent", meta, toolCalls);

    // Refresh balances after leave operations
    if (text.toLowerCase().includes("leave")) {
      loadLeaveBalances();
    }
  } catch (error) {
    if (typingIndicator) typingIndicator.style.display = "none";
    addMessage(`Error: ${error.message}`, "agent", "Error");
  } finally {
    isLoading = false;
    if (sendBtn) sendBtn.disabled = false;
    messageInput.focus();
    updateModelStatus();
  }
}

// ---- Quick Actions -------------------------------------------------------

function handleQuickAction(query) {
  messageInput.value = query;
  sendMessage();
}

// ---- Clear Chat ----------------------------------------------------------

function clearChat() {
  if (conversationHistory.length === 0) return;
  const confirmed = confirm("Clear all messages?");
  if (confirmed) {
    chatLog.innerHTML = `
      <div class="welcome-message">
        <div class="welcome-icon"><i class="fas fa-brain"></i></div>
        <h2>Multi-Agent AI Assistant</h2>
        <p>Ask about company policies, apply for leave, raise IT tickets, or check finance queries.</p>
        <div class="quick-actions" id="quickActions">
          <button class="quick-btn" data-query="Check leave balance">📊 Leave Balance</button>
          <button class="quick-btn" data-query="Show holiday calendar">📅 Holidays</button>
          <button class="quick-btn" data-query="Show leave history">📋 Leave History</button>
          <button class="quick-btn" data-query="What is the notice period policy?">📄 Policies</button>
        </div>
      </div>
    `;
    conversationHistory = [];
    // Re-bind quick action buttons
    document.querySelectorAll(".quick-btn").forEach((btn) => {
      btn.addEventListener("click", () => handleQuickAction(btn.dataset.query));
    });
  }
}

// ---- Logout / Auth -------------------------------------------------------

function logout() {
  localStorage.removeItem("auth.token");
  localStorage.removeItem("auth.username");
  localStorage.removeItem("auth.role");
  window.location.href = "/";
}

function handleAuthExpired() {
  localStorage.removeItem("auth.token");
  localStorage.removeItem("auth.username");
  localStorage.removeItem("auth.role");
  window.location.href = "/";
}

// ---- Toast Notifications -------------------------------------------------

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(20px)";
    toast.style.transition = "all 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

function getTimestamp() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// ---- Auto-resize Textarea -----------------------------------------------

function autoResizeTextarea() {
  messageInput.style.height = "auto";
  messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + "px";
}

// ---- Event Listeners -----------------------------------------------------

function setupEventListeners() {
  if (sendBtn) sendBtn.addEventListener("click", sendMessage);
  if (clearBtn) clearBtn.addEventListener("click", clearChat);
  if (logoutBtn) logoutBtn.addEventListener("click", logout);
  if (refreshPendingBtn) refreshPendingBtn.addEventListener("click", loadPendingApprovals);

  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  messageInput.addEventListener("input", autoResizeTextarea);

  [sessionIdInput, modelSelect].forEach((input) => {
    if (!input) return;
    input.addEventListener("change", persistInputs);
  });

  // Quick action buttons
  document.querySelectorAll(".quick-btn").forEach((btn) => {
    btn.addEventListener("click", () => handleQuickAction(btn.dataset.query));
  });
}

// ---- Boot ----------------------------------------------------------------

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
