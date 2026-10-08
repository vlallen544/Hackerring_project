// Shared helpers for the VidyaPath UI: API calls, safe HTML, tabs, loading states and small render helpers.
// The UI is served by FastAPI at /ui, so every API call is same-origin.

// --------------------------------------------------------------------------- //
// Login state: the JWT from /api/auth/login is kept in this browser and sent as a Bearer token
// --------------------------------------------------------------------------- //
const AUTH_KEY = "vp-auth";

function getAuth() {
    try { return JSON.parse(localStorage.getItem(AUTH_KEY)); } catch { return null; }
}

function setAuth(auth) {
    try { localStorage.setItem(AUTH_KEY, JSON.stringify(auth)); } catch { /* storage blocked: login lasts this page only */ }
}

function clearAuth() {
    try { localStorage.removeItem(AUTH_KEY); } catch { /* ignore */ }
}

function authHeaders() {
    const auth = getAuth();
    return auth && auth.token ? { Authorization: `Bearer ${auth.token}` } : {};
}

const homeFor = user => (user.role === "faculty" ? "faculty.html" : "student.html");

function goLogin() {
    clearAuth();
    const back = location.pathname.split("/").pop() + location.search + location.hash;
    location.href = `login.html?next=${encodeURIComponent(back)}`;
}

function logout() {
    clearAuth();
    location.href = "login.html";
}

// Call at the top of a page: returns the logged-in user, or redirects (to login, or to the user's own page)
function requireRole(role) {
    const auth = getAuth();
    if (!auth || !auth.token) {
        goLogin();
        return null;
    }
    if (role && auth.user.role !== role) {
        location.href = homeFor(auth.user);
        return null;
    }
    return auth.user;
}

async function api(path, { method = "GET", body } = {}) {
    const res = await fetch(path, {
        method,
        headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...authHeaders() },
        body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401 && !location.pathname.endsWith("login.html")) {
        goLogin();  // missing, expired or revoked login
        throw new Error(data.detail || "Please log in");
    }
    if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
    return data;
}

const post = (path, body = {}) => api(path, { method: "POST", body });

// Model output is untrusted text: always escape it before putting it into HTML
function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const $ = id => document.getElementById(id);

// Tabs are real links (#viva, #path...), so the browser back button moves between them
const VIEW_HOOKS = {};  // view name -> function to run whenever that view is shown

function switchView(name) {
    document.querySelectorAll(".view-section").forEach(v => {
        const show = v.id === `view-${name}`;
        v.classList.toggle("hidden", !show);
        if (show) {
            v.classList.remove("animate-slam");
            void v.offsetWidth;  // restart the animation
            v.classList.add("animate-slam");
        }
    });
    document.querySelectorAll("[data-view]").forEach(b => b.classList.toggle("active", b.dataset.view === name));
    try { sessionStorage.setItem(`vp-view-${location.pathname}`, name); } catch { /* storage may be blocked */ }
    window.scrollTo(0, 0);
    if (VIEW_HOOKS[name]) VIEW_HOOKS[name]();
}

// Navigate to a view (adds a history entry, so Back returns to the previous view)
function go(name) {
    if (location.hash.slice(1) === name) switchView(name);
    else location.hash = name;
}

// Opens the view named in the URL hash, else the last view used, else the fallback
function initViews(fallback) {
    window.addEventListener("hashchange", () => {
        const name = location.hash.slice(1);
        if ($(`view-${name}`)) switchView(name);
    });
    let name = location.hash.slice(1);
    if (!$(`view-${name}`)) {
        try { name = sessionStorage.getItem(`vp-view-${location.pathname}`); } catch { name = null; }
    }
    if (!name || !$(`view-${name}`)) name = fallback;
    history.replaceState(null, "", `${location.pathname}${location.search}#${name}`);
    switchView(name);
}

// Disables the button and shows a working label while an agent call runs (some take 10-20 seconds)
async function busy(button, label, fn) {
    const original = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `<i class="ph-bold ph-spinner animate-spin"></i> ${esc(label)}`;
    try {
        return await fn();
    } catch (err) {
        toast(err.message, "error");
    } finally {
        button.disabled = false;
        button.innerHTML = original;
    }
}

function toast(message, kind = "info") {
    const el = document.createElement("div");
    const color = kind === "error" ? "bg-neo-red text-white" : "bg-neo-yellow text-black";
    el.className = `fixed bottom-6 right-6 z-50 ${color} border-4 border-black shadow-brutal-sm px-4 py-3 font-bold max-w-sm animate-slam`;
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 4500);
}

function meter(value, color = "bg-neo-black") {
    const pct = toPercent(Math.max(0, Math.min(1, value ?? 0)));
    return `<div class="meter"><span class="${color}" style="width:${pct}%"></span></div>`;
}

// Percent rounded half up (0.685 -> 69), the same rule the backend uses in its reason text
const toPercent = v => Math.floor(v * 100 + 0.5);
const pct = v => (v === null || v === undefined ? "—" : `${toPercent(v)}%`);

function bandChip(band) {
    const color = { high: "bg-neo-red text-white", medium: "bg-neo-yellow", low: "bg-neo-green",
        strong: "bg-neo-green", developing: "bg-neo-yellow", weak: "bg-neo-red text-white" }[band] || "bg-white";
    return `<span class="chip ${color}">${esc(band)}</span>`;
}

function masteryBand(score) {
    return score >= 0.75 ? "strong" : score >= 0.45 ? "developing" : "weak";
}

// Concept ids -> readable names, loaded once from the course graph
const CONCEPTS = {};
let COURSE_GRAPH = null;

async function loadConcepts() {
    try {
        COURSE_GRAPH = await api("/api/course/graph");
        COURSE_GRAPH.nodes.forEach(n => { CONCEPTS[n.id] = n.label; });
    } catch (err) {
        toast("Course not built yet. Open the faculty page and run BUILD COURSE.", "error");
    }
    return COURSE_GRAPH;
}

const cname = id => CONCEPTS[id] || id;

function emptyState(text) {
    return `<div class="border-4 border-dashed border-black p-8 text-center font-bold uppercase bg-white/70">${esc(text)}</div>`;
}

// Course switcher next to the logo on every page: every view then shows the chosen course
async function switchCourse(courseId) {
    const overlay = document.createElement("div");
    overlay.className = "fixed inset-0 z-50 bg-black/60 flex items-center justify-center";
    overlay.innerHTML = `<div class="card p-8 text-center font-bold uppercase animate-slam">
        <i class="ph-bold ph-spinner animate-spin text-4xl"></i>
        <p class="mt-3">Switching course...</p>
        <p class="text-xs normal-case font-normal mt-1">A course that was never built takes about a minute.</p></div>`;
    document.body.appendChild(overlay);
    try {
        await post("/api/course/switch", { course: courseId });
        location.reload();  // every page re-reads the active course's data
    } catch (err) {
        overlay.remove();
        toast(err.message, "error");
    }
}

function courseSelect(course, extraClass = "") {
    return `<select class="field !w-auto !py-1 !text-xs font-bold uppercase bg-neo-blue ${extraClass}" aria-label="Course"
                    title="Switch course" onchange="switchCourse(this.value)">
        ${Object.entries(course.available).map(([id, title]) =>
            `<option value="${esc(id)}" ${id === course.id ? "selected" : ""}>${esc(title)}</option>`).join("")}
    </select>`;
}

let ACTIVE_COURSE = null;

document.addEventListener("DOMContentLoaded", async () => {
    const auth = getAuth();
    const user = auth && auth.user;
    const nav = document.querySelector("nav > div");
    if (user && nav && !location.pathname.endsWith("login.html")) {
        // Students only see their own pages: no switch to the faculty view
        if (user.role !== "faculty") document.querySelectorAll(".role-switch").forEach(el => el.remove());
        // Put the user menu next to the existing right-hand items (wrapped, so their own styles don't apply to it)
        const right = nav.lastElementChild;
        const box = document.createElement("div");
        box.className = "flex items-center gap-3 flex-wrap justify-end";
        right.replaceWith(box);
        box.appendChild(right);
        box.insertAdjacentHTML("beforeend", `
            <a href="profile.html" class="chip bg-white hover:bg-neo-yellow !py-1 flex items-center gap-1" title="My profile">
                <i class="ph-bold ph-user-circle text-lg"></i><span class="hidden sm:inline">${esc(user.name || user.username)}</span></a>
            <button onclick="logout()" class="chip bg-neo-red text-white !py-1 hover:bg-black" title="Log out">
                <i class="ph-bold ph-sign-out"></i><span class="hidden sm:inline"> Logout</span></button>`);
    }
    try {
        ACTIVE_COURSE = await api("/api/course");
        const logo = document.querySelector("nav a[href='index.html']");
        if (logo && !location.pathname.endsWith("login.html")) {
            // Only faculty can switch the course; everyone else sees which course is active
            logo.insertAdjacentHTML("afterend", user && user.role === "faculty"
                ? `<label class="hidden md:flex items-center gap-2 ml-3"><i class="ph-bold ph-books text-xl"></i>${courseSelect(ACTIVE_COURSE)}</label>`
                : `<span class="chip bg-neo-blue ml-3 hidden md:inline-block">${esc(ACTIVE_COURSE.title)}</span>`);
        }
        if ($("course-list") && user && user.role === "faculty") renderCourseList(ACTIVE_COURSE);  // home page
    } catch { /* older backend without /api/course */ }
});

function renderCourseList(course) {
    $("course-list").innerHTML = Object.entries(course.available).map(([id, title]) => {
        const active = id === course.id;
        return `
            <div class="border-4 border-black p-4 ${active ? "bg-neo-yellow shadow-brutal-sm" : "bg-white"} flex flex-wrap justify-between items-center gap-3">
                <div>
                    <p class="font-display text-xl uppercase leading-tight">${esc(title)}</p>
                    <p class="text-xs font-bold uppercase">${active ? "Active course" : "Available"}</p>
                </div>
                ${active ? '<span class="chip bg-neo-black text-white">Active</span>'
                    : `<button class="btn" onclick="switchCourse('${esc(id)}')">Switch -></button>`}
            </div>`;
    }).join("");
}
