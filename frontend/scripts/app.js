const API_BASE = window.CHRONOSALON_API_BASE || "";

const roomBackgrounds = {
  historical_scene: "/assets/backgrounds/historical-scene.png",
  cross_time: "/assets/backgrounds/cross-time.png"
};

const state = {
  room: null,
  messages: [],
  reviewReport: null,
  reviewVisible: false,
  reviewMonitor: null,
  buildMode: "historical_scene",
  roomStatus: "idle",
  statusText: "",
  pendingNodes: [],
  mention: {
    active: false,
    start: -1,
    end: -1,
    query: "",
    selectedIndex: 0,
    options: []
  }
};

const dom = {
  topicInput: document.querySelector("#topicInput"),
  topicSuggestions: document.querySelector("#topicSuggestions"),
  enterBtn: document.querySelector("#enterBtn"),
  entryStatus: document.querySelector("#entryStatus"),
  entryView: document.querySelector("#entryView"),
  roomTypeInputs: [...document.querySelectorAll('input[name="roomType"]')],
  roomTypeCards: [...document.querySelectorAll("[data-room-type-card]")],
  choicePanel: document.querySelector("#choicePanel"),
  chatLayout: document.querySelector("#chatLayout"),
  peopleList: document.querySelector("#peopleList"),
  chatMode: document.querySelector("#chatMode"),
  chatTitle: document.querySelector("#chatTitle"),
  messages: document.querySelector("#messages"),
  quickQuestions: document.querySelector("#quickQuestions"),
  composer: document.querySelector("#composer"),
  messageInput: document.querySelector("#messageInput"),
  mentionMenu: document.querySelector("#mentionMenu"),
  studyPanel: document.querySelector(".study-panel"),
  studyContent: document.querySelector("#studyContent"),
  newRoomBtn: document.querySelector("#newRoomBtn"),
  saveChatBtn: document.querySelector("#saveChatBtn"),
  clearChatBtn: document.querySelector("#clearChatBtn"),
  reviewBtn: document.querySelector("#reviewBtn"),
  exportReviewBtn: document.querySelector("#exportReviewBtn"),
  closeReviewBtn: document.querySelector("#closeReviewBtn")
};

const TOPIC_HISTORY_KEY = "chronosalon.topicHistory";
const MAX_TOPIC_HISTORY = 12;
const defaultTopics = ["安史之乱", "商鞅变法", "为什么改革总是困难？", "唐朝"];

const roomStatusText = {
  idle: "",
  entering: "正在进入聊天室...",
  choosing: "这个主题有点大，先选一个具体方向。",
  opening: "群主正在开场...",
  ready: "",
  responding: "人物正在回复...",
  reviewing: "正在生成学习回顾...",
  error: "操作失败，请稍后再试。"
};

async function postJson(path, payload) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`);
  }
  return response.json();
}

async function buildRoom(topic) {
  return postJson("/api/rooms/build", {
    topic,
    room_type: state.buildMode
  });
}

async function enterRoomFromTopic(topic) {
  const cleanTopic = topic.trim();
  if (!cleanTopic) {
    setRoomStatus("idle", "先输入一个历史主题。");
    dom.topicInput.focus();
    return;
  }

  recordTopic(cleanTopic);
  setRoomStatus("entering");
  try {
    const room = await buildRoom(cleanTopic);
    if (room.status === "needs_choice") {
      showChoicePanel(room);
      setRoomStatus("choosing");
      return;
    }
    state.room = room;
    dom.choicePanel.hidden = true;
    enterRoom();
  } catch (error) {
    setRoomStatus("error", "进入失败：请确认后端服务正在运行。");
  } finally {
    if (state.roomStatus === "entering") {
      setRoomStatus(state.room ? "opening" : "idle");
    }
  }
}

function setRoomStatus(status, text = "") {
  state.roomStatus = status;
  state.statusText = text || roomStatusText[status] || "";
  applyRoomStatus();
}

function setEntryStatus(text) {
  state.statusText = text;
  dom.entryStatus.textContent = text;
}

function applyRoomStatus() {
  const status = state.roomStatus;
  const isEntering = status === "entering";
  const isOpening = status === "opening";
  const isResponding = status === "responding";
  const isReviewing = status === "reviewing";
  const blocksComposer = isOpening || isResponding;
  const blocksBuilder = isEntering || isOpening || isResponding;

  document.body.dataset.roomStatus = status;
  dom.enterBtn.disabled = blocksBuilder;
  dom.topicInput.disabled = blocksBuilder;
  dom.roomTypeInputs.forEach((input) => {
    input.disabled = blocksBuilder;
  });
  dom.roomTypeCards.forEach((card) => {
    card.classList.toggle("disabled", blocksBuilder);
  });
  dom.messageInput.disabled = !state.room || blocksComposer;
  dom.composer.querySelector("button").disabled = !state.room || blocksComposer;
  dom.reviewBtn.disabled = !state.room || isReviewing;
  dom.exportReviewBtn.disabled = !state.room || isReviewing || !state.reviewReport;
  dom.closeReviewBtn.disabled = !state.reviewVisible || isReviewing;
  dom.saveChatBtn.disabled = !state.room;
  dom.clearChatBtn.disabled = !state.room || isResponding || isOpening;
  [...dom.quickQuestions.querySelectorAll("button")].forEach((button) => {
    button.disabled = blocksComposer;
  });

  dom.enterBtn.textContent = isEntering ? "进入中..." : "进入聊天室";
  dom.messageInput.placeholder = composerPlaceholderForStatus(status);
  dom.entryStatus.textContent = state.statusText;
  if (blocksComposer) {
    hideMentionMenu();
  }
}

function composerPlaceholderForStatus(status) {
  if (!state.room) return "@安禄山 你为什么要起兵？";
  if (status === "opening") return "群主正在开场...";
  if (status === "responding") return "人物正在回复...";
  return "@人物 输入你的问题，或直接发言让群主承接";
}

function showChoicePanel(room) {
  const options = room.options || [];
  const boundaryText = String(room.topic_boundary || "");
  const needsClarification = /无法可靠识别|信息还不足|请先补充/.test(boundaryText);
  const nextTitle = needsClarification ? "先补充主题信息" : "选一个子主题进入";
  const nextCopy = needsClarification
    ? "可以补充时代、关键人物或核心问题，系统再尝试建房。"
    : "聊天室会自动创建相关人物和推荐问题。";
  const eyebrow = needsClarification ? "需要补充" : "需要细化";
  dom.choicePanel.hidden = false;
  dom.choicePanel.innerHTML = `
    <div class="preview-grid">
      <div class="info-box">
        <p class="eyebrow">${eyebrow}</p>
        <h2>${escapeHtml(room.room_title)}</h2>
        <p>${escapeHtml(room.topic_boundary || "")}</p>
        <div class="chips option-chips">
          ${options.map((option) => `<button type="button" class="chip">${escapeHtml(option)}</button>`).join("")}
        </div>
      </div>
      <div class="info-box">
        <p class="eyebrow">下一步</p>
        <h2>${nextTitle}</h2>
        <p>${nextCopy}</p>
      </div>
    </div>
  `;
  [...dom.choicePanel.querySelectorAll(".option-chips button")].forEach((button) => {
    button.addEventListener("click", () => {
      dom.topicInput.value = button.textContent;
      enterRoomFromTopic(button.textContent);
    });
  });
}

function roomTypeLabel(type) {
  if (type === "historical_scene") return "历史现场";
  if (type === "cross_time") return "跨时空讨论";
  return "需要细化";
}

function setRoomVisual(type) {
  const roomType = type === "cross_time" ? "cross_time" : "historical_scene";
  document.body.dataset.roomType = roomType;
  const imagePath = roomBackgrounds[roomType];
  document.documentElement.style.setProperty("--room-bg-image", "none");

  const image = new Image();
  image.onload = () => {
    if (document.body.dataset.roomType === roomType) {
      document.documentElement.style.setProperty("--room-bg-image", `url("${imagePath}")`);
    }
  };
  image.src = imagePath;
}

function showEntryView() {
  resetReviewPanelUI();
  state.room = null;
  state.messages = [];
  state.pendingNodes = [];
  hideMentionMenu();
  clearTyping();
  dom.messages.innerHTML = "";
  dom.chatLayout.hidden = true;
  dom.choicePanel.hidden = true;
  dom.entryView.hidden = false;
  setRoomStatus("idle", "");
  dom.topicInput.focus();
}

function showChatView() {
  dom.entryView.hidden = true;
  dom.chatLayout.hidden = false;
}

function setBuildMode(type) {
  state.buildMode = type === "cross_time" ? "cross_time" : "historical_scene";
  dom.roomTypeInputs.forEach((input) => {
    input.checked = input.value === state.buildMode;
  });
  dom.roomTypeCards.forEach((card) => {
    card.classList.toggle("active", card.dataset.roomTypeCard === state.buildMode);
  });
  setRoomVisual(state.buildMode);
}

function enterRoom() {
  if (!state.room) return;
  resetReviewPanelUI();
  state.messages = [];
  state.pendingNodes = [];
  dom.messages.innerHTML = "";
  showChatView();
  setRoomVisual(state.room.room_type);
  dom.chatMode.textContent = roomTypeLabel(state.room.room_type);
  dom.chatTitle.textContent = state.room.room_title;
  renderPeople();
  renderQuickQuestions();
  setRoomStatus("opening", `已进入：${state.room.room_title}，群主正在开场...`);
  addOpening();
}

function renderPeople() {
  dom.peopleList.innerHTML = (state.room.characters || []).map((person) => `
    <article class="person ${person.is_temporary ? "temporary" : ""}">
      <strong>${escapeHtml(person.name)}</strong>
      <span>${escapeHtml(person.role || person.identity || person.type || "")}</span>
      ${person.is_temporary ? "<small>临时加入</small>" : ""}
    </article>
  `).join("");
  updateMentionMenu();
}

function isModeratorPerson(person) {
  return person?.type === "moderator" || person?.name === "群主" || person?.name === "历史助手";
}

function getMentionContext() {
  const input = dom.messageInput;
  const cursor = input.selectionStart;
  if (cursor === null || input.selectionEnd !== cursor) return null;

  const prefix = input.value.slice(0, cursor);
  const match = prefix.match(/@([^\s@，,。.!！?？:：]*)$/);
  if (!match) return null;

  const start = prefix.lastIndexOf("@");
  return {
    start,
    end: cursor,
    query: match[1] || ""
  };
}

function getMentionCandidates(query) {
  if (!state.room) return [];
  const normalizedQuery = query.trim();
  const people = (state.room.characters || [])
    .filter((person) => person?.name && !isModeratorPerson(person))
    .map((person) => ({
      name: person.name,
      role: person.role || person.identity || person.type || "",
      isTemporary: Boolean(person.is_temporary)
    }));
  const options = [
    { name: "所有人", role: "让当前群里的人物依次发言", isSpecial: true },
    ...people
  ];

  return options
    .filter((option) => {
      if (!normalizedQuery) return true;
      return option.name.includes(normalizedQuery) || option.role.includes(normalizedQuery);
    })
    .slice(0, 8);
}

function updateMentionMenu() {
  const context = getMentionContext();
  if (!context) {
    hideMentionMenu();
    return;
  }

  const options = getMentionCandidates(context.query);
  if (!options.length) {
    hideMentionMenu();
    return;
  }

  state.mention = {
    active: true,
    start: context.start,
    end: context.end,
    query: context.query,
    selectedIndex: Math.min(state.mention.selectedIndex, options.length - 1),
    options
  };
  renderMentionMenu();
}

function renderMentionMenu() {
  dom.mentionMenu.hidden = false;
  dom.mentionMenu.innerHTML = "";

  state.mention.options.forEach((option, index) => {
    const button = document.createElement("button");
    const name = document.createElement("strong");
    const role = document.createElement("span");
    const isActive = index === state.mention.selectedIndex;

    button.type = "button";
    button.setAttribute("role", "option");
    button.dataset.index = String(index);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
    button.className = isActive ? "active" : "";

    name.textContent = `@${option.name}`;
    role.textContent = `${option.role}${option.isTemporary ? " · 临时加入" : ""}`;

    button.appendChild(name);
    button.appendChild(role);

    button.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      event.stopPropagation();
      state.mention.selectedIndex = index;
      insertMention(index);
    });

    button.addEventListener("mouseenter", () => {
      state.mention.selectedIndex = index;
      syncMentionSelectionVisual();
    });

    dom.mentionMenu.appendChild(button);
  });
}

function hideMentionMenu() {
  state.mention.active = false;
  state.mention.options = [];
  state.mention.start = -1;
  state.mention.end = -1;
  state.mention.query = "";
  state.mention.selectedIndex = 0;
  dom.mentionMenu.hidden = true;
  dom.mentionMenu.innerHTML = "";
}

function moveMentionSelection(direction) {
  if (!state.mention.active || !state.mention.options.length) return;
  const total = state.mention.options.length;
  state.mention.selectedIndex = (state.mention.selectedIndex + direction + total) % total;
  renderMentionMenu();
}

function insertMention(index = state.mention.selectedIndex) {
  const option = state.mention.options[index];
  if (!option) return;

  const input = dom.messageInput;
  const before = input.value.slice(0, state.mention.start);
  const after = input.value.slice(state.mention.end).replace(/^\s*/, "");
  const mentionText = `@${option.name}`;
  input.value = `${before}${mentionText}${after ? ` ${after}` : " "}`;

  const cursor = before.length + mentionText.length + 1;
  hideMentionMenu();
  input.focus();
  input.setSelectionRange(cursor, cursor);
}

function syncMentionSelectionVisual() {
  [...dom.mentionMenu.querySelectorAll("button[data-index]")].forEach((button) => {
    const isActive = Number(button.dataset.index) === state.mention.selectedIndex;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });
}

function renderQuickQuestions() {
  dom.quickQuestions.innerHTML = (state.room.recommended_questions || []).map((question) => `
    <button type="button">${escapeHtml(question)}</button>
  `).join("");
  [...dom.quickQuestions.querySelectorAll("button")].forEach((button) => {
    button.addEventListener("click", () => {
      dom.messageInput.value = button.textContent;
      dom.messageInput.focus();
    });
  });
  applyRoomStatus();
}

function renderReviewLoading() {
  const title = state.room?.room_title || "本次主题";
  const monitor = state.reviewMonitor || {
    startedAt: Date.now(),
    phaseIndex: 0
  };
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - monitor.startedAt) / 1000));
  const steps = [
    "读取当前聊天室的全部聊天记录",
    "提炼关键知识点与人物分歧",
    "整理处世启发、易错点与追问方向"
  ];
  const activeIndex = Math.max(0, Math.min(monitor.phaseIndex, steps.length - 1));
  dom.studyContent.innerHTML = `
    <article class="study-report">
      <p class="eyebrow">正在整理</p>
      <h3>${escapeHtml(title)} 学习回顾</h3>
      <p class="study-summary">系统正在基于当前聊天室的全部聊天记录生成学习回顾报告。报告生成完成后才会展示正式内容。</p>
      <div class="study-meta">
        <span>状态：生成中...</span>
        <span>已等待 ${elapsedSeconds} 秒</span>
      </div>
      <section class="study-section">
        <h4>进度监控</h4>
        <ul>
          ${steps.map((step, index) => `
            <li>${index < activeIndex ? "已完成" : index === activeIndex ? "进行中" : "等待中"}：${step}</li>
          `).join("")}
        </ul>
      </section>
    </article>
  `;
}

function setReviewVisibility(visible) {
  state.reviewVisible = Boolean(visible);
  dom.studyPanel.hidden = !state.reviewVisible;
  dom.chatLayout.classList.toggle("with-study-panel", state.reviewVisible);
}

function resetReviewPanelUI() {
  stopReviewMonitor();
  state.reviewReport = null;
  state.reviewVisible = false;
  dom.studyContent.innerHTML = "";
  dom.studyPanel.hidden = true;
  dom.chatLayout.classList.remove("with-study-panel");
}

function startReviewMonitor() {
  stopReviewMonitor();
  state.reviewMonitor = {
    startedAt: Date.now(),
    phaseIndex: 0,
    timerId: window.setInterval(() => {
      if (state.roomStatus !== "reviewing" || !state.reviewVisible) return;
      const elapsedSeconds = Math.floor((Date.now() - state.reviewMonitor.startedAt) / 1000);
      state.reviewMonitor.phaseIndex = Math.min(2, Math.floor(elapsedSeconds / 2));
      renderReviewLoading();
    }, 1000)
  };
}

function stopReviewMonitor() {
  if (state.reviewMonitor?.timerId) {
    window.clearInterval(state.reviewMonitor.timerId);
  }
  state.reviewMonitor = null;
}

function renderStudyReport(review) {
  const report = review?.study_report;
  const sections = report?.sections || [];
  const meta = report?.meta || {};
  const metaItems = [
    `参考发言 ${Number(meta.message_count || 0)} 条`,
    `参与角色 ${Number(meta.participant_count || 0)} 位`,
    meta.room_type_label || ""
  ].filter(Boolean);
  dom.studyContent.innerHTML = `
    <article class="study-report">
      <p class="eyebrow">学习回顾</p>
      <h3>${escapeHtml(report?.title || `${state.room?.room_title || "本次主题"} 学习回顾`)}</h3>
      <p class="study-summary">${escapeHtml(report?.summary || "已整理本次对话中的学习要点。")}</p>
      <div class="study-meta">
        ${metaItems.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
      </div>
      ${sections.map((section) => `
        <section class="study-section">
          <h4>${escapeHtml(section.title || "")}</h4>
          <ul>
            ${(section.items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
          </ul>
        </section>
      `).join("")}
    </article>
  `;
}

async function addOpening() {
  setRoomStatus("opening", state.statusText || "群主正在开场...");
  try {
    const planPayload = await postJson("/api/chat/plan", {
      room: state.room,
      message: "开场",
      recent_messages: state.messages,
      use_llm: false
    });
    applyRoomUpdate(planPayload);
    showTypingFromPlan(planPayload.plan);
    const payload = await postJson("/api/chat", {
      room: state.room,
      message: "开场",
      recent_messages: state.messages,
      use_llm: false
    });
    clearTyping();
    applyChatPayload(payload);
    setRoomStatus("ready", `已进入：${state.room.room_title}`);
  } catch (error) {
    clearTyping();
    appendSystemHint("开场请求失败，使用本地提示继续。");
    appendMessage("群主", `${state.room.room_title}聊天室开张。先听当事人说，再把线索捋清楚。`, "moderator", ["开场"]);
    setRoomStatus("ready", `已进入：${state.room.room_title}`);
  }
}

function applyRoomUpdate(payload) {
  if (payload.room) {
    state.room = payload.room;
    renderPeople();
  }
  if (payload.added_character) {
    appendSystemHint(`${payload.added_character.name} 已临时加入，只围绕当前主题发言。`);
  }
}

function applyChatPayload(payload) {
  applyRoomUpdate(payload);
  appendMessages(payload.messages || []);
}

function showTypingFromPlan(plan) {
  clearTyping();
  const speakers = (plan?.speaker_sequence || []).slice(0, plan?.max_auto_messages || 4).map((step) => step.speaker);
  speakers.forEach((speaker) => {
    state.pendingNodes.push(appendTyping(speaker));
  });
}

function appendTyping(speaker) {
  const node = document.createElement("article");
  node.className = "message typing";
  node.dataset.pending = "true";
  node.innerHTML = `
    <div class="name"><span>${escapeHtml(speaker)}</span></div>
    <div class="typing-dots"><span></span><span></span><span></span> ${escapeHtml(speaker)} 输入中...</div>
  `;
  dom.messages.appendChild(node);
  dom.messages.scrollTop = dom.messages.scrollHeight;
  return node;
}

function clearTyping() {
  state.pendingNodes.forEach((node) => node.remove());
  state.pendingNodes = [];
}

function appendMessages(messages) {
  messages.forEach((message) => {
    appendMessage(
      message.sender_name,
      message.content,
      message.sender_type === "student" ? "student" : message.sender_type === "moderator" ? "moderator" : "character",
      message.labels || []
    );
  });
}

function appendMessage(name, content, type, labels = []) {
  state.messages.push({
    sender_name: name,
    content,
    sender_type: type === "student" ? "student" : type === "moderator" ? "moderator" : "character",
    labels
  });
  const node = document.createElement("article");
  node.className = `message ${type}`;
  node.innerHTML = `
    <div class="name"><span>${escapeHtml(name)}</span></div>
    <div>${escapeHtml(content)}</div>
    <div class="labels">${labels.map((label) => `<span>${escapeHtml(label)}</span>`).join("")}</div>
  `;
  dom.messages.appendChild(node);
  dom.messages.scrollTop = dom.messages.scrollHeight;
}

function clearChatHistory() {
  if (!state.room) return;
  if (!window.confirm("确定清空当前聊天室的聊天记录吗？这不会删除人物和学习线索。")) {
    return;
  }
  clearTyping();
  state.messages = [];
  state.reviewReport = null;
  stopReviewMonitor();
  setReviewVisibility(false);
  dom.messages.innerHTML = "";
  dom.studyContent.innerHTML = "";
  appendSystemHint("聊天记录已清空。");
  setRoomStatus("ready", "聊天记录已清空。");
}

function saveChatHistory() {
  if (!state.room) {
    setRoomStatus("idle", "先进入一个聊天室，再保存记录。");
    return;
  }
  const lines = [
    `# ${state.room.room_title} 聊天记录`,
    "",
    `- 聊天室类型：${roomTypeLabel(state.room.room_type)}`,
    `- 导出时间：${new Date().toLocaleString("zh-CN")}`,
    "",
    "## 学习目标",
    ...(state.room.learning_goals || []).map((goal) => `- ${goal}`),
    "",
    "## 参与人物",
    ...(state.room.characters || []).map((person) => `- ${person.name}：${person.role || person.identity || person.type || ""}`),
    "",
    "## 对话",
    ""
  ];

  if (!state.messages.length) {
    lines.push("_暂无聊天记录。_");
  } else {
    state.messages.forEach((message) => {
      const labels = message.labels?.length ? `（${message.labels.join("、")}）` : "";
      lines.push(`### ${message.sender_name}${labels}`);
      lines.push("");
      lines.push(message.content || "");
      lines.push("");
    });
  }

  const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${sanitizeFileName(state.room.room_title)}-聊天记录.md`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  setRoomStatus("ready", "聊天记录已保存为 Markdown 文件。");
}

function sanitizeFileName(value) {
  return String(value || "ChronoSalon")
    .replace(/[\\/:*?"<>|]/g, "_")
    .slice(0, 60);
}

function appendSystemHint(text) {
  const node = document.createElement("article");
  node.className = "message moderator";
  node.innerHTML = `<div class="name"><span>系统提示</span></div><div>${escapeHtml(text)}</div>`;
  dom.messages.appendChild(node);
  dom.messages.scrollTop = dom.messages.scrollHeight;
}

async function sendStudentMessage(text) {
  if (state.roomStatus === "opening" || state.roomStatus === "responding") return;
  setRoomStatus("responding");
  appendMessage("我", text, "student", ["学生"]);
  try {
    const planPayload = await postJson("/api/chat/plan", {
      room: state.room,
      message: text,
      recent_messages: state.messages,
      use_llm: false
    });
    applyRoomUpdate(planPayload);
    showTypingFromPlan(planPayload.plan);

    const payload = await postJson("/api/chat", {
      room: state.room,
      message: text,
      recent_messages: state.messages,
      use_llm: true
    });
    clearTyping();
    applyChatPayload(payload);
    setRoomStatus("ready", `已进入：${state.room.room_title}`);
  } catch (error) {
    clearTyping();
    appendSystemHint("后端聊天接口暂时不可用。可以先检查服务是否已启动。");
    setRoomStatus("error", "后端聊天接口暂时不可用。");
  }
}

async function generateReview() {
  if (!state.room) return;
  const previousStatus = state.roomStatus;
  startReviewMonitor();
  setReviewVisibility(true);
  renderReviewLoading();
  setRoomStatus("reviewing");
  try {
    const review = await postJson("/api/review", {
      room: state.room,
      messages: state.messages
    });
    stopReviewMonitor();
    state.reviewReport = review;
    renderStudyReport(review);
    setRoomStatus(previousStatus === "idle" ? "idle" : "ready", `学习回顾已更新：${state.room.room_title}`);
  } catch (error) {
    stopReviewMonitor();
    state.reviewReport = null;
    dom.studyContent.innerHTML = `
      <article class="study-report">
        <h3>学习回顾</h3>
        <p class="study-summary">后端回顾接口暂时不可用，请确认服务已启动。</p>
      </article>
    `;
    setRoomStatus("error", "学习回顾生成失败，请确认服务已启动。");
  }
}

function exportReviewReport() {
  if (!state.room || !state.reviewReport?.report_markdown) {
    setRoomStatus("ready", "请先生成学习回顾，再导出报告。");
    return;
  }
  const blob = new Blob([state.reviewReport.report_markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${sanitizeFileName(state.room.room_title)}-学习回顾.md`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  setRoomStatus("ready", "学习回顾已导出为 Markdown 文件。");
}

function closeReviewPanel() {
  if (!state.room) return;
  stopReviewMonitor();
  setReviewVisibility(false);
  setRoomStatus("ready", `已收起：${state.room.room_title} 学习回顾`);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function loadTopicHistory() {
  try {
    const raw = window.localStorage.getItem(TOPIC_HISTORY_KEY);
    if (!raw) return [...defaultTopics];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [...defaultTopics];
    return mergeTopics(parsed, defaultTopics);
  } catch (error) {
    return [...defaultTopics];
  }
}

function saveTopicHistory(topics) {
  try {
    window.localStorage.setItem(TOPIC_HISTORY_KEY, JSON.stringify(topics));
  } catch (error) {
    return;
  }
}

function mergeTopics(...topicGroups) {
  const seen = new Set();
  const merged = [];
  topicGroups.flat().forEach((topic) => {
    const cleanTopic = String(topic || "").trim();
    if (!cleanTopic || seen.has(cleanTopic)) return;
    seen.add(cleanTopic);
    merged.push(cleanTopic);
  });
  return merged.slice(0, MAX_TOPIC_HISTORY);
}

function renderTopicSuggestions(topics = loadTopicHistory()) {
  dom.topicSuggestions.innerHTML = topics
    .map((topic) => `<option value="${escapeHtml(topic)}"></option>`)
    .join("");
}

function recordTopic(topic) {
  const cleanTopic = String(topic || "").trim();
  if (!cleanTopic) return;
  const history = mergeTopics([cleanTopic], loadTopicHistory());
  saveTopicHistory(history);
  renderTopicSuggestions(history);
}

dom.roomTypeInputs.forEach((input) => {
  input.addEventListener("change", () => {
    if (input.checked) {
      setBuildMode(input.value);
    }
  });
});

dom.roomTypeCards.forEach((card) => {
  card.addEventListener("click", () => {
    if (state.roomStatus === "entering" || state.roomStatus === "opening" || state.roomStatus === "responding") return;
    setBuildMode(card.dataset.roomTypeCard);
  });
});

dom.enterBtn.addEventListener("click", () => {
  enterRoomFromTopic(dom.topicInput.value);
});

dom.topicInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    enterRoomFromTopic(dom.topicInput.value);
  }
});

dom.messageInput.addEventListener("input", () => {
  state.mention.selectedIndex = 0;
  updateMentionMenu();
});

dom.messageInput.addEventListener("click", updateMentionMenu);

dom.messageInput.addEventListener("keydown", (event) => {
  if (!state.mention.active) return;

  if (event.key === "ArrowDown") {
    event.preventDefault();
    moveMentionSelection(1);
    return;
  }
  if (event.key === "ArrowUp") {
    event.preventDefault();
    moveMentionSelection(-1);
    return;
  }
  if (event.key === "Enter" || event.key === "Tab") {
    event.preventDefault();
    insertMention();
    return;
  }
  if (event.key === "Escape") {
    event.preventDefault();
    hideMentionMenu();
  }
});

document.addEventListener("click", (event) => {
  if (event.target === dom.messageInput || dom.mentionMenu.contains(event.target)) return;
  hideMentionMenu();
});

dom.composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = dom.messageInput.value.trim();
  if (!text || !state.room || state.roomStatus === "opening" || state.roomStatus === "responding") return;
  dom.messageInput.value = "";
  hideMentionMenu();
  await sendStudentMessage(text);
});

dom.newRoomBtn.addEventListener("click", showEntryView);
dom.saveChatBtn.addEventListener("click", saveChatHistory);
dom.clearChatBtn.addEventListener("click", clearChatHistory);
dom.reviewBtn.addEventListener("click", generateReview);
dom.exportReviewBtn.addEventListener("click", exportReviewReport);
dom.closeReviewBtn.addEventListener("click", closeReviewPanel);
window.addEventListener("pageshow", () => {
  if (!state.room) {
    resetReviewPanelUI();
  }
});

resetReviewPanelUI();
renderTopicSuggestions();
setBuildMode(state.buildMode);
applyRoomStatus();
