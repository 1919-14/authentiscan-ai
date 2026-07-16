(function () {
  "use strict";

  /* ---------- helpers ---------- */

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  function scrollToBottom(el) {
    el.scrollTop = el.scrollHeight;
  }

  /* ---------- markdown renderer with sanitisation ---------- */

  function renderMarkdown(text) {
    if (!window.marked) return text;
    return window.marked.parse(text, { breaks: true, gfm: true });
  }

  function sanitizeHtml(html) {
    const allowed = ["p","br","strong","em","code","pre","ul","ol","li","h1","h2","h3","h4","blockquote","table","thead","tbody","tr","th","td","a","hr"];
    const div = document.createElement("div");
    div.innerHTML = html;
    const walk = (el) => {
      const children = [...el.childNodes];
      for (const node of children) {
        if (node.nodeType === 1 && !allowed.includes(node.tagName.toLowerCase())) {
          const span = document.createElement("span");
          span.textContent = node.textContent;
          node.replaceWith(span);
        } else if (node.nodeType === 1) {
          walk(node);
        }
      }
    };
    walk(div);
    return div.innerHTML;
  }

  function renderMarkdownSafe(text) {
    return sanitizeHtml(renderMarkdown(text));
  }

  /* ---------- DOM refs ---------- */

  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const log = document.getElementById("chat-log");
  const sendBtn = document.getElementById("chat-send");

  if (!form || !log) return;

  form.style.display = "";

  const streamUrl = form.dataset.sendUrl;
  const csrftoken = getCookie("csrftoken");

  /* ---------- message rendering ---------- */

  function appendMessage(role, text) {
    const wrapper = document.createElement("div");
    wrapper.className = `msg ${role}`;

    if (role === "assistant") {
      const inner = document.createElement("div");
      inner.className = "msg-content";
      inner.innerHTML = renderMarkdownSafe(text);
      wrapper.appendChild(inner);
    } else {
      wrapper.textContent = text;
    }

    log.appendChild(wrapper);
    scrollToBottom(log);
    return wrapper;
  }

  function updateMessage(el, text) {
    const content = el.querySelector(".msg-content");
    if (content) {
      content.innerHTML = renderMarkdownSafe(text);
    }
    scrollToBottom(log);
  }

  /* ---------- reasoning block ---------- */

  function appendReasoningBlock() {
    const wrapper = document.createElement("div");
    wrapper.className = "msg assistant reasoning-block";

    const toggle = document.createElement("button");
    toggle.className = "reasoning-toggle";
    toggle.type = "button";
    toggle.innerHTML = '<span class="reasoning-icon"><i data-lucide="brain" style="width:14px;height:14px;"></i></span> <span class="reasoning-label">Thinking</span> <span class="reasoning-arrow"><i data-lucide="chevron-down" style="width:14px;height:14px;"></i></span>';

    const body = document.createElement("div");
    body.className = "reasoning-body";
    body.style.display = "none";

    const textEl = document.createElement("div");
    textEl.className = "reasoning-text";
    body.appendChild(textEl);

    toggle.addEventListener("click", function () {
      const isOpen = body.style.display !== "none";
      body.style.display = isOpen ? "none" : "block";
      toggle.classList.toggle("open", !isOpen);
    });

    wrapper.appendChild(toggle);
    wrapper.appendChild(body);
    log.appendChild(wrapper);
    scrollToBottom(log);

    if (window.lucide) lucide.createIcons();

    return { wrapper, textEl, toggle };
  }

  function updateReasoning(el, text) {
    el.textContent = text;
  }

  function finaliseReasoning(wrapper) {
    const toggle = wrapper.querySelector(".reasoning-toggle");
    const label = toggle.querySelector(".reasoning-label");
    label.textContent = "Thought";
  }

  /* ---------- typing indicator ---------- */

  function appendTyping() {
    const div = document.createElement("div");
    div.className = "msg assistant typing";
    div.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';
    log.appendChild(div);
    scrollToBottom(log);
    return div;
  }

  /* ---------- SSE streaming ---------- */

  function startStream(userText) {
    appendMessage("user", userText);
    input.value = "";
    sendBtn.disabled = true;

    const typingEl = appendTyping();

    let reasoningBlock = null;
    let reasoningTextEl = null;
    let contentBuffer = "";
    let reasoningBuffer = "";
    let assistantMsgEl = null;

    const xhr = new XMLHttpRequest();
    xhr.open("POST", streamUrl, true);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.setRequestHeader("X-CSRFToken", csrftoken);

    let lastIndex = 0;

    xhr.onprogress = function () {
      const newData = xhr.responseText.substring(lastIndex);
      lastIndex = xhr.responseText.length;

      const lines = newData.split("\n");
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.substring(6).trim();
        if (!raw) continue;

        let event;
        try {
          event = JSON.parse(raw);
        } catch (e) {
          continue;
        }

        if (event.type === "reasoning") {
          if (!reasoningBlock) {
            typingEl.remove();
            reasoningBlock = appendReasoningBlock();
            reasoningTextEl = reasoningBlock.textEl;
          }
          reasoningBuffer += event.text;
          updateReasoning(reasoningTextEl, reasoningBuffer);
        }

        if (event.type === "content") {
          if (!assistantMsgEl) {
            if (reasoningBlock) {
              finaliseReasoning(reasoningBlock);
            } else if (typingEl.parentNode) {
              typingEl.remove();
            }
            contentBuffer = "";
            assistantMsgEl = appendMessage("assistant", "");
          }
          contentBuffer += event.text;
          updateMessage(assistantMsgEl, contentBuffer);
        }

        if (event.type === "error") {
          typingEl.remove();
          appendMessage("assistant", event.text || "Something went wrong.");
        }

        if (event.type === "done") {
          if (assistantMsgEl === null) {
            if (reasoningBlock) {
              finaliseReasoning(reasoningBlock);
            } else {
              typingEl.remove();
            }
            if (event.finish_reason === "length" && reasoningBuffer) {
              assistantMsgEl = appendMessage("assistant", "_The thinking used up the entire token budget, so no response was generated. Try asking a more specific question or start a new session._");
            } else {
              assistantMsgEl = appendMessage("assistant", "");
            }
          } else if (event.finish_reason === "length") {
            const note = document.createElement("div");
            note.className = "msg system-note";
            note.textContent = "Response was cut off because it reached the token limit. Try asking a shorter question.";
            log.appendChild(note);
            scrollToBottom(log);
          }
          sendBtn.disabled = false;
          input.focus();
        }
      }
    };

    xhr.onerror = function () {
      typingEl.remove();
      appendMessage("assistant", "Network error — please check your connection and try again.");
      sendBtn.disabled = false;
    };

    xhr.send(JSON.stringify({ message: userText }));
  }

  /* ---------- event binding ---------- */

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    startStream(text);
  });
})();
