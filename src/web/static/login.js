// ===========================================================================
// Enterprise AI Copilot — Login & Registration Logic
// ===========================================================================

// ---- DOM Elements --------------------------------------------------------

const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");
const loginTab = document.getElementById("loginTab");
const registerTab = document.getElementById("registerTab");
const tabIndicator = document.getElementById("tabIndicator");
const loginMessage = document.getElementById("loginMessage");
const registerMessage = document.getElementById("registerMessage");

// ---- On Load  — redirect to chat if already authenticated ----------------

(function checkExistingSession() {
  const token = localStorage.getItem("auth.token");
  if (token) {
    // Verify the token is still valid
    fetch("/auth/me", {
      headers: { Authorization: "Bearer " + token },
    })
      .then((r) => {
        if (r.ok) {
          window.location.href = "/chat";
        } else {
          // Token expired / invalid – clear it
          localStorage.removeItem("auth.token");
          localStorage.removeItem("auth.username");
          localStorage.removeItem("auth.role");
        }
      })
      .catch(() => {});
  }
})();

// ---- Background particles ------------------------------------------------

function createParticles() {
  const container = document.getElementById("bgParticles");
  if (!container) return;

  const colors = [
    "rgba(99, 102, 241, 0.4)",
    "rgba(139, 92, 246, 0.3)",
    "rgba(167, 139, 250, 0.25)",
    "rgba(99, 102, 241, 0.2)",
    "rgba(59, 130, 246, 0.2)",
  ];

  for (let i = 0; i < 35; i++) {
    const p = document.createElement("div");
    p.className = "particle";
    const size = Math.random() * 6 + 2;
    const duration = Math.random() * 15 + 10;
    const delay = Math.random() * 10;
    p.style.width = size + "px";
    p.style.height = size + "px";
    p.style.left = Math.random() * 100 + "%";
    p.style.background = colors[Math.floor(Math.random() * colors.length)];
    p.style.animationDuration = duration + "s";
    p.style.animationDelay = delay + "s";
    container.appendChild(p);
  }
}
createParticles();

// ---- Tab Switching -------------------------------------------------------

loginTab.addEventListener("click", () => switchTab("login"));
registerTab.addEventListener("click", () => switchTab("register"));

function switchTab(tab) {
  if (tab === "login") {
    loginTab.classList.add("active");
    registerTab.classList.remove("active");
    loginForm.classList.remove("hidden");
    registerForm.classList.add("hidden");
    tabIndicator.classList.remove("right");
  } else {
    registerTab.classList.add("active");
    loginTab.classList.remove("active");
    registerForm.classList.remove("hidden");
    loginForm.classList.add("hidden");
    tabIndicator.classList.add("right");
  }
  clearMessages();
}

// ---- Toggle password visibility ------------------------------------------

document.querySelectorAll(".toggle-password").forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = document.getElementById(btn.dataset.target);
    if (!target) return;
    const isPassword = target.type === "password";
    target.type = isPassword ? "text" : "password";
    btn.innerHTML = isPassword
      ? '<i class="fas fa-eye-slash"></i>'
      : '<i class="fas fa-eye"></i>';
  });
});

// ---- Message helpers -----------------------------------------------------

function showMessage(el, text, type) {
  el.textContent = text;
  el.className = "form-message " + type;
}

function clearMessages() {
  loginMessage.textContent = "";
  loginMessage.className = "form-message";
  registerMessage.textContent = "";
  registerMessage.className = "form-message";
}

// ---- Login ---------------------------------------------------------------

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearMessages();

  const username = document.getElementById("loginUsername").value.trim();
  const password = document.getElementById("loginPassword").value;

  if (!username || !password) {
    showMessage(loginMessage, "Please fill in all fields.", "error");
    return;
  }

  const submitBtn = document.getElementById("loginSubmit");
  setLoading(submitBtn, true);

  try {
    const res = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    const data = await res.json();

    if (data.success) {
      showMessage(loginMessage, "Login successful! Redirecting…", "success");
      localStorage.setItem("auth.token", data.token);
      localStorage.setItem("auth.username", data.username);
      localStorage.setItem("auth.role", data.role);
      if (data.email) localStorage.setItem("auth.email", data.email);
      setTimeout(() => (window.location.href = "/chat"), 600);
    } else {
      showMessage(loginMessage, data.message || "Login failed.", "error");
    }
  } catch (err) {
    showMessage(loginMessage, "Network error. Please try again.", "error");
  } finally {
    setLoading(submitBtn, false);
  }
});

// ---- Register ------------------------------------------------------------

registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearMessages();

  const username = document.getElementById("registerUsername").value.trim();
  const email = document.getElementById("registerEmail").value.trim();
  const password = document.getElementById("registerPassword").value;
  const role = document.getElementById("registerRole").value;

  if (!username || !email || !password || !role) {
    showMessage(registerMessage, "Please fill in all fields.", "error");
    return;
  }

  const submitBtn = document.getElementById("registerSubmit");
  setLoading(submitBtn, true);

  try {
    const res = await fetch("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password, role }),
    });

    const data = await res.json();

    if (data.success) {
      showMessage(registerMessage, "Account created! Redirecting…", "success");
      localStorage.setItem("auth.token", data.token);
      localStorage.setItem("auth.username", data.username);
      localStorage.setItem("auth.role", data.role);
      if (data.email) localStorage.setItem("auth.email", data.email);
      setTimeout(() => (window.location.href = "/chat"), 600);
    } else {
      showMessage(registerMessage, data.message || "Registration failed.", "error");
    }
  } catch (err) {
    showMessage(registerMessage, "Network error. Please try again.", "error");
  } finally {
    setLoading(submitBtn, false);
  }
});

// ---- Loading state helper ------------------------------------------------

function setLoading(btn, loading) {
  const text = btn.querySelector(".btn-text");
  const loader = btn.querySelector(".btn-loader");
  const arrow = btn.querySelector(".btn-arrow");

  if (loading) {
    btn.disabled = true;
    if (text) text.style.display = "none";
    if (loader) loader.style.display = "inline-block";
    if (arrow) arrow.style.display = "none";
  } else {
    btn.disabled = false;
    if (text) text.style.display = "inline";
    if (loader) loader.style.display = "none";
    if (arrow) arrow.style.display = "inline";
  }
}
