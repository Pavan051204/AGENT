// DOM Elements
const chatLog = document.getElementById("chatLog");
const messageInput = document.getElementById("message");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearChat");
const exportBtn = document.getElementById("exportChat");
const userIdInput = document.getElementById("userId");
const sessionIdInput = document.getElementById("sessionId");
const roleSelect = document.getElementById("role");
const modelSelect = document.getElementById("model");
const apiStatus = document.getElementById("apiStatus");
const statusDot = document.getElementById("statusDot");
const themeToggle = document.getElementById("themeToggle");
const typingIndicator = document.getElementById("typingIndicator");
const toastContainer = document.getElementById("toastContainer");
const rateLimit = document.getElementById("rateLimit");
const latency = document.getElementById("latency");
const modelStatus = document.getElementById("modelStatus");

// Storage Keys
const STORAGE_KEYS = {
  userId: "agent.userId",
  sessionId: "agent.sessionId",
  role: "agent.role",
  model: "agent.model",
  theme: "agent.theme",
};

// Model Configuration
const MODEL_CONFIG = {
  "openai-fast": { name: "OpenAI (Fast)", limit: 60, icon: "🚀" },
  "openai-pro": { name: "OpenAI (Pro)", limit: 60, icon: "⚡" },
  "groq": { name: "Mixtral (Ultra-fast)", limit: 30, icon: "⚡" },
  "gemini": { name: "Gemini (Budget)", limit: 40, icon: "🔮" },
  "adaptive": { name: "Adaptive (Auto)", limit: 50, icon: "🤖" },
};

// Rate Limiting State
const rateLimitState = {
  "openai-fast": { requests: 0, resetTime: Date.now() },
  "openai-pro": { requests: 0, resetTime: Date.now() },
  "groq": { requests: 0, resetTime: Date.now() },
  "gemini": { requests: 0, resetTime: Date.now() },
};

const modelMetrics = {
  "openai-fast": { responseTime: 0, available: true },
  "openai-pro": { responseTime: 0, available: true },
  "groq": { responseTime: 0, available: true },
  "gemini": { responseTime: 0, available: true },
};

// State
let isLoading = false;
let conversationHistory = [];
let currentModel = "openai-pro";

// Initialize
function init() {
  setDefaultIds();
  checkHealth();
  setupEventListeners();
  restoreTheme();
  autoResizeTextarea();
  updateModelInfo();
  
  setInterval(checkHealth, 5000);
  setInterval(updateModelMetrics, 10000);
}

// Theme Management
function restoreTheme() {
  const savedTheme = localStorage.getItem(STORAGE_KEYS.theme);
  if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.body.classList.add('dark-mode');
    themeToggle.textContent = '☀️';
  }
}

themeToggle.addEventListener('click', () => {
  document.body.classList.toggle('dark-mode');
  const isDark = document.body.classList.contains('dark-mode');
  localStorage.setItem(STORAGE_KEYS.theme, isDark ? 'dark' : 'light');
  themeToggle.innerHTML = isDark ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon toggle-icon"></i>';
});

// Set Default IDs
function setDefaultIds() {
  const storedUser = localStorage.getItem(STORAGE_KEYS.userId);
  const storedSession = localStorage.getItem(STORAGE_KEYS.sessionId);
  const storedRole = localStorage.getItem(STORAGE_KEYS.role);
  const storedModel = localStorage.getItem(STORAGE_KEYS.model);

  userIdInput.value = storedUser || `user-${crypto.randomUUID().slice(0, 8)}`;
  sessionIdInput.value = storedSession || `session-${crypto.randomUUID().slice(0, 8)}`;
  roleSelect.value = storedRole || "employee";
  modelSelect.value = storedModel || "openai-pro";
  currentModel = modelSelect.value;

  persistInputs();
}

// Persist Inputs
function persistInputs() {
  localStorage.setItem(STORAGE_KEYS.userId, userIdInput.value.trim());
  localStorage.setItem(STORAGE_KEYS.sessionId, sessionIdInput.value.trim());
  localStorage.setItem(STORAGE_KEYS.role, roleSelect.value);
  localStorage.setItem(STORAGE_KEYS.model, modelSelect.value);
}

// Update Model Info Display
function updateModelInfo() {
  const config = MODEL_CONFIG[currentModel];
  if (!config) return;

  rateLimit.textContent = `${config.limit} req/min`;
  modelStatus.textContent = "Ready";
  
  const metrics = modelMetrics[currentModel];
  if (metrics && metrics.responseTime > 0) {
    latency.textContent = `${Math.round(metrics.responseTime)}ms`;
  } else {
    latency.textContent = "--";
  }
}

// Update Model Metrics
function updateModelMetrics() {
  // Simulate metrics update - in production, fetch from backend
  for (let model in modelMetrics) {
    if (modelMetrics[model].available) {
      modelMetrics[model].responseTime += (Math.random() - 0.5) * 100;
      modelMetrics[model].responseTime = Math.max(100, Math.min(5000, modelMetrics[model].responseTime));
    }
  }
  
  if (!isLoading) {
    updateModelInfo();
  }
}

// Check Rate Limit
function checkRateLimit(model) {
  const now = Date.now();
  const state = rateLimitState[model];
  const config = MODEL_CONFIG[model];
  
  if (now - state.resetTime >= 60000) {
    state.requests = 0;
    state.resetTime = now;
  }
  
  if (state.requests >= config.limit) {
    return false;
  }
  
  state.requests++;
  return true;
}

// Get Best Model (Adaptive)
function getBestModel() {
  let bestModel = "openai-pro";
  let bestScore = Infinity;
  
  for (let model in modelMetrics) {
    if (modelMetrics[model].available && checkRateLimit(model)) {
      const score = modelMetrics[model].responseTime;
      if (score < bestScore) {
        bestScore = score;
        bestModel = model;
      }
    }
  }
  
  return bestModel;
}

// Model Selection Handler
modelSelect.addEventListener("change", (e) => {
  currentModel = e.target.value;
  
  if (currentModel === "adaptive") {
    const bestModel = getBestModel();
    showToast(`Adaptive mode enabled: Using ${MODEL_CONFIG[bestModel].name}`, 'info');
  } else {
    if (!checkRateLimit(currentModel)) {
      showToast(`Rate limit exceeded for ${MODEL_CONFIG[currentModel].name}`, 'warning');
      modelSelect.value = "adaptive";
      currentModel = "adaptive";
    }
  }
  
  persistInputs();
  updateModelInfo();
});

// API Health Check
async function checkHealth() {
  try {
    const response = await fetch("/health");
    if (response.ok) {
      apiStatus.textContent = "Online";
      statusDot.classList.remove('offline');
    } else {
      apiStatus.textContent = "Degraded";
      statusDot.classList.add('offline');
    }
  } catch (error) {
    apiStatus.textContent = "Offline";
    statusDot.classList.add('offline');
  }
}

// Create Chat Bubble
function createBubble(text, type, meta) {
  const wrapper = document.createElement("div");
  wrapper.className = `chat-bubble ${type}`;

  const content = document.createElement("div");
  
  if (type === 'agent') {
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

// Parse message content for formatting
function parseMessageContent(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
}

// Add Message to Chat
function addMessage(text, type, meta) {
  const bubble = createBubble(text, type, meta);
  chatLog.appendChild(bubble);
  conversationHistory.push({ text, type, meta, timestamp: new Date() });
  chatLog.scrollTop = chatLog.scrollHeight;
}

// Get Timestamp
function getTimestamp() {
  const now = new Date();
  return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Show Toast Notification
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let iconClass = '';
  switch(type) {
    case 'success': iconClass = 'fas fa-check-circle'; break;
    case 'error': iconClass = 'fas fa-times-circle'; break;
    case 'warning': iconClass = 'fas fa-exclamation-circle'; break;
    case 'info': iconClass = 'fas fa-info-circle'; break;
  }
  
  const icon = document.createElement('i');
  icon.className = iconClass;
  
  const textSpan = document.createElement('span');
  textSpan.textContent = message;
  
  toast.appendChild(icon);
  toast.appendChild(textSpan);
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'slideInLeft 0.3s var(--ease-out) reverse';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Send Message
async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || isLoading) return;

  // Select model
  let selectedModel = currentModel;
  if (currentModel === "adaptive") {
    selectedModel = getBestModel();
    showToast(`Using ${MODEL_CONFIG[selectedModel].name} (Adaptive)`, 'info');
  }

  // Check rate limit
  if (!checkRateLimit(selectedModel)) {
    showToast(`Rate limit exceeded for ${MODEL_CONFIG[selectedModel].name}. Trying another model...`, 'warning');
    selectedModel = getBestModel();
  }

  persistInputs();
  addMessage(text, "user", getTimestamp());
  messageInput.value = "";
  autoResizeTextarea();

  const payload = {
    user_id: userIdInput.value.trim(),
    role: roleSelect.value,
    query: text,
    session_id: sessionIdInput.value.trim(),
    model: selectedModel,
  };

  isLoading = true;
  sendBtn.disabled = true;
  typingIndicator.style.display = 'flex';
  
  const startTime = performance.now();

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const endTime = performance.now();
    const responseTime = endTime - startTime;
    modelMetrics[selectedModel].responseTime = responseTime;

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    typingIndicator.style.display = 'none';

    let meta = `${getTimestamp()} | ${MODEL_CONFIG[selectedModel].icon} ${MODEL_CONFIG[selectedModel].name} | ${Math.round(responseTime)}ms`;
    if (data.approval_required) {
      meta += ' | ⚠️ Approval Required';
    }

    addMessage(data.response, "agent", meta);
    showToast('Response received', 'success');
  } catch (error) {
    typingIndicator.style.display = 'none';
    addMessage("Something went wrong. Please try again.", "agent", "Error");
    showToast(`Error: ${error.message}`, 'error');
  } finally {
    isLoading = false;
    sendBtn.disabled = false;
    messageInput.focus();
    updateModelInfo();
  }
}

// Clear Chat
function clearChat() {
  if (conversationHistory.length === 0) return;
  
  const confirmed = confirm("Are you sure you want to clear the chat?");
  if (confirmed) {
    chatLog.innerHTML = `
      <div class="welcome-message">
        <div class="welcome-icon">
          <i class="fas fa-robot"></i>
        </div>
        <h2>Chat Cleared</h2>
        <p>Start a new conversation anytime.</p>
      </div>
    `;
    conversationHistory = [];
    showToast('Chat cleared', 'info');
  }
}

// Export Chat
function exportChat() {
  if (conversationHistory.length === 0) {
    showToast('No messages to export', 'info');
    return;
  }

  let content = `# Chat Export\n`;
  content += `**User:** ${userIdInput.value}\n`;
  content += `**Session:** ${sessionIdInput.value}\n`;
  content += `**Role:** ${roleSelect.value}\n`;
  content += `**Model:** ${MODEL_CONFIG[currentModel].name}\n`;
  content += `**Exported:** ${new Date().toLocaleString()}\n\n`;
  content += `---\n\n`;

  conversationHistory.forEach(msg => {
    const role = msg.type === 'user' ? 'You' : 'AI Assistant';
    content += `**${role}** (${msg.timestamp.toLocaleTimeString()}):\n`;
    content += `${msg.text}\n\n`;
  });

  const blob = new Blob([content], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `chat-export-${Date.now()}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  showToast('Chat exported successfully', 'success');
}

// Auto-resize Textarea
function autoResizeTextarea() {
  messageInput.style.height = 'auto';
  messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
}

// Quick Prompt Buttons
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('prompt-btn')) {
    messageInput.value = e.target.dataset.prompt;
    messageInput.focus();
    autoResizeTextarea();
  }
});

// Setup Event Listeners
function setupEventListeners() {
  sendBtn.addEventListener("click", sendMessage);
  clearBtn.addEventListener("click", clearChat);
  exportBtn.addEventListener("click", exportChat);

  messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });

  messageInput.addEventListener("input", autoResizeTextarea);

  [userIdInput, sessionIdInput, roleSelect].forEach((input) => {
    input.addEventListener("change", persistInputs);
  });

  document.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.shiftKey) {
      if (event.key === 'C') {
        event.preventDefault();
        clearChat();
      }
      if (event.key === 'E') {
        event.preventDefault();
        exportChat();
      }
    }
  });
}

// Initialize on load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

// Theme Management
function restoreTheme() {
  const savedTheme = localStorage.getItem(STORAGE_KEYS.theme);
  if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.body.classList.add('dark-mode');
    themeToggle.textContent = '☀️';
  }
}

themeToggle.addEventListener('click', () => {
  document.body.classList.toggle('dark-mode');
  const isDark = document.body.classList.contains('dark-mode');
  localStorage.setItem(STORAGE_KEYS.theme, isDark ? 'dark' : 'light');
  themeToggle.textContent = isDark ? '☀️' : '🌙';
});

// Set Default IDs
function setDefaultIds() {
  const storedUser = localStorage.getItem(STORAGE_KEYS.userId);
  const storedSession = localStorage.getItem(STORAGE_KEYS.sessionId);
  const storedRole = localStorage.getItem(STORAGE_KEYS.role);

  userIdInput.value = storedUser || `user-${crypto.randomUUID().slice(0, 8)}`;
  sessionIdInput.value = storedSession || `session-${crypto.randomUUID().slice(0, 8)}`;
  roleSelect.value = storedRole || "employee";

  persistInputs();
}

// Persist Inputs
function persistInputs() {
  localStorage.setItem(STORAGE_KEYS.userId, userIdInput.value.trim());
  localStorage.setItem(STORAGE_KEYS.sessionId, sessionIdInput.value.trim());
  localStorage.setItem(STORAGE_KEYS.role, roleSelect.value);
}

// API Health Check
async function checkHealth() {
  try {
    const response = await fetch("/health");
    if (response.ok) {
      apiStatus.textContent = "Online";
      statusDot.classList.remove('offline');
    } else {
      apiStatus.textContent = "Degraded";
      statusDot.classList.add('offline');
    }
  } catch (error) {
    apiStatus.textContent = "Offline";
    statusDot.classList.add('offline');
  }
}

// Create Chat Bubble
function createBubble(text, type, meta) {
  const wrapper = document.createElement("div");
  wrapper.className = `chat-bubble ${type}`;

  const content = document.createElement("div");
  
  // Parse markdown-like formatting
  if (type === 'agent') {
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

// Parse message content for basic formatting
function parseMessageContent(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
}

// Add Message to Chat
function addMessage(text, type, meta) {
  const bubble = createBubble(text, type, meta);
  chatLog.appendChild(bubble);
  conversationHistory.push({ text, type, meta, timestamp: new Date() });
  chatLog.scrollTop = chatLog.scrollHeight;
}

// Get Timestamp
function getTimestamp() {
  const now = new Date();
  return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Show Toast Notification with Icons
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let iconClass = '';
  switch(type) {
    case 'success': iconClass = 'fas fa-check-circle'; break;
    case 'error': iconClass = 'fas fa-times-circle'; break;
    case 'info': iconClass = 'fas fa-info-circle'; break;
  }
  
  const icon = document.createElement('i');
  icon.className = iconClass;
  
  const textSpan = document.createElement('span');
  textSpan.textContent = message;
  
  toast.appendChild(icon);
  toast.appendChild(textSpan);
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'slideInLeft 0.3s var(--ease-out) reverse';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Send Message
async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || isLoading) return;

  persistInputs();
  addMessage(text, "user", getTimestamp());
  messageInput.value = "";
  autoResizeTextarea();

  const payload = {
    user_id: userIdInput.value.trim(),
    role: roleSelect.value,
    query: text,
    session_id: sessionIdInput.value.trim(),
  };

  isLoading = true;
  sendBtn.disabled = true;
  typingIndicator.style.display = 'flex';

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    typingIndicator.style.display = 'none';

    let meta = `${getTimestamp()} | Trace: ${data.trace_id?.slice(0, 8)}...`;
    if (data.approval_required) {
      meta += ' | ⚠️ Approval Required';
    }

    addMessage(data.response, "agent", meta);
    showToast('Response received', 'success');
  } catch (error) {
    typingIndicator.style.display = 'none';
    addMessage("Something went wrong. Please try again.", "agent", "Error");
    showToast(`Error: ${error.message}`, 'error');
  } finally {
    isLoading = false;
    sendBtn.disabled = false;
    messageInput.focus();
  }
}

// Clear Chat
function clearChat() {
  if (conversationHistory.length === 0) return;
  
  const confirmed = confirm("Are you sure you want to clear the chat?");
  if (confirmed) {
    chatLog.innerHTML = `
      <div class="welcome-message">
        <div class="welcome-icon">🤖</div>
        <h2>Chat Cleared</h2>
        <p>Start a new conversation anytime.</p>
      </div>
    `;
    conversationHistory = [];
    showToast('Chat cleared', 'info');
  }
}

// Export Chat
function exportChat() {
  if (conversationHistory.length === 0) {
    showToast('No messages to export', 'info');
    return;
  }

  let content = `# Chat Export\n`;
  content += `**User:** ${userIdInput.value}\n`;
  content += `**Session:** ${sessionIdInput.value}\n`;
  content += `**Role:** ${roleSelect.value}\n`;
  content += `**Exported:** ${new Date().toLocaleString()}\n\n`;
  content += `---\n\n`;

  conversationHistory.forEach(msg => {
    const role = msg.type === 'user' ? 'You' : 'AI Assistant';
    content += `**${role}** (${msg.timestamp.toLocaleTimeString()}):\n`;
    content += `${msg.text}\n\n`;
  });

  const blob = new Blob([content], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `chat-export-${Date.now()}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  showToast('Chat exported successfully', 'success');
}

// Auto-resize Textarea
function autoResizeTextarea() {
  messageInput.style.height = 'auto';
  messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
}

// Quick Prompt Buttons
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('prompt-btn')) {
    messageInput.value = e.target.dataset.prompt;
    messageInput.focus();
    autoResizeTextarea();
  }
});

// Setup Event Listeners
function setupEventListeners() {
  sendBtn.addEventListener("click", sendMessage);
  clearBtn.addEventListener("click", clearChat);
  exportBtn.addEventListener("click", exportChat);

  messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });

  messageInput.addEventListener("input", autoResizeTextarea);

  [userIdInput, sessionIdInput, roleSelect].forEach((input) => {
    input.addEventListener("change", persistInputs);
  });

  // Keyboard shortcuts
  document.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.shiftKey) {
      if (event.key === 'C') {
        event.preventDefault();
        clearChat();
      }
      if (event.key === 'E') {
        event.preventDefault();
        exportChat();
      }
    }
  });
}

// Initialize on load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
