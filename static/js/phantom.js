/* phantom_ — interaction layer + localStorage backend.
   No frameworks, no trackers. Vanilla JS, ~zero cost at startup. */

(function () {
  "use strict";

  /* ========================================================================
     Store — the localStorage backend. Everything persists on this device.
     ======================================================================== */

  const DB_KEY = "phantom.db.v1";

  const store = {
    _state: null,
    _load() {
      if (this._state) return this._state;
      try { this._state = JSON.parse(localStorage.getItem(DB_KEY)) || {}; }
      catch { this._state = {}; }
      const s = this._state;
      s.messages  = s.messages  || {};   // convId -> [msg]
      s.drafts    = s.drafts    || {};
      s.reactions = s.reactions || {};
      s.pins      = s.pins      || [];
      s.prefs     = s.prefs     || {};
      s.convos    = s.convos    || [];   // local conversations [{id,title,created}]
      s.joins     = s.joins     || [];   // joined explore-space ids
      s.profile   = s.profile   || null; // {name, handle}
      return s;
    },
    _save() { localStorage.setItem(DB_KEY, JSON.stringify(this._state)); },

    addMessage(convId, msg) { const s = this._load(); (s.messages[convId] = s.messages[convId] || []).push(msg); this._save(); },
    getMessages(convId) { return this._load().messages[convId] || []; },

    setDraft(convId, text) { const s = this._load(); if (text) s.drafts[convId] = text; else delete s.drafts[convId]; this._save(); },
    getDraft(convId) { return this._load().drafts[convId] || ""; },

    toggleReaction(msgId, glyph) {
      const s = this._load();
      const list = (s.reactions[msgId] = s.reactions[msgId] || []);
      const i = list.indexOf(glyph);
      if (i >= 0) list.splice(i, 1); else list.push(glyph);
      if (!list.length) delete s.reactions[msgId];
      this._save();
      return s.reactions[msgId] || [];
    },
    getReactions(msgId) { return this._load().reactions[msgId] || []; },

    addPin(pin) {
      const s = this._load();
      if (!s.pins.some((p) => p.id === pin.id)) { s.pins.unshift(pin); this._save(); return true; }
      return false;
    },
    getPins() { return this._load().pins; },

    addConvo(c) { const s = this._load(); s.convos.unshift(c); this._save(); },
    getConvos() { return this._load().convos; },

    toggleJoin(id) {
      const s = this._load();
      const i = s.joins.indexOf(id);
      if (i >= 0) s.joins.splice(i, 1); else s.joins.push(id);
      this._save();
      return i < 0;
    },
    isJoined(id) { return this._load().joins.includes(id); },

    setProfile(p) { const s = this._load(); s.profile = p; this._save(); },
    getProfile() { return this._load().profile; },

    setPref(k, v) { const s = this._load(); s.prefs[k] = v; this._save(); },
    getPref(k, fb) { const v = this._load().prefs[k]; return v === undefined ? fb : v; },
  };

  /* ========================================================================
     i18n — instant, zero-reload language transitions.
     ======================================================================== */

  const I18N = {
    en: { home: "Home", messages: "Messages", spaces: "Spaces", moments: "Moments",
          people: "People", calls: "Calls", media: "Media", settings: "Settings", search: "Search",
          ghost_mode: "Ghost mode", on: "ON", off: "OFF", pinned: "Pinned",
          message_placeholder: "Message…", send: "Send", delivered: "delivered",
          recent: "Recent", active_spaces: "Active spaces",
          quick_actions: "Quick actions", new_message: "New message",
          today: "Today", yesterday: "Yesterday",
          last_week: "Last week", last_month: "Last month", pinned_by_you: "Pinned by you",
          profile: "Profile", privacy: "Privacy", appearance: "Appearance",
          languages: "Languages", accessibility: "Accessibility",
          download: "Get phantom", open_app: "Open the app", members: "members" },
    hi: { home: "होम", messages: "संदेश", spaces: "स्पेसेस", moments: "क्षण",
          people: "लोग", calls: "कॉल", media: "मीडिया", settings: "सेटिंग्स", search: "खोजें",
          ghost_mode: "घोस्ट मोड", on: "चालू", off: "बंद", pinned: "पिन किए गए",
          message_placeholder: "संदेश…", send: "भेजें", delivered: "पहुँच गया",
          recent: "हाल के", active_spaces: "सक्रिय स्पेसेस",
          quick_actions: "त्वरित क्रियाएँ", new_message: "नया संदेश",
          today: "आज", yesterday: "कल",
          last_week: "पिछला सप्ताह", last_month: "पिछला महीना", pinned_by_you: "आपके द्वारा पिन किए गए",
          profile: "प्रोफ़ाइल", privacy: "गोपनीयता", appearance: "रूप",
          languages: "भाषाएँ", accessibility: "सुलभता",
          download: "phantom पाएं", open_app: "ऐप खोलें", members: "सदस्य" },
    es: { home: "Inicio", messages: "Mensajes", spaces: "Espacios", moments: "Momentos",
          people: "Personas", calls: "Llamadas", media: "Multimedia", settings: "Ajustes", search: "Buscar",
          ghost_mode: "Modo fantasma", on: "SÍ", off: "NO", pinned: "Fijados",
          message_placeholder: "Mensaje…", send: "Enviar", delivered: "entregado",
          recent: "Recientes", active_spaces: "Espacios activos",
          quick_actions: "Acciones rápidas", new_message: "Nuevo mensaje",
          today: "Hoy", yesterday: "Ayer",
          last_week: "La semana pasada", last_month: "El mes pasado", pinned_by_you: "Fijado por ti",
          profile: "Perfil", privacy: "Privacidad", appearance: "Apariencia",
          languages: "Idiomas", accessibility: "Accesibilidad",
          download: "Obtener phantom", open_app: "Abrir la app", members: "miembros" },
    fr: { home: "Accueil", messages: "Messages", spaces: "Espaces", moments: "Moments",
          people: "Personnes", calls: "Appels", media: "Médias", settings: "Réglages", search: "Rechercher",
          ghost_mode: "Mode fantôme", on: "OUI", off: "NON", pinned: "Épinglés",
          message_placeholder: "Message…", send: "Envoyer", delivered: "distribué",
          recent: "Récents", active_spaces: "Espaces actifs",
          quick_actions: "Actions rapides", new_message: "Nouveau message",
          today: "Aujourd'hui", yesterday: "Hier",
          last_week: "La semaine dernière", last_month: "Le mois dernier", pinned_by_you: "Épinglé par vous",
          profile: "Profil", privacy: "Confidentialité", appearance: "Apparence",
          languages: "Langues", accessibility: "Accessibilité",
          download: "Obtenir phantom", open_app: "Ouvrir l'app", members: "membres" },
    de: { home: "Start", messages: "Nachrichten", spaces: "Räume", moments: "Momente",
          people: "Menschen", calls: "Anrufe", media: "Medien", settings: "Einstellungen", search: "Suchen",
          ghost_mode: "Geistmodus", on: "AN", off: "AUS", pinned: "Angeheftet",
          message_placeholder: "Nachricht…", send: "Senden", delivered: "zugestellt",
          recent: "Zuletzt", active_spaces: "Aktive Räume",
          quick_actions: "Schnellaktionen", new_message: "Neue Nachricht",
          today: "Heute", yesterday: "Gestern",
          last_week: "Letzte Woche", last_month: "Letzter Monat", pinned_by_you: "Von dir angeheftet",
          profile: "Profil", privacy: "Privatsphäre", appearance: "Erscheinungsbild",
          languages: "Sprachen", accessibility: "Barrierefreiheit",
          download: "phantom holen", open_app: "App öffnen", members: "Mitglieder" },
    ja: { home: "ホーム", messages: "メッセージ", spaces: "スペース", moments: "モーメント",
          people: "メンバー", calls: "通話", media: "メディア", settings: "設定", search: "検索",
          ghost_mode: "ゴーストモード", on: "オン", off: "オフ", pinned: "ピン留め",
          message_placeholder: "メッセージ…", send: "送信", delivered: "配信済み",
          recent: "最近", active_spaces: "アクティブなスペース",
          quick_actions: "クイック操作", new_message: "新規メッセージ",
          today: "今日", yesterday: "昨日",
          last_week: "先週", last_month: "先月", pinned_by_you: "あなたのピン",
          profile: "プロフィール", privacy: "プライバシー", appearance: "外観",
          languages: "言語", accessibility: "アクセシビリティ",
          download: "phantomを入手", open_app: "アプリを開く", members: "人" },
    ar: { home: "الرئيسية", messages: "الرسائل", spaces: "المساحات", moments: "اللحظات",
          people: "الأشخاص", calls: "المكالمات", media: "الوسائط", settings: "الإعدادات", search: "بحث",
          ghost_mode: "وضع الشبح", on: "مفعل", off: "معطل", pinned: "مثبتة",
          message_placeholder: "…رسالة", send: "إرسال", delivered: "تم التسليم",
          recent: "الأحدث", active_spaces: "المساحات النشطة",
          quick_actions: "إجراءات سريعة", new_message: "رسالة جديدة",
          today: "اليوم", yesterday: "أمس",
          last_week: "الأسبوع الماضي", last_month: "الشهر الماضي", pinned_by_you: "مثبت بواسطتك",
          profile: "الملف الشخصي", privacy: "الخصوصية", appearance: "المظهر",
          languages: "اللغات", accessibility: "إمكانية الوصول",
          download: "احصل على phantom", open_app: "افتح التطبيق", members: "أعضاء" },
  };

  let lang = store.getPref("lang", document.documentElement.lang || "en");

  function t(key) { return (I18N[lang] && I18N[lang][key]) || I18N.en[key] || key; }

  function applyLanguage(next, persistRemote) {
    lang = I18N[next] ? next : "en";
    store.setPref("lang", lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
    document.querySelectorAll(".lang-btn[data-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
    if (persistRemote) {
      fetch("/api/language", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lang }) }).catch(() => {});
    }
  }

  /* ========================================================================
     Ghost mode
     ======================================================================== */

  let ghost = store.getPref("ghost", false);

  function applyGhost(enabled, persistRemote) {
    ghost = enabled;
    store.setPref("ghost", enabled);
    document.body.classList.toggle("ghost-on", enabled);
    document.querySelectorAll("[data-ghost-toggle]").forEach((el) => {
      el.setAttribute("aria-pressed", String(enabled));
      el.setAttribute("aria-checked", String(enabled));
      const state = el.querySelector(".state");
      if (state) state.textContent = enabled ? t("on") : t("off");
    });
    if (persistRemote) {
      fetch("/api/ghost", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }) }).catch(() => {});
    }
  }

  /* ========================================================================
     Skins — dark / onyx / light / high contrast
     ======================================================================== */

  function applySkin(skin) {
    const valid = ["dark", "onyx", "light", "contrast"];
    skin = valid.includes(skin) ? skin : "dark";
    store.setPref("skin", skin);
    document.documentElement.dataset.skin = skin;
    document.querySelectorAll("[data-skin-pick]").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.skinPick === skin)));
  }

  /* ========================================================================
     Themes — the chosen world re-skins the whole app
     ======================================================================== */

  function atmData() {
    const el = document.getElementById("atm-data");
    return el ? JSON.parse(el.textContent) : {};
  }

  function applyTheme(key) {
    const atms = atmData();
    if (!atms[key]) return;
    store.setPref("theme", key);
    document.documentElement.style.setProperty("--theme-img", `url('/static/${atms[key].src}')`);
    // home view floats in the chosen world too
    if (document.body.dataset.view === "home") {
      const el = document.querySelector(".content > .atmosphere");
      if (el) el.className = "atmosphere atm-" + key;
    }
    document.querySelectorAll("[data-atm-default]").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.atmDefault === key)));
  }

  /* ========================================================================
     Profile — set during onboarding, painted everywhere
     ======================================================================== */

  function applyProfile() {
    // signed-in users are painted by the server; localStorage profile is for guests
    if (document.body.dataset.guest === "0") return;
    const p = store.getProfile();
    if (!p) return;
    document.querySelectorAll("[data-profile-name]").forEach((el) => { el.textContent = p.name; });
    document.querySelectorAll("[data-profile-handle]").forEach((el) => { el.textContent = p.handle; });
    document.querySelectorAll("[data-profile-avatar]").forEach((el) => {
      el.textContent = (p.name || "?").trim().split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toLowerCase();
    });
  }

  /* ========================================================================
     Preferences (appearance / accessibility)
     ======================================================================== */

  function applyPrefs() {
    const opacity = store.getPref("atmOpacity", null);
    if (opacity !== null) {
      document.querySelectorAll(".content > .atmosphere, .landing > .atmosphere").forEach((el) => { el.style.opacity = opacity / 100; });
      const r = document.getElementById("atm-range"); if (r) r.value = opacity;
    }
    const scale = store.getPref("textScale", null);
    if (scale !== null) {
      document.documentElement.style.fontSize = scale + "%";
      const r = document.getElementById("text-scale"); if (r) r.value = scale;
    }
    const theme = store.getPref("theme", null);
    if (theme) applyTheme(theme);
    applySkin(store.getPref("skin", "dark"));
  }

  function initPrefControls() {
    const atmRange = document.getElementById("atm-range");
    if (atmRange) atmRange.addEventListener("input", (e) => {
      store.setPref("atmOpacity", +e.target.value);
      document.querySelectorAll(".content > .atmosphere").forEach((el) => { el.style.opacity = e.target.value / 100; });
    });
    const textRange = document.getElementById("text-scale");
    if (textRange) textRange.addEventListener("input", (e) => {
      store.setPref("textScale", +e.target.value);
      document.documentElement.style.fontSize = e.target.value + "%";
    });
    document.querySelectorAll("[data-atm-default]").forEach((btn) =>
      btn.addEventListener("click", () => applyTheme(btn.dataset.atmDefault)));
    document.querySelectorAll("[data-skin-pick]").forEach((btn) =>
      btn.addEventListener("click", () => applySkin(btn.dataset.skinPick)));
  }

  /* ========================================================================
     Command center
     ======================================================================== */

  function initCommandCenter() {
    const backdrop = document.getElementById("cmdk");
    if (!backdrop) return;
    const input = backdrop.querySelector("input");
    const list = backdrop.querySelector(".cmdk-list");
    const base = JSON.parse(document.getElementById("cmdk-data").textContent);
    let sel = 0, filtered = [];

    function allItems() {
      const locals = store.getConvos().map((c) => ({ title: c.title, hint: "local chat", href: "/app/messages/" + c.id + "?t=" + encodeURIComponent(c.title) }));
      return base.concat(locals);
    }

    function render() {
      list.innerHTML = "";
      if (!filtered.length) {
        list.innerHTML = '<div class="cmdk-empty">nothing here — try another word</div>';
        return;
      }
      filtered.forEach((it, i) => {
        const btn = document.createElement("button");
        btn.className = "cmdk-item" + (i === sel ? " sel" : "");
        btn.setAttribute("role", "option");
        btn.innerHTML =
          '<span class="cube" style="width:18px;height:18px"><span class="cube-core" style="width:9px;height:9px;border-radius:2px"></span></span>' +
          "<span></span><span class='hint'></span>";
        btn.children[1].textContent = it.title;
        btn.children[2].textContent = it.hint;
        btn.addEventListener("click", () => go(it));
        list.appendChild(btn);
      });
    }

    function go(it) {
      if (it.action === "ghost") { applyGhost(!ghost, true); close(); return; }
      if (it.action === "new-convo") { close(); startNewConvo(); return; }
      window.location.href = it.href;
    }

    function open() {
      backdrop.classList.add("open");
      input.value = "";
      filtered = allItems(); sel = 0; render();
      input.focus();
    }
    function close() { backdrop.classList.remove("open"); }

    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      filtered = allItems().filter((it) => (it.title + " " + it.hint).toLowerCase().includes(q));
      sel = 0; render();
    });

    document.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        backdrop.classList.contains("open") ? close() : open();
      } else if (backdrop.classList.contains("open")) {
        if (e.key === "Escape") close();
        if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(sel + 1, filtered.length - 1); render(); }
        if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(sel - 1, 0); render(); }
        if (e.key === "Enter" && filtered[sel]) go(filtered[sel]);
      }
    });

    backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
    document.querySelectorAll("[data-cmdk-open]").forEach((el) => el.addEventListener("click", open));
  }

  /* ========================================================================
     Local conversations
     ======================================================================== */

  function convoHref(c) { return "/app/messages/" + c.id + "?t=" + encodeURIComponent(c.title); }

  function startNewConvo() {
    const list = document.getElementById("convo-list");
    const make = (title) => {
      title = (title || "").trim();
      if (!title) return;
      const c = { id: "local-" + Date.now().toString(36), title, created: Date.now() };
      store.addConvo(c);
      window.location.href = convoHref(c);
    };
    if (!list) {
      // not on the messages page — go there and create inline
      const title = window.prompt("Name this conversation:");
      if (title) make(title);
      return;
    }
    if (document.getElementById("new-convo-row")) { document.querySelector("#new-convo-row input").focus(); return; }
    const row = document.createElement("form");
    row.id = "new-convo-row";
    row.className = "convo-item";
    row.style.gap = "10px";
    row.innerHTML = '<span class="avatar" aria-hidden="true">+</span>' +
      '<input type="text" placeholder="Name this conversation…" aria-label="Conversation name" style="flex:1;font-size:13px">';
    row.addEventListener("submit", (e) => { e.preventDefault(); make(row.querySelector("input").value); });
    list.prepend(row);
    row.querySelector("input").focus();
  }

  function renderLocalConvos() {
    const list = document.getElementById("convo-list");
    const home = document.getElementById("home-local-convos");
    const convos = store.getConvos();
    const current = location.pathname.split("/").pop();
    convos.forEach((c) => {
      const last = store.getMessages(c.id).slice(-1)[0];
      if (list) {
        const a = document.createElement("a");
        a.className = "convo-item" + (current === c.id ? " active" : "");
        a.dataset.kind = "local";
        a.href = convoHref(c);
        a.innerHTML = '<span class="avatar" aria-hidden="true"></span>' +
          '<div class="meta"><div class="name"></div><div class="last"></div></div>';
        a.querySelector(".avatar").textContent = c.title.slice(0, 2).toLowerCase();
        a.querySelector(".name").textContent = c.title;
        a.querySelector(".last").textContent = last ? last.body : "no messages yet";
        list.appendChild(a);
      }
      if (home) {
        const a = document.createElement("a");
        a.className = "row-item";
        a.href = convoHref(c);
        a.innerHTML = '<span class="avatar" aria-hidden="true"></span>' +
          '<div style="min-width:0;flex:1"><div class="name"></div><div class="sub"></div></div>';
        a.querySelector(".avatar").textContent = c.title.slice(0, 2).toLowerCase();
        a.querySelector(".name").textContent = c.title;
        a.querySelector(".sub").textContent = last ? last.body : "no messages yet";
        home.appendChild(a);
      }
    });

    const btn = document.getElementById("new-convo-btn");
    if (btn) btn.addEventListener("click", startNewConvo);

    // conversation tabs
    document.querySelectorAll("[data-convo-tab]").forEach((tab) => {
      tab.addEventListener("click", () => {
        document.querySelectorAll("[data-convo-tab]").forEach((b) => b.setAttribute("aria-selected", String(b === tab)));
        const f = tab.dataset.convoTab;
        document.querySelectorAll("#convo-list .convo-item").forEach((item) => {
          item.style.display = f === "all" || item.dataset.kind === f ? "" : "none";
        });
      });
    });
  }

  /* ========================================================================
     Messages — composer, AI relay, reactions, pins, attachments
     ======================================================================== */

  const REACTION_GLYPHS = ["✦", "❍", "△", "↑"];

  function bubbleActions(row, msgId, bodyText, convTitle, atmosphere) {
    const bar = document.createElement("div");
    bar.className = "bubble-actions";
    REACTION_GLYPHS.forEach((g) => {
      const b = document.createElement("button");
      b.textContent = g;
      b.setAttribute("aria-label", "React " + g);
      b.addEventListener("click", () => renderReactionChips(row, msgId, store.toggleReaction(msgId, g)));
      bar.appendChild(b);
    });
    const pin = document.createElement("button");
    pin.innerHTML = '<svg class="icon"><use href="#i-pin"/></svg>';
    pin.setAttribute("aria-label", "Pin to moments");
    pin.addEventListener("click", () => {
      store.addPin({
        id: msgId, kind: "text",
        title: bodyText.length > 48 ? "“" + bodyText.slice(0, 48) + "…”" : "“" + bodyText + "”",
        note: "pinned from " + convTitle, source: "you", atmosphere: atmosphere || "glass-cube",
      });
      pin.style.color = "#fff";
    });
    bar.appendChild(pin);
    row.appendChild(bar);
  }

  function renderReactionChips(row, msgId, list) {
    let chips = row.nextElementSibling;
    if (!chips || !chips.classList.contains("reaction-chips")) {
      chips = document.createElement("div");
      chips.className = "reaction-chips";
      row.after(chips);
    }
    chips.innerHTML = "";
    (list || store.getReactions(msgId)).forEach((g) => {
      const c = document.createElement("span");
      c.className = "reaction-chip";
      c.textContent = g;
      chips.appendChild(c);
    });
  }

  function appendBubble(scroll, msg, convTitle, atmosphere, isAi) {
    const row = document.createElement("div");
    row.className = "bubble-row" + (msg.author === "me" ? " me" : "");
    row.dataset.id = msg.id;
    if (msg.author !== "me" && isAi) {
      row.innerHTML = '<span class="avatar avatar--ai" aria-hidden="true"><svg class="icon" style="width:11px;height:11px"><use href="#i-sparkle"/></svg></span>';
    }
    const bubble = document.createElement("div");
    if (msg.kind === "file") {
      bubble.className = "bubble bubble--file";
      bubble.innerHTML = '<svg class="icon" style="width:13px;height:13px"><use href="#i-file"/></svg><span></span><span class="fsize"></span>';
      bubble.children[1].textContent = msg.body;
      bubble.children[2].textContent = (msg.meta && msg.meta.size) || "";
    } else {
      bubble.className = "bubble";
      bubble.textContent = msg.body;
    }
    row.appendChild(bubble);
    bubbleActions(row, msg.id, msg.body, convTitle, atmosphere);
    scroll.appendChild(row);
    renderReactionChips(row, msg.id);
    return row;
  }

  function initMessages() {
    const form = document.getElementById("composer-form");
    if (!form) return;
    const input = form.querySelector("input[name=body]");
    const scroll = document.getElementById("chat-scroll");
    // static deploys rewrite local-*/dm-* pages onto a template — recover the
    // real conversation id and title from the URL
    if (/-template$/.test(form.dataset.conv)) {
      const slug = location.pathname.split("/").filter(Boolean).pop();
      if (slug && !/-template$/.test(slug)) form.dataset.conv = slug;
      const t = new URLSearchParams(location.search).get("t");
      if (t) {
        form.dataset.title = t;
        const titleEl = document.getElementById("chat-title");
        if (titleEl) titleEl.textContent = t;
      }
    }
    const convId = form.dataset.conv;
    const convTitle = form.dataset.title || "conversation";
    const atmosphere = form.dataset.atmosphere || "glass-cube";
    const isAi = form.dataset.ai === "1";
    const isLocal = form.dataset.local === "1";

    scroll.querySelectorAll(".bubble-row[data-id]").forEach((row) => {
      const id = row.dataset.id;
      const body = (row.querySelector(".bubble") || {}).textContent || "";
      bubbleActions(row, id, body.trim(), convTitle, atmosphere);
      renderReactionChips(row, id);
    });

    store.getMessages(convId).forEach((m) => appendBubble(scroll, m, convTitle, atmosphere, isAi));

    input.value = store.getDraft(convId);
    input.addEventListener("input", () => store.setDraft(convId, input.value));

    function aiHistory() {
      return [...scroll.querySelectorAll(".bubble-row")].map((row) => ({
        role: row.classList.contains("me") ? "me" : "ai",
        text: (row.querySelector(".bubble") || {}).textContent || "",
      })).filter((m) => m.text);
    }

    function showTyping() {
      const tip = document.createElement("div");
      tip.className = "typing";
      tip.setAttribute("aria-label", "Phantom AI is thinking");
      tip.innerHTML = "<span></span><span></span><span></span>";
      scroll.appendChild(tip);
      scroll.scrollTop = scroll.scrollHeight;
      return tip;
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = input.value.trim();
      if (!body) return;
      input.value = "";
      store.setDraft(convId, "");

      const history = isAi ? aiHistory() : null;
      const msg = { id: "c" + Date.now().toString(36), author: "me", body, kind: "text", ts: Date.now() / 1000 };
      store.addMessage(convId, msg);
      appendBubble(scroll, msg, convTitle, atmosphere, isAi);
      scroll.scrollTop = scroll.scrollHeight;

      if (isAi) {
        const tip = showTyping();
        try {
          const res = await fetch("/api/assistant", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: body, history }),
          });
          const data = await res.json();
          tip.remove();
          const reply = { id: "a" + Date.now().toString(36), author: "ai", body: data.reply || "…", kind: "text", ts: Date.now() / 1000 };
          store.addMessage(convId, reply);
          appendBubble(scroll, reply, convTitle, atmosphere, true);
        } catch {
          tip.remove();
          appendBubble(scroll, { id: "e" + Date.now().toString(36), author: "ai", body: "I couldn't reach the server. Check that phantom is running.", kind: "text" }, convTitle, atmosphere, true);
        }
        scroll.scrollTop = scroll.scrollHeight;
        return;
      }

      const receipt = document.createElement("div");
      receipt.className = "receipt";
      receipt.textContent = "…";
      scroll.appendChild(receipt);
      scroll.scrollTop = scroll.scrollHeight;
      if (isLocal) { receipt.textContent = "saved on this device"; return; }
      fetch(`/api/conversations/${convId}/messages`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body }),
      }).then((res) => { receipt.textContent = res.ok ? t("delivered") : "saved locally"; })
        .catch(() => { receipt.textContent = "saved locally"; });
    });

    const fileInput = document.getElementById("file-input");
    const attachBtn = document.getElementById("attach-btn");
    if (attachBtn && fileInput) {
      attachBtn.addEventListener("click", () => fileInput.click());
      fileInput.addEventListener("change", () => {
        const f = fileInput.files[0];
        if (!f) return;
        const size = f.size > 1048576 ? (f.size / 1048576).toFixed(1) + " MB" : Math.ceil(f.size / 1024) + " KB";
        const msg = { id: "c" + Date.now().toString(36), author: "me", body: f.name, kind: "file", meta: { size }, ts: Date.now() / 1000 };
        store.addMessage(convId, msg);
        appendBubble(scroll, msg, convTitle, atmosphere, isAi);
        scroll.scrollTop = scroll.scrollHeight;
        fileInput.value = "";
      });
    }

    scroll.scrollTop = scroll.scrollHeight;
  }

  /* ========================================================================
     Moments — pins + filters + empty state
     ======================================================================== */

  function initMoments() {
    const host = document.getElementById("pinned-moments");
    if (!host) return;
    const empty = document.getElementById("moments-empty");
    const pins = store.getPins();
    if (!pins.length) return;
    if (empty) empty.hidden = true;

    const section = document.createElement("section");
    section.className = "tl-group";
    const lbl = document.createElement("span");
    lbl.className = "label";
    lbl.textContent = t("pinned_by_you");
    section.appendChild(lbl);
    pins.forEach((p) => {
      const art = document.createElement("article");
      art.className = "moment";
      art.dataset.kind = p.kind;
      art.innerHTML =
        '<span class="atmosphere" aria-hidden="true"></span>' +
        '<span class="kind"></span><div style="min-width:0"><div class="title"></div><div class="note"></div></div>' +
        '<span class="source"></span>';
      art.querySelector(".atmosphere").classList.add("atm-" + p.atmosphere);
      art.querySelector(".kind").textContent = p.kind;
      art.querySelector(".title").textContent = p.title;
      art.querySelector(".note").textContent = p.note;
      art.querySelector(".source").textContent = p.source;
      section.appendChild(art);
    });
    host.prepend(section);

    document.querySelectorAll("[data-moment-tab]").forEach((tab) => {
      tab.addEventListener("click", () => {
        document.querySelectorAll("[data-moment-tab]").forEach((b) => b.setAttribute("aria-selected", String(b === tab)));
        const f = tab.dataset.momentTab;
        host.querySelectorAll(".moment").forEach((m) => {
          m.style.display = f === "all" || m.dataset.kind === f ? "" : "none";
        });
      });
    });
  }

  /* ========================================================================
     Spaces — join buttons
     ======================================================================== */

  function initSpaces() {
    document.querySelectorAll("[data-join]").forEach((btn) => {
      const id = btn.dataset.join;
      const paint = (joined) => {
        btn.textContent = joined ? "Joined" : "Join";
        btn.classList.toggle("btn--solid", !joined);
        btn.setAttribute("aria-pressed", String(joined));
      };
      paint(store.isJoined(id));
      btn.addEventListener("click", () => paint(store.toggleJoin(id)));
    });
  }

  /* ========================================================================
     Media — filters + lightbox
     ======================================================================== */

  function initMedia() {
    const grid = document.querySelector(".media-grid");
    if (!grid) return;
    document.querySelectorAll(".media-filters button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".media-filters button").forEach((b) => {
          b.setAttribute("aria-pressed", String(b === btn));
          b.setAttribute("aria-selected", String(b === btn));
        });
        const f = btn.dataset.filter;
        grid.querySelectorAll(".media-tile").forEach((tile) => {
          tile.style.display = f === "all" || tile.dataset.kind === f ? "" : "none";
        });
      });
    });

    const lb = document.getElementById("lightbox");
    if (!lb) return;
    const img = lb.querySelector("img");
    const cap = lb.querySelector(".lb-cap .t");
    grid.querySelectorAll(".media-tile").forEach((tile) => {
      tile.addEventListener("click", () => {
        img.src = tile.querySelector("img").src;
        img.alt = tile.dataset.title;
        cap.textContent = tile.dataset.title;
        lb.classList.add("open");
        lb.querySelector(".lb-close").focus();
      });
    });
    function close() { lb.classList.remove("open"); }
    lb.addEventListener("click", (e) => { if (e.target === lb) close(); });
    lb.querySelector(".lb-close").addEventListener("click", close);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  }

  /* ========================================================================
     Onboarding
     ======================================================================== */

  function initOnboarding() {
    const wrap = document.getElementById("onboarding");
    if (!wrap) return;
    const steps = [...wrap.querySelectorAll("[data-step]")];
    const dots = [...wrap.querySelectorAll(".ob-dot")];
    let i = 0;
    let chosenTheme = store.getPref("theme", "moon-horizon");

    function show(n) {
      i = Math.max(0, Math.min(n, steps.length - 1));
      steps.forEach((s, j) => { s.hidden = j !== i; if (j === i) { s.classList.remove("in"); requestAnimationFrame(() => s.classList.add("in")); } });
      dots.forEach((d, j) => d.setAttribute("aria-current", String(j === i)));
      const first = steps[i].querySelector("input, button");
      if (first) first.focus();
    }

    wrap.querySelectorAll("[data-next]").forEach((b) => b.addEventListener("click", () => {
      if (i === 0) {
        const name = wrap.querySelector("#ob-name").value.trim();
        if (!name) { wrap.querySelector("#ob-name").focus(); return; }
      }
      show(i + 1);
    }));
    wrap.querySelectorAll("[data-back]").forEach((b) => b.addEventListener("click", () => show(i - 1)));

    wrap.querySelectorAll("[data-ob-theme]").forEach((tile) => {
      tile.addEventListener("click", () => {
        chosenTheme = tile.dataset.obTheme;
        wrap.querySelectorAll("[data-ob-theme]").forEach((x) => x.setAttribute("aria-pressed", String(x === tile)));
        document.querySelector(".landing > .atmosphere").className = "atmosphere atm-" + chosenTheme;
      });
    });

    wrap.querySelectorAll("[data-ob-lang]").forEach((b) => b.addEventListener("click", () => {
      applyLanguage(b.dataset.obLang, true);
      wrap.querySelectorAll("[data-ob-lang]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    }));

    const ghostSwitch = wrap.querySelector("#ob-ghost");
    if (ghostSwitch) ghostSwitch.addEventListener("click", () => {
      const on = ghostSwitch.getAttribute("aria-checked") !== "true";
      ghostSwitch.setAttribute("aria-checked", String(on));
    });

    wrap.querySelector("#ob-finish").addEventListener("click", () => {
      const name = wrap.querySelector("#ob-name").value.trim() || "you";
      const handle = "@" + (wrap.querySelector("#ob-handle").value.trim().replace(/^@/, "") || name.toLowerCase().replace(/\s+/g, ""));
      store.setProfile({ name, handle });
      store.setPref("theme", chosenTheme);
      if (ghostSwitch && ghostSwitch.getAttribute("aria-checked") === "true") applyGhost(true, true);
      wrap.classList.add("ob-done");
      setTimeout(() => { window.location.href = "/app"; }, 600);
    });

    show(0);
  }

  /* ========================================================================
     Motion — reveals, parallax, card tilt
     ======================================================================== */

  function initMotion() {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const revealed = document.querySelectorAll(".reveal");
    if (revealed.length) {
      if (reduce) revealed.forEach((el) => el.classList.add("in"));
      else {
        const io = new IntersectionObserver((entries) => {
          entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
        }, { threshold: 0.12 });
        revealed.forEach((el) => io.observe(el));
      }
    }
    if (!reduce && document.body.classList.contains("landing")) {
      let ticking = false;
      window.addEventListener("scroll", () => {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(() => {
          document.documentElement.style.setProperty("--plx", String(window.scrollY * 0.08));
          ticking = false;
        });
      }, { passive: true });
    }
    if (!reduce) {
      document.querySelectorAll(".space-card, .media-tile").forEach((card) => {
        card.addEventListener("mousemove", (e) => {
          const r = card.getBoundingClientRect();
          const x = (e.clientX - r.left) / r.width - 0.5;
          const y = (e.clientY - r.top) / r.height - 0.5;
          card.style.transform = `translateY(-2px) perspective(700px) rotateY(${x * 4}deg) rotateX(${-y * 4}deg)`;
        });
        card.addEventListener("mouseleave", () => { card.style.transform = ""; });
      });
    }
  }

  /* ========================================================================
     Settings tabs
     ======================================================================== */

  function initSettings() {
    const nav = document.querySelector(".settings-nav");
    if (!nav) return;
    const tabs = nav.querySelectorAll("button[data-tab]");
    const panes = document.querySelectorAll("[data-pane]");
    function show(id) {
      tabs.forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === id)));
      panes.forEach((p) => (p.hidden = p.dataset.pane !== id));
    }
    tabs.forEach((b) => b.addEventListener("click", () => { show(b.dataset.tab); history.replaceState(null, "", "#" + b.dataset.tab); }));
    show(location.hash.slice(1) || tabs[0].dataset.tab);
  }

  /* ======================================================================== */

  document.addEventListener("DOMContentLoaded", () => {
    applyLanguage(lang, false);
    applyGhost(ghost, false);
    applyPrefs();
    applyProfile();
    initPrefControls();
    initCommandCenter();
    renderLocalConvos();
    initMessages();
    initMoments();
    initSpaces();
    initMedia();
    initOnboarding();
    initMotion();
    initSettings();

    document.querySelectorAll("[data-ghost-toggle]").forEach((el) =>
      el.addEventListener("click", () => applyGhost(!ghost, true)));
    document.querySelectorAll(".lang-btn[data-lang]").forEach((el) =>
      el.addEventListener("click", () => applyLanguage(el.dataset.lang, true)));
  });

  window.phantom = { applyLanguage, applyGhost, applyTheme, applySkin, store };
})();
