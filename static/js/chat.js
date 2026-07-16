(function () {
  "use strict";

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  function scrollToBottom(el) {
    el.scrollTop = el.scrollHeight;
  }

  function renderMarkdown(text) {
    if (!window.marked) return text;
    return window.marked.parse(text, { breaks: true, gfm: true });
  }

  function sanitizeHtml(html) {
    const allowed = ["p", "br", "strong", "em", "code", "pre", "ul", "ol", "li", "h1", "h2", "h3", "h4", "blockquote", "table", "thead", "tbody", "tr", "th", "td", "a", "hr"];
    const div = document.createElement("div");
    div.innerHTML = html;

    const walk = (el) => {
      const children = [...el.childNodes];
      for (const node of children) {
        if (node.nodeType !== 1) continue;

        if (!allowed.includes(node.tagName.toLowerCase())) {
          const span = document.createElement("span");
          span.textContent = node.textContent;
          node.replaceWith(span);
          continue;
        }

        for (const attr of [...node.attributes]) {
          if (node.tagName.toLowerCase() === "a" && attr.name === "href") {
            continue;
          }
          node.removeAttribute(attr.name);
        }

        walk(node);
      }
    };

    walk(div);
    return div.innerHTML;
  }

  function renderMarkdownSafe(text) {
    return sanitizeHtml(renderMarkdown(text || ""));
  }

  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const log = document.getElementById("chat-log");
  const sendBtn = document.getElementById("chat-send");

  if (!form || !input || !log || !sendBtn) return;

  form.style.display = "";

  const sendUrl = form.dataset.sendUrl;
  const csrftoken = getCookie("csrftoken");

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

  function appendTyping() {
    const div = document.createElement("div");
    div.className = "msg assistant typing";
    div.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';
    log.appendChild(div);
    scrollToBottom(log);
    return div;
  }

  function removeTyping(typingEl) {
    if (typingEl && typingEl.parentNode) {
      typingEl.remove();
    }
  }

  async function sendMessage(userText) {
    appendMessage("user", userText);
    input.value = "";
    sendBtn.disabled = true;

    const typingEl = appendTyping();

    try {
      const response = await fetch(sendUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken,
        },
        body: JSON.stringify({ message: userText }),
      });

      let data = {};
      try {
        data = await response.json();
      } catch (e) {
        data = {};
      }

      if (!response.ok) {
        throw new Error(data.error || `Request failed with status ${response.status}.`);
      }

      removeTyping(typingEl);
      appendMessage("assistant", (data.reply || "").trim() || "I could not generate a response.");
    } catch (error) {
      removeTyping(typingEl);
      appendMessage("assistant", error.message || "Network error - please check your connection and try again.");
    } finally {
      removeTyping(typingEl);
      sendBtn.disabled = false;
      input.focus();
    }
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (sendBtn.disabled) return;

    const text = input.value.trim();
    if (!text) return;

    sendMessage(text);
  });
})();
