// ===========================================================================
// NOVI PILOT — Enterprise Dashboard with Adaptive Cards
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
const balanceList = document.getElementById("balanceList");
const ticketsList = document.getElementById("ticketsList");
const pendingList = document.getElementById("pendingList");
const refreshTicketsBtn = document.getElementById("refreshTicketsBtn");
const toastContainer = document.getElementById("toastContainer");
const dashEmail = document.getElementById("dashProfileEmail");

const STORAGE_KEYS = {
  sessionId: "rag.sessionId",
  model: "rag.model",
};

let isLoading = false;
let conversationHistory = [];
let messageCount = 0;

const ROLE_META = {
  employee: { label: "Employee", icon: "fa-user", color: "#667eea" },
  manager: { label: "Manager", icon: "fa-user-tie", color: "#8b5cf6" },
  hr: { label: "HR Team", icon: "fa-people-group", color: "#ec4899" },
  it: { label: "IT Team", icon: "fa-laptop-code", color: "#06b6d4" },
  finance: { label: "Finance", icon: "fa-coins", color: "#f59e0b" },
  admin: { label: "Admin", icon: "fa-shield-halved", color: "#ef4444" },
};

const LEAVE_TYPE_LABELS = {
  casual: "Casual Leave",
  sick: "Sick Leave",
  earned: "Earned Leave",
  comp_off: "Compensatory Off",
};

// ---- Role-specific Quick Action Prompts ----------------------------------

const ROLE_QUICK_ACTIONS = {
  employee: [
    { icon: "fa-calendar-plus", label: "Apply Leave", query: "I want to apply for leave" },
    { icon: "fa-chart-pie", label: "Leave Balance", query: "Check leave balance" },
    { icon: "fa-clock-rotate-left", label: "Leave History", query: "Show leave history" },
    { icon: "fa-calendar", label: "Holidays", query: "Show holiday calendar" },
    { icon: "fa-plus-circle", label: "Raise Ticket", query: "Raise a ticket for VPN issue" },
    { icon: "fa-list", label: "My Tickets", query: "Show my tickets" },
    { icon: "fa-book", label: "Policies", query: "What is the notice period policy?" },
    { icon: "fa-laptop", label: "Request Asset", query: "I want to request a laptop" },
  ],
  hr: [
    { icon: "fa-clipboard-check", label: "Pending Approvals", query: "Show pending leave approvals" },
    { icon: "fa-users", label: "All Leaves", query: "Show all leave requests" },
    { icon: "fa-check-double", label: "Approve All Leaves", query: "Approve all pending leaves" },
    { icon: "fa-calendar", label: "Holidays", query: "Show holiday calendar" },
    { icon: "fa-chart-pie", label: "My Balance", query: "Check leave balance" },
    { icon: "fa-calendar-plus", label: "Apply Leave", query: "I want to apply for leave" },
    { icon: "fa-book", label: "Policies", query: "What is the leave policy?" },
    { icon: "fa-file-lines", label: "HR Guidelines", query: "Show work from home policy" },
  ],
  it: [
    { icon: "fa-ticket", label: "All Tickets", query: "Show all IT tickets" },
    { icon: "fa-check-circle", label: "Resolve Tickets", query: "Resolve all open tickets" },
    { icon: "fa-triangle-exclamation", label: "Check Outages", query: "Check current outages" },
    { icon: "fa-wrench", label: "Maintenance", query: "Check maintenance schedule" },
    { icon: "fa-warehouse", label: "Inventory", query: "Check IT inventory" },
    { icon: "fa-box", label: "Asset Requests", query: "Show all asset requests" },
    { icon: "fa-plus-circle", label: "Raise Ticket", query: "Raise a ticket for network issue" },
    { icon: "fa-book", label: "Policies", query: "What is the IT security policy?" },
  ],
  finance: [
    { icon: "fa-receipt", label: "My Payslip", query: "Show my payslip" },
    { icon: "fa-money-bill-wave", label: "Reimbursement", query: "Submit reimbursement claim for 2000" },
    { icon: "fa-chart-pie", label: "Leave Balance", query: "Check leave balance" },
    { icon: "fa-calendar-plus", label: "Apply Leave", query: "I want to apply for leave" },
    { icon: "fa-plus-circle", label: "Raise Ticket", query: "Raise a ticket for software issue" },
    { icon: "fa-book", label: "Policies", query: "What is the reimbursement policy?" },
  ],
  manager: [
    { icon: "fa-clipboard-check", label: "Pending Approvals", query: "Show pending leave approvals" },
    { icon: "fa-users", label: "Team Leaves", query: "Show all leave requests" },
    { icon: "fa-chart-pie", label: "My Balance", query: "Check leave balance" },
    { icon: "fa-calendar-plus", label: "Apply Leave", query: "I want to apply for leave" },
    { icon: "fa-calendar", label: "Holidays", query: "Show holiday calendar" },
    { icon: "fa-plus-circle", label: "Raise Ticket", query: "Raise a ticket for laptop issue" },
    { icon: "fa-list", label: "My Tickets", query: "Show my tickets" },
    { icon: "fa-book", label: "Policies", query: "What is the appraisal policy?" },
  ],
  admin: [
    { icon: "fa-clipboard-check", label: "Pending Approvals", query: "Show pending leave approvals" },
    { icon: "fa-users", label: "All Leaves", query: "Show all leave requests" },
    { icon: "fa-ticket", label: "All Tickets", query: "Show all IT tickets" },
    { icon: "fa-check-circle", label: "Resolve Tickets", query: "Resolve all open tickets" },
    { icon: "fa-warehouse", label: "Inventory", query: "Check IT inventory" },
    { icon: "fa-box", label: "Asset Requests", query: "Show all asset requests" },
    { icon: "fa-chart-pie", label: "Leave Balance", query: "Check leave balance" },
    { icon: "fa-book", label: "Policies", query: "What is the company code of conduct?" },
  ],
};

function getQuickActionsHTML() {
  const actions = ROLE_QUICK_ACTIONS[AUTH_ROLE] || ROLE_QUICK_ACTIONS.employee;
  return actions
    .map(a => `<button class="quick-action-btn" data-query="${a.query}"><i class="fas ${a.icon}"></i> ${a.label}</button>`)
    .join("");
}

const ROLE_WELCOME_TEXT = {
  employee: "Your intelligent assistant for HR, IT, and Finance operations",
  hr: "Manage leave approvals, employee requests, and HR operations",
  it: "Manage tickets, assets, outages, and IT infrastructure",
  finance: "Handle payslips, reimbursements, and financial operations",
  manager: "Oversee team leaves, approvals, and operations",
  admin: "Full access to all enterprise operations and management",
};

function populateQuickActions() {
  const container = document.getElementById("quickActions");
  if (!container) return;

  // Always force populate with role-specific buttons
  container.innerHTML = getQuickActionsHTML();

  // Update welcome subtitle based on role
  const welcomeP = container.closest(".welcome-section")?.querySelector("p");
  if (welcomeP) {
    welcomeP.textContent = ROLE_WELCOME_TEXT[AUTH_ROLE] || ROLE_WELCOME_TEXT.employee;
  }

  // Bind click handlers using event delegation on the container
  container.addEventListener("click", (e) => {
    const btn = e.target.closest(".quick-action-btn");
    if (!btn) return;
    const query = btn.getAttribute("data-query");
    if (query) {
      messageInput.value = query;
      handleSendMessage();
    }
  });
}

// Alias for backwards compat
function bindQuickActions() {
  populateQuickActions();
}

// ---- Dashboard Role Configuration ----------------------------------------

const DASHBOARD_CONFIG = {
  employee: {
    title: "My Dashboard",
    subtitle: "Your personal leave, tickets, and requests at a glance.",
    show: ["leaveBalanceCard", "itTicketsCard", "leaveHistoryCard", "assetRequestsCard", "profileSettingsCard"],
    hide: ["pendingApprovalPanel"],
  },
  hr: {
    title: "HR Dashboard",
    subtitle: "Manage employee leaves, approvals, and HR operations.",
    show: ["leaveBalanceCard", "pendingApprovalPanel", "leaveHistoryCard", "profileSettingsCard"],
    hide: ["itTicketsCard", "assetRequestsCard"],
  },
  it: {
    title: "IT Operations Dashboard",
    subtitle: "Manage tickets, assets, outages, and infrastructure.",
    show: ["itTicketsCard", "pendingApprovalPanel", "assetRequestsCard", "profileSettingsCard"],
    hide: ["leaveBalanceCard", "leaveHistoryCard"],
  },
  finance: {
    title: "Finance Dashboard",
    subtitle: "Track reimbursements, payslips, and financial operations.",
    show: ["leaveBalanceCard", "leaveHistoryCard", "itTicketsCard", "profileSettingsCard"],
    hide: ["pendingApprovalPanel", "assetRequestsCard"],
  },
  manager: {
    title: "Manager Dashboard",
    subtitle: "Oversee team operations, approvals, and requests.",
    show: ["leaveBalanceCard", "pendingApprovalPanel", "leaveHistoryCard", "itTicketsCard", "assetRequestsCard", "profileSettingsCard"],
    hide: [],
  },
  admin: {
    title: "Admin Dashboard",
    subtitle: "Full enterprise overview — all operations and management.",
    show: ["leaveBalanceCard", "pendingApprovalPanel", "itTicketsCard", "leaveHistoryCard", "assetRequestsCard", "profileSettingsCard"],
    hide: [],
  },
};

function configureDashboardForRole() {
  const config = DASHBOARD_CONFIG[AUTH_ROLE] || DASHBOARD_CONFIG.employee;

  // Update dashboard header
  const dashHeader = document.querySelector("#dashboardMainView header h1");
  const dashSubtitle = document.querySelector("#dashboardMainView header p");
  if (dashHeader) dashHeader.innerHTML = `<i class="fas fa-chart-pie" style="margin-right:8px;"></i> ${config.title}`;
  if (dashSubtitle) dashSubtitle.textContent = config.subtitle;

  // Show specified cards
  for (const id of config.show) {
    const el = document.getElementById(id);
    if (el) el.style.display = id === "pendingApprovalPanel" || el.style.gridColumn ? "block" : "";
  }

  // Hide specified cards
  for (const id of config.hide) {
    const el = document.getElementById(id);
    if (el) el.style.display = "none";
  }

  // Role-specific card title updates
  if (AUTH_ROLE === "hr") {
    const leaveTitle = document.getElementById("leaveBalanceTitle");
    if (leaveTitle) leaveTitle.innerHTML = '<i class="fas fa-users"></i> Company Leaves Overview';
    const histTitle = document.querySelector("#leaveHistoryCard .panel-title");
    if (histTitle) histTitle.innerHTML = '<i class="fas fa-clock-rotate-left"></i> All Employee Leaves';
  } else if (AUTH_ROLE === "it") {
    const ticketTitle = document.getElementById("itTicketsTitle");
    if (ticketTitle) ticketTitle.innerHTML = '<i class="fas fa-ticket"></i> All IT Tickets';
    const assetTitle = document.querySelector("#assetRequestsCard .panel-title");
    if (assetTitle) assetTitle.innerHTML = '<i class="fas fa-box"></i> All Asset Requests';
  } else if (AUTH_ROLE === "admin") {
    const leaveTitle = document.getElementById("leaveBalanceTitle");
    if (leaveTitle) leaveTitle.innerHTML = '<i class="fas fa-users"></i> Company Leaves Overview';
    const ticketTitle = document.getElementById("itTicketsTitle");
    if (ticketTitle) ticketTitle.innerHTML = '<i class="fas fa-ticket"></i> All IT Tickets';
    const histTitle = document.querySelector("#leaveHistoryCard .panel-title");
    if (histTitle) histTitle.innerHTML = '<i class="fas fa-clock-rotate-left"></i> All Employee Leaves';
  }
}

// ---- Initialize ----------------------------------------------------------

function init() {
  populateUserInfo();
  setDefaultIds();
  setupEventListeners();
  autoResizeTextarea();
  setupNavigation();

  // Populate role-specific quick action buttons
  populateQuickActions();

  // ── Role-specific dashboard customization ──────────────────────────
  configureDashboardForRole();

  loadLeaveBalances();
  loadITTickets();
  loadLeaveHistory();
  loadAssetRequests();

  const refreshBtn = document.getElementById("refreshTicketsBtn");
  if (refreshBtn) refreshBtn.addEventListener("click", loadITTickets);

  const refreshLeavesBtn = document.getElementById("refreshLeavesBtn");
  if (refreshLeavesBtn) refreshLeavesBtn.addEventListener("click", loadLeaveHistory);

  // Load pending approvals for roles that manage them
  if (["hr", "manager", "admin", "it"].includes(AUTH_ROLE)) {
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

  const dashName = document.getElementById("dashProfileName");
  const dashRole = document.getElementById("dashProfileRole");
  if (dashName) dashName.textContent = AUTH_USERNAME || "User";
  if (dashRole) dashRole.textContent = meta.label;
  
  // Show email — try localStorage first, then fallback to /auth/me
  const cachedEmail = localStorage.getItem("auth.email");
  if (dashEmail) {
    if (cachedEmail) {
      dashEmail.textContent = cachedEmail;
    } else {
      dashEmail.textContent = "";
      fetch("/auth/me", { headers: { Authorization: "Bearer " + AUTH_TOKEN } })
        .then(r => r.json())
        .then(data => {
          const email = data.email || "";
          dashEmail.textContent = email;
          localStorage.setItem("auth.email", email);
        })
        .catch(() => {});
    }
  }

  if (profileAvatar) {
    profileAvatar.innerHTML = `<i class="fas ${meta.icon}"></i>`;
    profileAvatar.style.background = meta.color;
  }
}

// ---- Navigation Setup ----------------------------------------------------

function setupNavigation() {
  document.querySelectorAll(".nav-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      switchView(tab.dataset.view);
    });
  });
}

function switchView(viewName) {
  document.querySelectorAll(".nav-tab").forEach((t) => t.classList.remove("active"));
  document.querySelector(`[data-view="${viewName}"]`)?.classList.add("active");
  document.querySelectorAll(".nav-panel").forEach((p) => p.classList.remove("active"));
  document.getElementById(`${viewName}Panel`)?.classList.add("active");

  const chatView = document.getElementById("chatMainView");
  const dashView = document.getElementById("dashboardMainView");

  if (viewName === "dashboard") {
    if (chatView) chatView.style.display = "none";
    if (dashView) dashView.style.display = "block";
  } else {
    if (chatView) chatView.style.display = "flex";
    if (dashView) dashView.style.display = "none";
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
          <div class="quick-actions" id="quickActions">
            ${getQuickActionsHTML()}
          </div>
        </div>
      `;
      bindQuickActions();
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

  messageInput.addEventListener("input", autoResizeTextarea);
  logoutBtn.addEventListener("click", logout);
  bindQuickActions();

  if (refreshTicketsBtn) {
    refreshTicketsBtn.addEventListener("click", loadITTickets);
  }

  // Change password form
  const cpForm = document.getElementById("changePasswordForm");
  if (cpForm) {
    cpForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const oldPw = document.getElementById("oldPassword").value;
      const newPw = document.getElementById("newPassword").value;
      const msg = document.getElementById("passwordChangeMessage");
      try {
        const res = await fetch("/auth/change-password", {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: "Bearer " + AUTH_TOKEN },
          body: JSON.stringify({ old_password: oldPw, new_password: newPw }),
        });
        const data = await res.json();
        msg.textContent = data.message;
        msg.style.color = data.success ? "var(--green)" : "var(--red)";
      } catch {
        msg.textContent = "Error updating password.";
        msg.style.color = "var(--red)";
      }
    });
  }
}

function bindQuickActions() {
  document.querySelectorAll(".quick-action-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      messageInput.value = btn.dataset.query;
      autoResizeTextarea();
      setTimeout(handleSendMessage, 100);
    });
  });
}

// ---- Message Handling ----------------------------------------------------

async function handleSendMessage() {
  const query = messageInput.value.trim();
  if (!query || isLoading) return;

  messageInput.value = "";
  autoResizeTextarea();
  isLoading = true;
  sendBtn.disabled = true;

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
        Authorization: "Bearer " + AUTH_TOKEN,
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
  } catch (error) {
    showToast("Error: " + error.message, "error");
    appendMessage("assistant", "Error: Failed to get response. Please try again.");
  } finally {
    isLoading = false;
    sendBtn.disabled = false;
    showTypingIndicator(false);
  }
}

// ---- Adaptive Card Detection & Rendering ---------------------------------

function containsAdaptiveCard(text) {
  return text.includes('class="adaptive-card"') || text.includes("adaptive-card");
}

function renderMessageContent(text) {
  // If the response contains raw HTML adaptive cards, render them directly
  if (containsAdaptiveCard(text)) {
    // Split on adaptive card divs, render markdown for non-card parts
    const parts = text.split(/(<div class="adaptive-card"[\s\S]*?<\/div>\s*<\/div>\s*<\/div>)/g);
    let html = "";
    for (const part of parts) {
      if (part.includes('adaptive-card')) {
        html += part; // render card HTML as-is
      } else if (part.trim()) {
        html += renderMarkdown(part);
      }
    }
    return html;
  }

  // Check for markdown tables
  if (text.includes("|") && text.includes("---|")) {
    return renderMarkdownWithCards(text);
  }

  return renderMarkdown(text);
}

function renderMarkdown(text) {
  if (typeof marked !== "undefined") {
    try {
      return marked.parse(text);
    } catch {
      return text.replace(/\n/g, "<br>");
    }
  }
  return text.replace(/\n/g, "<br>");
}

function renderMarkdownWithCards(text) {
  // Parse markdown tables into styled adaptive cards
  const lines = text.split("\n");
  let html = "";
  let inTable = false;
  let tableLines = [];
  let preTableText = "";

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      if (!inTable) {
        // Render any text before the table
        if (preTableText.trim()) {
          html += renderMarkdown(preTableText);
          preTableText = "";
        }
        inTable = true;
        tableLines = [];
      }
      tableLines.push(trimmed);
    } else {
      if (inTable) {
        html += buildAdaptiveTable(tableLines);
        inTable = false;
        tableLines = [];
      }
      preTableText += line + "\n";
    }
  }

  if (inTable) {
    html += buildAdaptiveTable(tableLines);
  } else if (preTableText.trim()) {
    html += renderMarkdown(preTableText);
  }

  return html;
}

function buildAdaptiveTable(tableLines) {
  if (tableLines.length < 2) return renderMarkdown(tableLines.join("\n"));

  const headerCells = tableLines[0].split("|").filter((c) => c.trim()).map((c) => c.trim());

  // Skip separator line
  const dataRows = tableLines.slice(2).map((row) =>
    row.split("|").filter((c) => c.trim()).map((c) => c.trim())
  );

  if (dataRows.length === 0) return "";

  // Detect card type from headers
  let cardIcon = "fa-table";
  let cardTitle = "Results";
  let cardTheme = "primary";
  const headerStr = headerCells.join(" ").toLowerCase();

  if (headerStr.includes("leave")) {
    cardIcon = "fa-calendar-days";
    cardTitle = "Leave Information";
    cardTheme = "success";
  } else if (headerStr.includes("ticket") || headerStr.includes("issue")) {
    cardIcon = "fa-ticket";
    cardTitle = "IT Tickets";
    cardTheme = "info";
  } else if (headerStr.includes("asset")) {
    cardIcon = "fa-box";
    cardTitle = "Asset Requests";
    cardTheme = "warning";
  } else if (headerStr.includes("approval")) {
    cardIcon = "fa-clipboard-check";
    cardTitle = "Approvals";
    cardTheme = "primary";
  }

  let tableHTML = `<div class="adaptive-card">
    <div class="adaptive-card-header ${cardTheme}">
      <i class="fas ${cardIcon}"></i> ${cardTitle}
      <span class="card-badge">${dataRows.length} record${dataRows.length !== 1 ? "s" : ""}</span>
    </div>
    <div class="adaptive-card-body">
      <div class="card-table-wrapper">
        <table class="card-table">
          <thead><tr>`;

  for (const h of headerCells) {
    tableHTML += `<th>${h.replace(/\*\*/g, "")}</th>`;
  }
  tableHTML += `</tr></thead><tbody>`;

  for (const row of dataRows) {
    tableHTML += "<tr>";
    for (let i = 0; i < row.length; i++) {
      let cell = row[i];
      // Style status indicators
      cell = cell.replace(/🟢/g, '<span class="status-dot green"></span>');
      cell = cell.replace(/🟡/g, '<span class="status-dot yellow"></span>');
      cell = cell.replace(/🔴/g, '<span class="status-dot red"></span>');
      cell = cell.replace(/🔵/g, '<span class="status-dot blue"></span>');
      cell = cell.replace(/⚫/g, '<span class="status-dot grey"></span>');
      cell = cell.replace(/⚪/g, '<span class="status-dot grey"></span>');
      cell = cell.replace(/🚨/g, '<span class="status-dot red pulse"></span>');
      cell = cell.replace(/█/g, '<span class="bar-fill"></span>');
      cell = cell.replace(/░/g, '<span class="bar-empty"></span>');
      cell = cell.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      tableHTML += `<td>${cell}</td>`;
    }
    tableHTML += "</tr>";
  }

  tableHTML += `</tbody></table></div></div></div>`;
  return tableHTML;
}

function appendMessage(role, text) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${role}`;

  const avatarDiv = document.createElement("div");
  avatarDiv.className = "message-avatar";

  if (role === "assistant") {
    avatarDiv.innerHTML = '<i class="fas fa-brain"></i>';
  } else {
    const meta = ROLE_META[AUTH_ROLE] || ROLE_META.employee;
    avatarDiv.innerHTML = `<i class="fas ${meta.icon}"></i>`;
  }

  const contentDiv = document.createElement("div");
  contentDiv.className = "message-content";

  if (role === "assistant") {
    contentDiv.innerHTML = renderMessageContent(text);
  } else {
    contentDiv.textContent = text;
  }

  const timeDiv = document.createElement("div");
  timeDiv.className = "message-time";
  const now = new Date();
  timeDiv.textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  messageDiv.appendChild(avatarDiv);
  const msgBody = document.createElement("div");
  msgBody.className = "message-body";
  msgBody.appendChild(contentDiv);
  msgBody.appendChild(timeDiv);
  messageDiv.appendChild(msgBody);

  chatLog.appendChild(messageDiv);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function showTypingIndicator(show) {
  typingIndicator.style.display = show ? "flex" : "none";
  if (show) chatLog.scrollTop = chatLog.scrollHeight;
}

function updateDashboardStats() {
  // no-op — dashboard panel removed for enterprise simplification
}

// ---- Adaptive Card Callbacks ----------------------------------------------

window.submitAdaptiveLeaveForm = function(btn) {
  const card = btn.closest('.adaptive-card');
  const lt = card.querySelector(".ac-leave-type");
  const sd = card.querySelector(".ac-start-date");
  const ed = card.querySelector(".ac-end-date");
  const rs = card.querySelector(".ac-reason");
  const hr = card.querySelector(".ac-hr");
  
  if (!lt || !sd || !ed || !rs) return;
  
  if (!sd.value || !ed.value) {
    showToast("Please select both start and end dates.", "warning");
    return;
  }
  
  let hrStr = hr && hr.value.trim() ? `hr ${hr.value.trim()}` : "";
  let reason = rs.value.trim() || "personal";
  
  const query = `Confirm Apply ${lt.value} leave from ${sd.value} to ${ed.value} for ${reason} ${hrStr}`;
  
  messageInput.value = query;
  handleSendMessage();
};

window.submitAdaptiveHRSelect = function(leaveType, startDate, endDate, reason, hrUsername) {
  const query = `Confirm Apply ${leaveType} leave from ${startDate} to ${endDate} for ${reason} hr ${hrUsername}`;
  messageInput.value = query;
  handleSendMessage();
};

window.submitAdaptiveTicketForm = function(btn) {
  const card = btn.closest('.adaptive-card');
  const issue = card.querySelector(".ac-issue-type");
  const prio = card.querySelector(".ac-priority");
  const desc = card.querySelector(".ac-desc");

  if (!issue || !prio || !desc) return;
  if (!desc.value.trim()) {
    showToast("Please provide a description.", "warning");
    return;
  }

  const query = `Confirm Raise a ${prio.value} priority ticket for ${issue.value} because ${desc.value.trim()}`;
  messageInput.value = query;
  handleSendMessage();
};

window.submitAdaptiveAssetForm = function(btn) {
  const card = btn.closest('.adaptive-card');
  const type = card.querySelector(".ac-asset-type");
  const just = card.querySelector(".ac-justification");

  if (!type || !just) return;
  if (!just.value.trim()) {
    showToast("Please provide a justification.", "warning");
    return;
  }

  const query = `Confirm Request ${type.value} because ${just.value.trim()}`;
  messageInput.value = query;
  handleSendMessage();
};

// ---- Leave Balances ------------------------------------------------------

async function loadLeaveBalances() {
  const balanceTitle = document.getElementById("leaveBalanceTitle");
  if (balanceTitle && ["hr", "admin"].includes(AUTH_ROLE)) {
    return loadAllLeavesForHR();
  }

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
        const remaining = typeof dataObj === "object" ? dataObj.remaining : dataObj;
        const total = typeof dataObj === "object" ? dataObj.total : 12;
        const pct = Math.min((remaining / total) * 100, 100);
        const color = pct > 50 ? "var(--green)" : pct > 25 ? "var(--orange)" : "var(--red)";
        return `
        <div class="balance-item">
          <div class="balance-header">
            <span class="balance-label">${LEAVE_TYPE_LABELS[type] || type}</span>
            <span class="balance-days">${remaining}/${total}</span>
          </div>
          <div class="balance-bar">
            <div class="balance-fill" style="width:${pct}%; background:${color}"></div>
          </div>
        </div>
      `;
      })
      .join("");
  } catch {
    balanceList.innerHTML = '<p class="placeholder-text">Error loading balance</p>';
  }
}

async function loadAllLeavesForHR() {
  try {
    const res = await fetch("/api/leaves", {
      headers: { Authorization: "Bearer " + AUTH_TOKEN },
    });
    if (res.status === 401) return handleAuthExpired();
    const data = await res.json();

    const leaves = data.leaves || [];
    if (leaves.length === 0) {
      balanceList.innerHTML = '<p class="placeholder-text">No leaves filed yet.</p>';
      return;
    }

    const STATUS_STYLE = {
      approved: { bg: "rgba(52,211,153,.12)", color: "var(--green)", icon: "fa-check-circle" },
      pending: { bg: "rgba(251,146,60,.12)", color: "var(--orange)", icon: "fa-clock" },
      rejected: { bg: "rgba(248,113,113,.12)", color: "var(--red)", icon: "fa-times-circle" },
      cancelled: { bg: "rgba(107,114,128,.12)", color: "var(--text-muted)", icon: "fa-ban" },
    };

    balanceList.innerHTML = leaves
      .slice(0, 10)
      .map((leave) => {
        const st = STATUS_STYLE[leave.status] || STATUS_STYLE.pending;
        const typeLabel = LEAVE_TYPE_LABELS[leave.leave_type] || leave.leave_type || "Leave";
        return `
        <div class="leave-history-item">
          <div class="leave-history-header">
            <div class="leave-history-type">
              <i class="fas fa-user" style="color:var(--accent2)"></i>
              <strong>${leave.user_id}</strong> — ${typeLabel}
            </div>
            <span class="leave-status-badge" style="background:${st.bg};color:${st.color}">
              <i class="fas ${st.icon}"></i> ${(leave.status || "unknown").toUpperCase()}
            </span>
          </div>
          <div class="leave-history-dates">
            <i class="fas fa-arrow-right-long" style="font-size:10px;opacity:0.5"></i>
            ${leave.start_date} → ${leave.end_date}
          </div>
          <div class="leave-history-reason">${leave.reason || "No reason specified"}</div>
        </div>
      `;
      })
      .join("");
  } catch {
    balanceList.innerHTML = '<p class="placeholder-text">Error loading leaves</p>';
  }
}

// ---- Leave History -------------------------------------------------------

const LEAVE_STATUS_META = {
  approved: { icon: "fa-check-circle", color: "var(--green)", bg: "rgba(52,211,153,.12)", label: "Approved" },
  rejected: { icon: "fa-times-circle", color: "var(--red)", bg: "rgba(248,113,113,.12)", label: "Rejected" },
  pending: { icon: "fa-clock", color: "var(--orange)", bg: "rgba(251,146,60,.12)", label: "Pending" },
  cancelled: { icon: "fa-ban", color: "var(--text-muted)", bg: "rgba(107,114,128,.12)", label: "Cancelled" },
};

async function loadLeaveHistory() {
  const historyList = document.getElementById("leaveHistoryList");
  if (!historyList) return;

  try {
    const res = await fetch("/api/leaves", {
      headers: { Authorization: "Bearer " + AUTH_TOKEN },
    });
    if (res.status === 401) return handleAuthExpired();
    const data = await res.json();

    const leaves = data.leaves || [];
    if (leaves.length === 0) {
      historyList.innerHTML = '<p class="placeholder-text">No leave applications found. Use the chat to apply for leave.</p>';
      return;
    }

    historyList.innerHTML = leaves
      .slice(0, 15)
      .map((leave) => {
        const meta = LEAVE_STATUS_META[leave.status] || LEAVE_STATUS_META.pending;
        const leaveType = LEAVE_TYPE_LABELS[leave.leave_type] || leave.leave_type || "Leave";
        const dateRange = `${leave.start_date || "—"} → ${leave.end_date || "—"}`;
        const reason = leave.reason || "No reason specified";
        const canCancel = leave.status === "pending";

        return `
          <div class="leave-history-item">
            <div class="leave-history-header">
              <div class="leave-history-type">
                <i class="fas fa-calendar-day"></i> ${leaveType}
              </div>
              <span class="leave-status-badge" style="background:${meta.bg};color:${meta.color}">
                <i class="fas ${meta.icon}"></i> ${meta.label}
              </span>
            </div>
            <div class="leave-history-dates">
              <i class="fas fa-arrow-right-long" style="font-size:10px;opacity:0.5"></i> ${dateRange}
            </div>
            <div class="leave-history-reason">${reason}</div>
            ${canCancel ? `<button class="leave-cancel-btn" onclick="cancelLeave(${leave.id})"><i class="fas fa-xmark"></i> Cancel Request</button>` : ""}
          </div>
        `;
      })
      .join("");
  } catch {
    historyList.innerHTML = '<p class="placeholder-text">Error loading leave history</p>';
  }
}

async function cancelLeave(leaveId) {
  if (!confirm(`Cancel leave request #${leaveId}?`)) return;
  try {
    const res = await fetch(`/api/leaves/${leaveId}/cancel`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + AUTH_TOKEN,
      },
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Leave #${leaveId} cancelled ✅`, "success");
    } else {
      showToast(data.message || "Failed to cancel leave", "error");
    }
    loadLeaveHistory();
    loadLeaveBalances();
  } catch {
    showToast("Error cancelling leave", "error");
  }
}

// ---- Asset Requests ------------------------------------------------------

async function loadAssetRequests() {
  const assetList = document.getElementById("assetRequestsList");
  if (!assetList) return;

  try {
    const res = await fetch("/api/assets", {
      headers: { Authorization: "Bearer " + AUTH_TOKEN },
    });
    if (res.status === 401) return handleAuthExpired();
    const data = await res.json();

    const assets = data.assets || [];
    if (assets.length === 0) {
      assetList.innerHTML = '<p class="placeholder-text">No asset requests. Use the chat to request equipment.</p>';
      return;
    }

    const ASSET_LABELS = {
      laptop: "Laptop", monitor: "Monitor", keyboard: "Keyboard",
      mouse: "Mouse", vpn_token: "VPN Token", software_license: "Software License",
    };

    const STATUS_STYLE = {
      pending: { color: "var(--orange)", bg: "rgba(251,146,60,.12)", icon: "fa-clock" },
      approved: { color: "var(--green)", bg: "rgba(52,211,153,.12)", icon: "fa-check-circle" },
      rejected: { color: "var(--red)", bg: "rgba(248,113,113,.12)", icon: "fa-times-circle" },
      fulfilled: { color: "var(--cyan)", bg: "rgba(34,211,238,.12)", icon: "fa-box-check" },
    };

    assetList.innerHTML = assets
      .slice(0, 10)
      .map((asset) => {
        const label = ASSET_LABELS[asset.asset_type] || asset.asset_type;
        const st = STATUS_STYLE[asset.status] || STATUS_STYLE.pending;
        return `
          <div class="ticket-item">
            <div class="ticket-header">
              <span class="ticket-id"><i class="fas fa-box"></i> ${label}</span>
              <span class="leave-status-badge" style="background:${st.bg};color:${st.color}">
                <i class="fas ${st.icon}"></i> ${(asset.status || "pending").toUpperCase()}
              </span>
            </div>
            <p class="ticket-description">${asset.justification || "No justification provided"}</p>
            <span style="font-size:10px;color:var(--text-muted)">${asset.created_at ? asset.created_at.slice(0, 10) : ""}</span>
          </div>
        `;
      })
      .join("");
  } catch {
    assetList.innerHTML = '<p class="placeholder-text">Error loading asset requests</p>';
  }
}

// ---- IT Tickets ----------------------------------------------------------

async function loadITTickets() {
  const ticketsTitle = document.getElementById("itTicketsTitle");
  if (ticketsTitle && AUTH_ROLE === "it") {
    ticketsTitle.innerHTML = '<i class="fas fa-ticket"></i> Company IT Tickets';
  }
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

    const isITAdmin = ["it", "admin"].includes(AUTH_ROLE);

    ticketsList.innerHTML = tickets
      .slice(0, 8)
      .map((ticket) => {
        const status = ticket.status || "open";
        const isOpen = status === "open" || status === "in_progress";
        let actionsHTML = "";

        if (isITAdmin && isOpen) {
          actionsHTML = `
            <div class="ticket-actions">
              <button class="approve-btn" onclick="resolveTicket(${ticket.id})">
                <i class="fas fa-check-circle"></i> Resolve
              </button>
              <button class="approve-btn" style="background:rgba(99,120,255,.12);color:var(--accent);border-color:rgba(99,120,255,.2)" onclick="assignTicketPrompt(${ticket.id})">
                <i class="fas fa-user-plus"></i> Assign
              </button>
            </div>
          `;
        }

        return `
          <div class="ticket-item">
            <div class="ticket-header">
              <span class="ticket-id">#${ticket.id}</span>
              <span class="ticket-priority priority-${ticket.priority || "medium"}">${(ticket.priority || "medium").toUpperCase()}</span>
            </div>
            <p class="ticket-description">${ticket.description || ticket.issue_type}</p>
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px">
              <span class="ticket-status">${status}</span>
              <span style="font-size:10px;color:var(--text-muted)">${ticket.assigned_engineer ? 'Assigned: ' + ticket.assigned_engineer : 'Unassigned'}</span>
            </div>
            ${actionsHTML}
          </div>
        `;
      })
      .join("");
  } catch {
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

    pendingList.innerHTML = approvals
      .slice(0, 10)
      .map((approval) => {
        let detail = "";
        let requester = "";

        if (approval.request_type === "leave" && approval.leave_details) {
          const ld = approval.leave_details;
          detail = `${ld.leave_type || "Unknown"} Leave — ${ld.start_date || ""} to ${ld.end_date || ""}`;
          requester = ld.user_id || "";
        } else if (approval.request_type === "ticket" && approval.ticket_details) {
          const td = approval.ticket_details;
          detail = `${(td.issue_type || "Support").replace("_", " ")} Ticket — ${td.description || "No description"}`;
          requester = td.user_id || "";
        } else if (approval.request_type === "asset" && approval.asset_details) {
          const ad = approval.asset_details;
          const ASSET_NAMES = {laptop:"Laptop",monitor:"Monitor",keyboard:"Keyboard",mouse:"Mouse",vpn_token:"VPN Token",software_license:"Software License"};
          detail = `${ASSET_NAMES[ad.asset_type] || ad.asset_type} Request — ${ad.justification || "No justification"}`;
          requester = ad.user_id || "";
        } else {
          detail = `${approval.request_type} #${approval.request_id}`;
        }

        return `
        <div class="approval-card">
          <div class="approval-header">
            <span class="approval-id">#${approval.id}</span>
            <span class="approval-type">${approval.request_type}</span>
          </div>
          ${requester ? `<p style="font-size:11px;color:var(--text-muted);margin:2px 0"><i class="fas fa-user"></i> ${requester}</p>` : ""}
          <p class="approval-details">${detail}</p>
          <div class="approval-actions">
            <button class="approve-btn" onclick="handleApproval(${approval.id}, 'approved')">
              <i class="fas fa-check"></i> Approve
            </button>
            <button class="reject-btn" onclick="handleApproval(${approval.id}, 'rejected')">
              <i class="fas fa-times"></i> Reject
            </button>
          </div>
        </div>
      `;
      })
      .join("");
  } catch (error) {
    console.error("Failed to load approvals:", error);
  }
}

async function handleApproval(approvalId, decision) {
  try {
    const res = await fetch(`/api/approvals/${approvalId}/decide`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + AUTH_TOKEN,
      },
      body: JSON.stringify({ status: decision }),
    });
    const data = await res.json();
    showToast(`Approval #${approvalId} ${decision}`, decision === "approved" ? "success" : "error");
    loadPendingApprovals();
    loadLeaveBalances();
    loadLeaveHistory();
    loadITTickets();
    loadAssetRequests();
  } catch {
    showToast("Failed to process approval", "error");
  }
}

// ---- IT Ticket Actions (Dashboard) ----------------------------------------

async function resolveTicket(ticketId) {
  if (!confirm(`Resolve ticket #${ticketId}?`)) return;
  try {
    const res = await fetch(`/api/tickets/${ticketId}/resolve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + AUTH_TOKEN,
      },
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Ticket #${ticketId} resolved ✅`, "success");
    } else {
      showToast(data.message || data.error || "Failed to resolve ticket", "error");
    }
    loadITTickets();
    loadPendingApprovals();
  } catch {
    showToast("Error resolving ticket", "error");
  }
}

function assignTicketPrompt(ticketId) {
  const engineer = prompt(`Assign ticket #${ticketId} to which engineer? (enter username)`);
  if (!engineer || !engineer.trim()) return;
  assignTicket(ticketId, engineer.trim());
}

async function assignTicket(ticketId, engineer) {
  try {
    const res = await fetch(`/api/tickets/${ticketId}/assign`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + AUTH_TOKEN,
      },
      body: JSON.stringify({ engineer: engineer }),
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Ticket #${ticketId} assigned to ${engineer} ✅`, "success");
    } else {
      showToast(data.message || data.error || "Failed to assign ticket", "error");
    }
    loadITTickets();
  } catch {
    showToast("Error assigning ticket", "error");
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
  const icons = { info: "fa-circle-info", success: "fa-check-circle", error: "fa-exclamation-circle" };
  toast.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i><span>${message}</span>`;
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(80px)";
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

function handleAuthExpired() {
  localStorage.clear();
  window.location.href = "/";
}

function logout() {
  if (confirm("Sign out?")) {
    localStorage.clear(); // clears token, username, role, email
    window.location.href = "/";
  }
}

// ---- Start ---

init();
