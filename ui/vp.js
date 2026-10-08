// Shared helpers for the VidyaPath UI: API calls, safe HTML, tabs, loading states and small render helpers.
// The UI is served by FastAPI at /ui, so every API call is same-origin.

async function api(path, { method = "GET", body } = {}) {
    const res = await fetch(path, {
        method,
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
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
    const pct = Math.round(Math.max(0, Math.min(1, value ?? 0)) * 100);
    return `<div class="meter"><span class="${color}" style="width:${pct}%"></span></div>`;
}

const pct = v => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`);

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

// Shows which course is active next to the logo on every page (switch with scripts/switch_course.py)
document.addEventListener("DOMContentLoaded", async () => {
    try {
        const course = await api("/api/course");
        const logo = document.querySelector("nav a[href='index.html']");
        if (logo) logo.insertAdjacentHTML("afterend", `<span class="chip bg-neo-blue ml-2 hidden md:inline-block" title="Active course">${esc(course.title)}</span>`);
    } catch { /* older backend without /api/course */ }
});
