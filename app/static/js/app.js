"use strict";

const elements = {
  loading: document.querySelector("#loading-screen"),
  auth: document.querySelector("#auth-screen"),
  chat: document.querySelector("#chat-screen"),
  authTitle: document.querySelector("#auth-title"),
  authSubtitle: document.querySelector("#auth-subtitle"),
  authNotice: document.querySelector("#auth-notice"),
  loginForm: document.querySelector("#login-form"),
  registerForm: document.querySelector("#register-form"),
  authSwitchPrompt: document.querySelector("#auth-switch-prompt"),
  authSwitchButton: document.querySelector("#auth-switch-button"),
  currentUsername: document.querySelector("#current-username"),
  logoutButton: document.querySelector("#logout-button"),
  connectionStatus: document.querySelector(".connection-status"),
  connectionLabel: document.querySelector("#connection-label"),
  messageList: document.querySelector("#message-list"),
  messageState: document.querySelector("#message-state"),
  chatError: document.querySelector("#chat-error"),
  messageForm: document.querySelector("#message-form"),
  messageInput: document.querySelector("#message-input"),
  characterCount: document.querySelector("#character-count"),
  sendButton: document.querySelector("#send-button"),
};

const renderedMessageIds = new Set();
let currentUser = null;
let socket = null;
let reconnectTimer = null;
let reconnectAttempt = 0;
let sessionActive = false;
let registrationMode = false;
let pendingSend = false;
let hasLoadedMessages = false;

function showScreen(screen) {
  elements.loading.hidden = screen !== "loading";
  elements.auth.hidden = screen !== "auth";
  elements.chat.hidden = screen !== "chat";
}

function setConnectionState(state, label) {
  elements.connectionStatus.dataset.state = state;
  elements.connectionLabel.textContent = label;
}

function showAuthNotice(message) {
  elements.authNotice.textContent = message;
  elements.authNotice.hidden = !message;
}

function showChatError(message) {
  elements.chatError.textContent = message;
  elements.chatError.hidden = !message;
}

function formatApiError(payload, fallback) {
  if (Array.isArray(payload?.detail)) {
    return payload.detail
      .map((item) => {
        const location = Array.isArray(item.loc) ? item.loc.slice(1).join(" → ") : "";
        return location ? `${location}: ${item.msg}` : item.msg;
      })
      .join(" ");
  }
  if (typeof payload?.detail === "string") return payload.detail;
  return fallback;
}

async function apiRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      credentials: "same-origin",
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new Error("Не удалось связаться с сервером. Проверьте подключение и попробуйте снова.");
  }

  let payload = null;
  if (response.status !== 204) {
    try {
      payload = await response.json();
    } catch {
      if (response.ok) throw new Error("Сервер вернул ответ в неожиданном формате.");
    }
  }
  if (!response.ok) {
    throw new Error(formatApiError(payload, `Ошибка сервера (${response.status}).`));
  }
  return payload;
}

function setRegistrationMode(enabled) {
  registrationMode = enabled;
  elements.loginForm.hidden = enabled;
  elements.registerForm.hidden = !enabled;
  elements.authTitle.textContent = enabled ? "Создать аккаунт" : "Войти в аккаунт";
  elements.authSubtitle.textContent = enabled
    ? "Заполните данные, чтобы присоединиться к чату."
    : "Введите данные, чтобы продолжить общение.";
  elements.authSwitchPrompt.textContent = enabled ? "Уже есть аккаунт?" : "Еще нет аккаунта?";
  elements.authSwitchButton.textContent = enabled ? "Войти" : "Зарегистрироваться";
  showAuthNotice("");
}

function isValidMessage(message) {
  return message !== null
    && typeof message === "object"
    && Number.isSafeInteger(message.id)
    && Number.isSafeInteger(message.user_id)
    && typeof message.username === "string"
    && message.username.length > 0
    && typeof message.content === "string"
    && message.content.length > 0
    && message.content.length <= 2000
    && typeof message.created_at === "string"
    && !Number.isNaN(Date.parse(message.created_at));
}

function formatTime(value) {
  return new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function renderMessage(message, { pending = false } = {}) {
  if (!pending && renderedMessageIds.has(message.id)) return null;
  if (!pending) renderedMessageIds.add(message.id);
  elements.messageState.hidden = true;

  const row = document.createElement("article");
  row.className = `message-row${message.user_id === currentUser.id ? " own" : ""}${pending ? " pending" : ""}`;
  if (!pending) row.dataset.messageId = String(message.id);

  const avatar = document.createElement("span");
  avatar.className = "avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = message.username.trim().charAt(0).toLocaleUpperCase("ru-RU");

  const content = document.createElement("div");
  content.className = "message-content";
  const meta = document.createElement("div");
  meta.className = "message-meta";
  const author = document.createElement("span");
  author.className = "message-author";
  author.textContent = message.user_id === currentUser.id ? "Вы" : message.username;
  const time = document.createElement("time");
  time.dateTime = message.created_at;
  time.textContent = formatTime(message.created_at);
  meta.append(author, time);

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = message.content;
  content.append(meta, bubble);
  row.append(avatar, content);
  elements.messageList.append(row);
  return row;
}

function scrollToLatest() {
  elements.messageList.scrollTop = elements.messageList.scrollHeight;
}

function setEmptyState(message, icon = "···") {
  elements.messageState.querySelector("p").textContent = message;
  elements.messageState.querySelector(".state-icon").textContent = icon;
  elements.messageState.hidden = false;
}

async function loadMessages({ initial = false } = {}) {
  const messages = await apiRequest("/api/messages");
  if (!Array.isArray(messages) || !messages.every(isValidMessage)) {
    throw new Error("Сервер вернул сообщения в неожиданном формате.");
  }
  messages.sort((first, second) => Date.parse(first.created_at) - Date.parse(second.created_at));
  messages.forEach((message) => renderMessage(message));
  if (initial && messages.length === 0) setEmptyState("Здесь пока тихо. Напишите первое сообщение.", "✳");
  if (initial) {
    hasLoadedMessages = true;
    scrollToLatest();
  }
  return messages;
}

function clearReconnectTimer() {
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function connectWebSocket() {
  if (!sessionActive || socket) return;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const address = `${protocol}//${window.location.host}/ws`;
  setConnectionState("connecting", "Подключение...");

  try {
    socket = new WebSocket(address);
  } catch {
    socket = null;
    scheduleReconnect();
    return;
  }

  socket.addEventListener("open", () => {
    reconnectAttempt = 0;
    setConnectionState("connected", "В сети");
    updateCharacterCount();
  });

  socket.addEventListener("message", (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch {
      showChatError("Получено сообщение в неверном формате.");
      return;
    }
    if (!isValidMessage(message)) {
      showChatError("Получено сообщение с неполными данными.");
      return;
    }
    showChatError("");
    const row = renderMessage(message);
    if (row) scrollToLatest();
  });

  socket.addEventListener("error", () => {
    setConnectionState("disconnected", "Проблема соединения");
    updateCharacterCount();
  });

  socket.addEventListener("close", (event) => {
    socket = null;
    if (!sessionActive) return;
    updateCharacterCount();
    if (event.code === 1008) {
      sessionActive = false;
      showScreen("auth");
      showAuthNotice("Сервер отклонил авторизацию. Войдите в аккаунт снова.");
      setConnectionState("disconnected", "Нет соединения");
      return;
    }
    scheduleReconnect();
  });
}

function scheduleReconnect() {
  if (!sessionActive || reconnectTimer !== null) return;
  const delay = Math.min(1000 * (2 ** reconnectAttempt), 30000);
  reconnectAttempt += 1;
  setConnectionState("disconnected", `Повтор через ${Math.ceil(delay / 1000)} сек.`);
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    connectWebSocket();
  }, delay);
}

function stopWebSocket() {
  sessionActive = false;
  clearReconnectTimer();
  if (socket) {
    const currentSocket = socket;
    socket = null;
    currentSocket.close(1000, "Session ended");
  }
  setConnectionState("disconnected", "Не подключено");
}

async function enterChat(user) {
  currentUser = user;
  sessionActive = true;
  hasLoadedMessages = false;
  pendingSend = false;
  elements.currentUsername.textContent = user.username;
  elements.messageList.querySelectorAll(".message-row").forEach((row) => row.remove());
  renderedMessageIds.clear();
  setEmptyState("Загружаем сообщения...");
  showChatError("");
  showScreen("chat");
  connectWebSocket();
  updateCharacterCount();

  try {
    await loadMessages({ initial: true });
  } catch (error) {
    if (error.message) showChatError(error.message);
    if (!hasLoadedMessages) setEmptyState("Не удалось загрузить сообщения.");
  }
}

async function handleLogin(event) {
  event.preventDefault();
  showAuthNotice("");
  const button = elements.loginForm.querySelector("button[type=submit]");
  button.disabled = true;
  const values = new FormData(elements.loginForm);
  try {
    const user = await apiRequest("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: values.get("username"),
        password: values.get("password"),
      }),
    });
    elements.loginForm.reset();
    await enterChat(user);
  } catch (error) {
    showAuthNotice(error.message);
  } finally {
    button.disabled = false;
  }
}

async function handleRegister(event) {
  event.preventDefault();
  showAuthNotice("");
  const button = elements.registerForm.querySelector("button[type=submit]");
  button.disabled = true;
  const values = new FormData(elements.registerForm);
  try {
    await apiRequest("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({
        username: values.get("username"),
        email: values.get("email"),
        password: values.get("password"),
      }),
    });
    elements.loginForm.elements.username.value = values.get("username");
    elements.registerForm.reset();
    setRegistrationMode(false);
    showAuthNotice("Аккаунт создан. Теперь войдите, используя выбранный пароль.");
  } catch (error) {
    showAuthNotice(error.message);
  } finally {
    button.disabled = false;
  }
}

async function handleLogout() {
  elements.logoutButton.disabled = true;
  try {
    await apiRequest("/api/auth/logout", { method: "POST" });
    stopWebSocket();
    currentUser = null;
    renderedMessageIds.clear();
    elements.messageList.querySelectorAll(".message-row").forEach((row) => row.remove());
    elements.messageInput.value = "";
    updateCharacterCount();
    setRegistrationMode(false);
    showAuthNotice("Вы вышли из аккаунта.");
    showScreen("auth");
  } catch (error) {
    showChatError(error.message);
  } finally {
    elements.logoutButton.disabled = false;
  }
}

function updateCharacterCount() {
  const length = elements.messageInput.value.length;
  elements.characterCount.textContent = `${length} / 2000`;
  elements.sendButton.disabled = pendingSend
    || length > 2000
    || !sessionActive
    || !socket
    || socket.readyState !== WebSocket.OPEN;
  elements.messageInput.style.height = "auto";
  elements.messageInput.style.height = `${Math.min(elements.messageInput.scrollHeight, 160)}px`;
}

async function waitForSavedMessage(content, existingIds) {
  const deadline = Date.now() + 7000;
  while (sessionActive && Date.now() < deadline) {
    const messages = await apiRequest("/api/messages");
    if (!Array.isArray(messages) || !messages.every(isValidMessage)) {
      throw new Error("Сервер вернул сообщения в неожиданном формате.");
    }
    const match = messages
      .filter((message) => message.user_id === currentUser.id
        && message.content === content
        && !existingIds.has(message.id))
      .sort((first, second) => Date.parse(first.created_at) - Date.parse(second.created_at))[0];
    if (match) return match;
    await new Promise((resolve) => window.setTimeout(resolve, 250));
  }
  throw new Error("Не удалось подтвердить сохранение сообщения. Проверьте соединение перед повторной отправкой.");
}

async function handleSendMessage(event) {
  event.preventDefault();
  const content = elements.messageInput.value.trim();
  if (!content || content.length > 2000) {
    if (content.length > 2000) showChatError("Сообщение не должно превышать 2000 символов.");
    return;
  }
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    showChatError("Нет соединения с чатом. Дождитесь подключения и попробуйте снова.");
    return;
  }

  pendingSend = true;
  updateCharacterCount();
  showChatError("");
  const existingIds = new Set(renderedMessageIds);
  const temporaryMessage = {
    user_id: currentUser.id,
    username: currentUser.username,
    content,
    created_at: new Date().toISOString(),
  };
  let pendingRow = null;
  try {
    socket.send(content);
    elements.messageInput.value = "";
    updateCharacterCount();
    pendingRow = renderMessage(temporaryMessage, { pending: true });
    scrollToLatest();

    const savedMessage = await waitForSavedMessage(content, existingIds);
    const confirmedRow = renderMessage(savedMessage);
    pendingRow?.remove();
    if (confirmedRow) scrollToLatest();
    showChatError("");
  } catch (error) {
    pendingRow?.remove();
    if (error.message) showChatError(error.message);
    elements.messageInput.value = content;
    updateCharacterCount();
  } finally {
    pendingSend = false;
    updateCharacterCount();
    elements.messageInput.focus();
  }
}

async function initialize() {
  try {
    const user = await apiRequest("/api/users/me");
    if (!user || !Number.isSafeInteger(user.id) || typeof user.username !== "string") {
      throw new Error("Сервер вернул данные пользователя в неожиданном формате.");
    }
    await enterChat(user);
  } catch (error) {
    setRegistrationMode(false);
    showScreen("auth");
    if (error.message && !error.message.includes("401") && !error.message.includes("Unauthorized")) {
      showAuthNotice(error.message);
    }
  }
}

elements.authSwitchButton.addEventListener("click", () => setRegistrationMode(!registrationMode));
elements.loginForm.addEventListener("submit", handleLogin);
elements.registerForm.addEventListener("submit", handleRegister);
elements.logoutButton.addEventListener("click", handleLogout);
elements.messageForm.addEventListener("submit", handleSendMessage);
elements.messageInput.addEventListener("input", updateCharacterCount);
elements.messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    elements.messageForm.requestSubmit();
  }
});

initialize();
