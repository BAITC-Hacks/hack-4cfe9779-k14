const messages = document.querySelector("#messages");
const form = document.querySelector("#message-form");
const input = document.querySelector("#message");
const sendButton = document.querySelector("#send");
const status = document.querySelector("#status");
let sessionId = null;

function addMessage(role, text) {
  const item = document.createElement("article");
  item.className = `message ${role}`;
  item.textContent = text;
  messages.append(item);
  messages.scrollTop = messages.scrollHeight;
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.message || "Не удалось обработать запрос.");
  return body;
}

async function getSession() {
  if (sessionId) return sessionId;
  const session = await request("/api/chat/sessions", { method: "POST" });
  sessionId = session.id;
  return sessionId;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const content = input.value.trim();
  if (!content) return;
  addMessage("user", content);
  input.value = "";
  sendButton.disabled = true;
  status.textContent = "Отправляем…";
  try {
    const id = await getSession();
    const reply = await request(`/api/chat/sessions/${id}/messages`, {
      method: "POST", body: JSON.stringify({ content }),
    });
    addMessage("assistant", reply.assistant_message.content);
    status.textContent = "";
  } catch (error) {
    status.textContent = error.message;
  } finally {
    sendButton.disabled = false;
    input.focus();
  }
});
