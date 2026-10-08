(() => {
    const app = document.getElementById("aiApp");
    if (!app) return;

    const conversationList = document.getElementById("conversationList");
    const messageList = document.getElementById("messageList");
    const welcomePanel = document.getElementById("welcomePanel");
    const chatForm = document.getElementById("chatForm");
    const promptInput = document.getElementById("id_prompt");
    const modeSelect = document.getElementById("id_mode");
    const sendButton = document.getElementById("sendButton");
    const clearButton = document.getElementById("clearChatButton");
    const loadingIndicator = document.getElementById("loadingIndicator");
    const errorBanner = document.getElementById("aiError");
    const characterCount = document.getElementById("characterCount");
    const newChatButton = document.getElementById("newChatButton");
    let conversations = [];
    let activeConversationId = null;

    const csrfToken = chatForm.querySelector("[name=csrfmiddlewaretoken]").value;
    const messagesUrl = (id) => app.dataset.messagesUrlTemplate.replace("/0/", `/${id}/`);
    const deleteUrl = (id) => app.dataset.deleteUrlTemplate.replace("/0/", `/${id}/`);

    function showError(message) {
        errorBanner.textContent = message;
        errorBanner.hidden = false;
    }

    function clearError() {
        errorBanner.textContent = "";
        errorBanner.hidden = true;
    }

    function setBusy(busy) {
        promptInput.disabled = busy;
        modeSelect.disabled = busy;
        sendButton.disabled = busy;
        newChatButton.disabled = busy;
        clearButton.disabled = busy || !activeConversationId;
        loadingIndicator.hidden = !busy;
    }

    function addMessage(message) {
        const article = document.createElement("article");
        article.className = `ai-message ai-message-${message.role === "assistant" ? "assistant" : "user"}`;

        const avatar = document.createElement("span");
        avatar.className = "ai-message-avatar";
        avatar.innerHTML = message.role === "assistant"
            ? '<i class="bi bi-stars"></i>'
            : '<i class="bi bi-person-fill"></i>';

        const body = document.createElement("div");
        body.className = "ai-message-body";
        const label = document.createElement("span");
        label.className = "ai-message-label";
        label.textContent = message.role === "assistant" ? "Placement Prep Tutor" : "You";
        const content = document.createElement("div");
        content.className = "ai-message-content";
        content.textContent = message.content;
        body.append(label, content);
        article.append(avatar, body);
        messageList.append(article);
    }

    function renderMessages(messages) {
        messageList.replaceChildren();
        messages.forEach(addMessage);
        welcomePanel.hidden = messages.length > 0;
        clearButton.disabled = !activeConversationId;
        document.getElementById("messageScroll").scrollTop =
            document.getElementById("messageScroll").scrollHeight;
    }

    function renderConversations() {
        conversationList.replaceChildren();
        document.getElementById("historyCount").textContent = String(conversations.length);
        conversations.forEach((conversation) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "ai-history-item";
            if (conversation.id === activeConversationId) button.classList.add("is-active");
            button.setAttribute("aria-current", conversation.id === activeConversationId ? "page" : "false");

            const icon = document.createElement("i");
            icon.className = "bi bi-chat-left-text";
            const title = document.createElement("span");
            title.textContent = conversation.title;
            button.append(icon, title);
            button.addEventListener("click", () => openConversation(conversation.id));
            conversationList.append(button);
        });
    }

    async function loadConversations(selectMostRecent = false) {
        const response = await fetch(app.dataset.conversationsUrl, {
            headers: {"Accept": "application/json"},
            credentials: "same-origin"
        });
        if (!response.ok) throw new Error("Conversation history could not be loaded.");
        conversations = await response.json();
        if (selectMostRecent && conversations.length) {
            activeConversationId = conversations[0].id;
        }
        renderConversations();
    }

    async function openConversation(id) {
        clearError();
        activeConversationId = id;
        renderConversations();
        try {
            const response = await fetch(messagesUrl(id), {
                headers: {"Accept": "application/json"},
                credentials: "same-origin"
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "This conversation could not be opened.");
            renderMessages(result);
        } catch (error) {
            showError(error.message);
        }
    }

    async function createConversation() {
        const response = await fetch(app.dataset.conversationsUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken
            },
            body: JSON.stringify({})
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "A new conversation could not be created.");
        conversations.unshift(result);
        activeConversationId = result.id;
        renderConversations();
        renderMessages([]);
        return result.id;
    }

    async function sendMessage(prompt, mode) {
        clearError();
        setBusy(true);
        try {
            if (!activeConversationId) await createConversation();
            const response = await fetch(messagesUrl(activeConversationId), {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify({prompt, mode})
            });
            const result = await response.json();
            if (!response.ok) {
                const errorMessage = response.status === 429
                    ? (result.error || "Please wait before sending another message.")
                    : result.errors
                        ? "Please enter a valid question and try again."
                        : (result.error || "The AI tutor could not answer right now.");
                await openConversation(activeConversationId);
                showError(errorMessage);
                return;
            }
            result.messages.forEach(addMessage);
            welcomePanel.hidden = true;
            const updated = result.conversation;
            conversations = conversations.filter(item => item.id !== updated.id);
            conversations.unshift(updated);
            conversations = conversations.slice(0, 50);
            renderConversations();
            document.getElementById("messageScroll").scrollTop =
                document.getElementById("messageScroll").scrollHeight;
        } catch (error) {
            showError(error.message || "The AI tutor could not be reached. Please try again.");
        } finally {
            setBusy(false);
            promptInput.focus();
        }
    }

    chatForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const prompt = promptInput.value.trim();
        if (prompt.length < 2) {
            showError("Please enter a question with at least 2 characters.");
            return;
        }
        const mode = modeSelect.value;
        promptInput.value = "";
        characterCount.textContent = "0 / 6000";
        sendMessage(prompt, mode);
    });

    promptInput.addEventListener("input", () => {
        characterCount.textContent = `${promptInput.value.length} / 6000`;
    });

    promptInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            chatForm.requestSubmit();
        }
    });

    newChatButton.addEventListener("click", async () => {
        clearError();
        try {
            await createConversation();
            promptInput.focus();
        } catch (error) {
            showError(error.message);
        }
    });

    clearButton.addEventListener("click", async () => {
        if (!activeConversationId) return;
        if (!window.confirm("Delete this conversation and its messages? This cannot be undone.")) return;
        clearError();
        clearButton.disabled = true;
        try {
            const response = await fetch(deleteUrl(activeConversationId), {
                method: "DELETE",
                credentials: "same-origin",
                headers: {"X-CSRFToken": csrfToken, "Accept": "application/json"}
            });
            if (!response.ok) {
                const result = await response.json();
                throw new Error(result.error || "This conversation could not be deleted.");
            }
            conversations = conversations.filter(item => item.id !== activeConversationId);
            activeConversationId = null;
            renderConversations();
            renderMessages([]);
        } catch (error) {
            showError(error.message);
            clearButton.disabled = false;
        }
    });

    document.querySelectorAll(".ai-suggestion").forEach((button) => {
        button.addEventListener("click", () => {
            modeSelect.value = button.dataset.mode;
            promptInput.value = button.dataset.prompt;
            characterCount.textContent = `${promptInput.value.length} / 6000`;
            chatForm.requestSubmit();
        });
    });

    loadConversations(true).then(() => {
        if (activeConversationId) openConversation(activeConversationId);
        else renderMessages([]);
    }).catch((error) => showError(error.message));
})();
