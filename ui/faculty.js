// Faculty screens: sources + build, source conflicts with override, syllabus freshness, class gap radar.
const TYPE_STYLE = {
    faculty_notes: ["Faculty notes", "bg-neo-yellow"],
    textbook: ["Textbook", "bg-neo-green"],
    web_link: ["Web article", "bg-neo-blue"],
    job_description: ["Job description", "bg-neo-pink text-white"],
};
let SOURCES = {};

// --------------------------------------------------------------------------- //
// Sources + build
// --------------------------------------------------------------------------- //
const STATUS_STYLE = {
    in_build: ["In knowledge base", "bg-neo-green"],
    new: ["New: press Build course", "bg-neo-yellow"],
    changed: ["Changed since last build", "bg-neo-pink text-white"],
    missing_file: ["File missing", "bg-neo-red text-white"],
};
const FORMAT_ICON = { pdf: "ph-file-pdf", pptx: "ph-presentation", md: "ph-file-text", txt: "ph-file-text" };

function sourceCard(s) {
    const [label, color] = TYPE_STYLE[s.type] || [s.type, "bg-white"];
    const [statusLabel, statusColor] = STATUS_STYLE[s.status] || [s.status, "bg-white"];
    const pages = s.pages_total
        ? (s.page_range ? `${s.pages_used} of ${s.pages_total} pages (${esc(s.page_range)})` : `${s.pages_total} page${s.pages_total > 1 ? "s" : ""}`)
        : "";
    const facts = [
        (s.format || "").toUpperCase(), pages,
        s.words !== undefined ? `${Number(s.words).toLocaleString()} words` : "",
        s.size_bytes ? (s.size_bytes < 1024 * 1024 ? `${Math.ceil(s.size_bytes / 1024)} KB` : `${(s.size_bytes / 1024 / 1024).toFixed(1)} MB`) : "",
        s.uploaded_at ? `uploaded ${s.uploaded_at.slice(0, 10)}` : "",
    ].filter(Boolean).join(" · ");
    const usage = s.status === "in_build"
        ? `${s.claims} claims (${s.trusted_claims} trusted)${s.conflicts ? ` · in ${s.conflicts} conflict${s.conflicts > 1 ? "s" : ""}` : ""}`
        : "";
    return `
        <div class="card p-4">
            <div class="flex flex-wrap justify-between items-start gap-3">
                <div class="flex gap-3 items-start">
                    <i class="ph-bold ${FORMAT_ICON[s.format] || "ph-file"} text-3xl"></i>
                    <div>
                        <p class="font-display text-xl uppercase leading-tight">${esc(s.title)}</p>
                        <p class="text-xs font-bold uppercase text-gray-500">// ${esc(facts || s.file)}</p>
                    </div>
                </div>
                <div class="flex flex-wrap gap-2"><span class="chip ${color}">${esc(label)}</span><span class="chip bg-white">${esc(s.year)}</span></div>
            </div>
            <div class="flex flex-wrap justify-between items-center gap-2 mt-3 pt-3 border-t-2 border-black border-dashed">
                <div class="flex flex-wrap items-center gap-2 text-xs font-bold">
                    <span class="chip ${statusColor}">${esc(statusLabel)}</span><span>${esc(usage)}</span>
                </div>
                <div class="flex gap-2">
                    ${s.status !== "missing_file" ? `<button class="chip bg-white hover:bg-neo-yellow" onclick="previewSource('${esc(s.id)}')"><i class="ph-bold ph-eye"></i> Preview text</button>` : ""}
                    <button class="chip bg-white hover:bg-neo-red hover:text-white" onclick="deleteSource(this, '${esc(s.id)}')"><i class="ph-bold ph-trash"></i> Delete</button>
                </div>
            </div>
        </div>`;
}

async function loadSources() {
    const sources = await api("/api/sources");
    SOURCES = Object.fromEntries(sources.map(s => [s.id, s]));
    const pending = sources.filter(s => s.status === "new" || s.status === "changed");
    setSide("side-sources", pending.length ? `${sources.length} sources · ${pending.length} not built yet` : `${sources.length} sources, all built`);
    const banner = pending.length ? `
        <div class="border-4 border-black bg-neo-yellow p-4 flex flex-wrap justify-between items-center gap-3">
            <p class="font-bold uppercase">${pending.length} source${pending.length > 1 ? "s are" : " is"} not in the knowledge base yet</p>
            <button class="btn" onclick="buildCourse(this)"><i class="ph-bold ph-hammer"></i> Build course now</button>
        </div>` : "";
    $("source-list").innerHTML = banner + sources.map(sourceCard).join("");
}

function suggestTitle(input) {
    const form = input.form;
    if (input.files[0] && !form.title.value) {
        form.title.value = input.files[0].name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ");
    }
}

async function previewSource(id) {
    try {
        const data = await api(`/api/sources/${encodeURIComponent(id)}/pages`);
        $("preview-title").textContent = data.title;
        const show = i => {
            const p = data.pages[i];
            $("preview-text").textContent = p.text || "(no text on this page: image or scan)";
            document.querySelectorAll("#preview-pages button").forEach((b, j) => {
                b.classList.toggle("bg-neo-yellow", j === i);
                b.classList.toggle("bg-white", j !== i);
            });
        };
        $("preview-pages").innerHTML = data.pages.map(p =>
            `<button class="chip bg-white" title="${p.words} words">p.${p.page}</button>`).join("");
        document.querySelectorAll("#preview-pages button").forEach((b, i) => { b.onclick = () => show(i); });
        if (data.pages.length) show(0);
        $("preview").classList.remove("hidden");
    } catch (err) {
        toast(err.message, "error");
    }
}

function closePreview() {
    $("preview").classList.add("hidden");
}

async function deleteSource(button, id) {
    const src = SOURCES[id];
    if (!confirm(`Delete "${src ? src.title : id}"? Press Build course afterwards to update the knowledge base.`)) return;
    await busy(button, "Deleting...", async () => {
        const r = await api(`/api/sources/${encodeURIComponent(id)}`, { method: "DELETE" });
        toast(r.message);
        await loadSources();
    });
}

async function buildCourse(button) {
    await busy(button, "Agents at work...", async () => {
        const r = await post("/api/course/build");
        const stat = (n, label, color) => `
            <div class="border-4 border-black ${color} p-4 text-center shadow-brutal-sm">
                <p class="font-display text-4xl">${esc(n)}</p><p class="text-xs font-bold uppercase">${esc(label)}</p>
            </div>`;
        $("build-result").innerHTML = `
            <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8 animate-slam">
                ${stat(r.concepts, "concepts", "bg-white")}
                ${stat(r.claims_verified, "claims verified", "bg-neo-green")}
                ${stat(r.claims_rejected, "made-up quotes caught", "bg-neo-red text-white")}
                ${stat(r.conflicts, "conflicts found", "bg-neo-yellow")}
                ${stat(`${r.freshness_score ?? "—"}%`, "syllabus fresh", "bg-neo-blue")}
            </div>`;
        $("build-result").insertAdjacentHTML("beforeend", `
            <div class="border-4 border-black bg-neo-yellow p-4 mb-8 flex flex-wrap justify-between items-center gap-3">
                <p class="font-bold uppercase">Done. Next: step 2, check what the agent trusted</p>
                <a href="#conflicts" class="btn inline-block">Review conflicts -></a>
            </div>`);
        await Promise.all([loadConflicts(), loadFreshness()]);
        toast("Course knowledge base updated.");
    });
}

async function uploadSource(event) {
    event.preventDefault();
    const form = event.target;
    await busy($("btn-upload"), "Uploading...", async () => {
        $("upload-result").innerHTML = "";
        const res = await fetch("/api/sources/upload", { method: "POST", body: new FormData(form), headers: authHeaders() });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            $("upload-result").innerHTML = `<div class="border-4 border-black bg-neo-red text-white p-3 text-sm font-bold">${esc(data.detail || "Upload failed")}</div>`;
            return;
        }
        form.reset();
        $("upload-result").innerHTML = `
            <div class="border-4 border-black bg-neo-green p-3 text-sm">
                <p class="font-bold">${esc(data.message)}</p>
                ${data.warnings.map(w => `<p class="mt-1"><i class="ph-bold ph-warning"></i> ${esc(w)}</p>`).join("")}
            </div>`;
        await loadSources();
    });
}

async function resetDemo(button) {
    if (!confirm("Clear all student progress (vivas, lessons, paths)? Course knowledge is kept.")) return;
    await busy(button, "Resetting...", async () => {
        await post("/api/demo/reset");
        toast("Student progress cleared.");
    });
}

// --------------------------------------------------------------------------- //
// Conflicts
// --------------------------------------------------------------------------- //
const DECISION_STYLE = {
    resolved: ["Resolved", "bg-neo-green"],
    flagged_unreliable: ["Flagged unreliable", "bg-neo-red text-white"],
    needs_faculty_review: ["Needs your review", "bg-neo-pink text-white"],
    kept: ["Kept", "bg-white"],
};

function renderConflict(c) {
    const [label, color] = DECISION_STYLE[c.decision] || [c.decision, "bg-white"];
    const sides = c.sides.map((s, i) => {
        const win = c.winner_side === i;
        const f = s.score.factors;
        const srcs = s.score.sources.map(id => {
            const src = SOURCES[id] || { title: id, type: "", year: "" };
            const [, sc] = TYPE_STYLE[src.type] || ["", "bg-white"];
            return `<span class="chip ${sc} mr-1 mb-1">${esc(src.title)} ${esc(src.year)}</span>`;
        }).join("");
        const canOverride = c.sides.length > 1 && !win;
        return `
            <div class="border-4 border-black p-4 ${win ? "bg-neo-green/20" : "bg-white"} relative">
                ${win ? '<span class="absolute -top-4 -right-3 chip bg-neo-green rotate-3 shadow-brutal-sm">Trusted</span>' : ""}
                <p class="font-bold mb-2">${esc(s.label)}</p>
                <div class="mb-3">${srcs}</div>
                <div class="flex items-center gap-3 mb-2">
                    <span class="font-display text-3xl">${s.score.trust.toFixed(2)}</span>
                    <div class="flex-1">${meter(s.score.trust, win ? "bg-neo-green" : "bg-neo-black")}</div>
                </div>
                <div class="flex flex-wrap gap-1 text-xs">
                    <span class="chip bg-white">recency ${esc(f.recency)}</span>
                    <span class="chip bg-white">authority ${esc(f.authority)}</span>
                    <span class="chip bg-white">agreement ${esc(f.agreement)}</span>
                    <span class="chip bg-white">specific ${esc(f.specificity)}</span>
                    ${s.score.absolute_penalty ? '<span class="chip bg-neo-red text-white">always/never −0.15</span>' : ""}
                </div>
                ${canOverride ? `<button class="btn btn-light mt-3 text-sm" onclick="overrideConflict(this, '${esc(c.id)}', ${i})">Trust this side instead</button>` : ""}
            </div>`;
    }).join("");
    return `
        <section class="card p-6 animate-slam" id="card-${esc(c.id)}">
            <div class="flex flex-wrap justify-between items-start gap-3 mb-2">
                <div>
                    <p class="text-xs font-bold uppercase text-gray-500">// ${esc(c.id)} · ${esc(cname(c.concept_id))} · ${esc(c.type)}</p>
                    <h2 class="font-display text-2xl uppercase leading-tight">${esc(c.topic)}</h2>
                </div>
                <div class="flex gap-2"><span class="chip ${color}">${esc(label)}</span>
                    <span class="chip ${c.decided_by === "faculty" ? "bg-neo-blue" : "bg-white"}">by ${esc(c.decided_by)}</span></div>
            </div>
            <p class="mb-4">${esc(c.summary)}</p>
            <div class="grid grid-cols-1 ${c.sides.length > 1 ? "md:grid-cols-2" : ""} gap-6 mb-4">${sides}</div>
            <div class="border-2 border-black bg-neo-yellow p-3"><b>WHY:</b> ${esc(c.explanation)}</div>
        </section>`;
}

let CONFLICTS = [];
let CONFLICT_FILTER = "all";

function renderConflictList() {
    const groups = {
        all: ["All", () => true],
        needs_faculty_review: ["Needs your review", c => c.decision === "needs_faculty_review"],
        resolved: ["Resolved", c => c.decision === "resolved"],
        flagged_unreliable: ["Flagged unreliable", c => c.decision === "flagged_unreliable"],
    };
    $("conflict-filter").innerHTML = Object.entries(groups).map(([key, [label, test]]) => `
        <button class="chip !px-3 !py-1 ${CONFLICT_FILTER === key ? "bg-neo-yellow shadow-brutal-sm" : "bg-white"}"
                onclick="CONFLICT_FILTER='${key}'; renderConflictList()">${label} (${CONFLICTS.filter(test).length})</button>`).join("");
    const shown = CONFLICTS.filter(groups[CONFLICT_FILTER][1]);
    $("conflict-list").innerHTML = shown.length ? shown.map(renderConflict).join("") : emptyState("Nothing in this group");
}

async function loadConflicts() {
    try {
        CONFLICTS = await api("/api/course/conflicts");
        const review = CONFLICTS.filter(c => c.decision === "needs_faculty_review").length;
        setSide("side-conflicts", review ? `${review} need your review` : `${CONFLICTS.length} found, all decided`);
        renderConflictList();
    } catch (err) {
        $("conflict-list").innerHTML = emptyState(err.message);
    }
}

async function overrideConflict(button, id, side) {
    await busy(button, "Applying...", async () => {
        const updated = await post(`/api/course/conflicts/${encodeURIComponent(id)}/override`, { winning_side: side });
        CONFLICTS = CONFLICTS.map(c => (c.id === id ? updated : c));
        renderConflictList();
        toast("Your decision now overrides the agent.");
    });
}

// --------------------------------------------------------------------------- //
// Freshness
// --------------------------------------------------------------------------- //
async function loadFreshness() {
    try {
        const fr = await api("/api/course/freshness");
        setSide("side-fresh", `${fr.score ?? "—"}% aligned · ${fr.missing.length} missing`);
        const coverage = {
            covered: "bg-neo-green", partial: "bg-neo-yellow", outdated: "bg-neo-pink text-white", missing: "bg-neo-red text-white" };
        $("freshness-body").innerHTML = `
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-slam">
                <section class="card p-6 bg-neo-yellow text-center h-fit">
                    <p class="font-display text-8xl leading-none">${esc(fr.score ?? "—")}<span class="text-4xl">%</span></p>
                    <p class="font-bold uppercase mt-2">aligned with industry</p>
                    <div class="text-left mt-6 space-y-3">
                        ${fr.missing.length ? `<div><span class="chip bg-neo-red text-white">Missing</span><p class="mt-1">${fr.missing.map(esc).join("<br>")}</p></div>` : ""}
                        ${fr.outdated.length ? `<div><span class="chip bg-neo-pink text-white">Outdated</span><p class="mt-1">${fr.outdated.map(esc).join("<br>")}</p></div>` : ""}
                    </div>
                </section>
                <section class="lg:col-span-2 space-y-4">
                    ${fr.skills.map(s => `
                        <div class="card p-4">
                            <div class="flex flex-wrap justify-between items-center gap-2 mb-1">
                                <b class="uppercase">${esc(s.skill)}</b><span class="chip ${coverage[s.faculty_coverage] || "bg-white"}">${esc(s.faculty_coverage)}</span>
                            </div>
                            <p class="text-sm">${esc(s.note)}</p>
                            <p class="text-xs font-bold uppercase text-gray-500 mt-1">// asked for by ${s.demanded_by.map(id => esc((SOURCES[id] || {}).title || id)).join(", ")}</p>
                        </div>`).join("")}
                </section>
            </div>`;
    } catch (err) {
        $("freshness-body").innerHTML = emptyState(err.message);
    }
}

// --------------------------------------------------------------------------- //
// Class radar
// --------------------------------------------------------------------------- //
async function loadClassRadar() {
    try {
        const data = await api("/api/class/gap-radar");
        const atRisk = new Set(data.concepts.flatMap(e => e.students.filter(s => s.band === "high").map(s => s.name)));
        setSide("side-radar", atRisk.size ? `${atRisk.size} student${atRisk.size > 1 ? "s" : ""} at high risk` : "No high risks");
        const concepts = data.concepts.map(e => `
            <section class="card p-5">
                <div class="flex justify-between items-center mb-3 gap-2">
                    <h2 class="font-display text-xl uppercase leading-tight">${esc(e.concept_name)}</h2>
                    <span class="chip ${e.high_risk_count ? "bg-neo-red text-white" : "bg-neo-green"}">${esc(e.high_risk_count)} high risk</span>
                </div>
                ${e.students.map(s => `
                    <div class="mb-3">
                        <div class="flex justify-between text-sm font-bold"><a class="underline" href="student.html?id=${encodeURIComponent(s.student_id)}">${esc(s.name)}</a>
                            <span>${pct(s.risk)} ${bandChip(s.band)}</span></div>
                        ${meter(s.risk, s.band === "high" ? "bg-neo-red" : s.band === "medium" ? "bg-neo-yellow" : "bg-neo-green")}
                        <p class="text-xs">${s.weakest_prerequisite === e.concept_id
                            ? "weak in this topic itself" : `weakest: ${esc(cname(s.weakest_prerequisite))}`}</p>
                    </div>`).join("")}
            </section>`).join("");
        $("class-radar").innerHTML = `
            ${data.not_assessed.length ? `<div class="border-4 border-black bg-white p-4 mb-8 font-bold">
                NOT YET ASSESSED (no viva taken): ${data.not_assessed.map(esc).join(", ")}</div>` : ""}
            ${data.concepts.length ? `<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 animate-slam">${concepts}</div>`
                : emptyState("No risks predicted yet")}`;
    } catch (err) {
        $("class-radar").innerHTML = emptyState(err.message);
    }
}

// --------------------------------------------------------------------------- //
// Start
// --------------------------------------------------------------------------- //
// --------------------------------------------------------------------------- //
// Student accounts (JWT logins created by faculty)
// --------------------------------------------------------------------------- //
async function loadStudentAccounts() {
    try {
        const students = await api("/api/faculty/students");
        const withLogin = students.filter(s => s.login).length;
        setSide("side-students", `${students.length} students · ${withLogin} can log in`);
        $("student-accounts").innerHTML = students.length ? students.map(s => `
            <div class="card p-4 flex flex-wrap justify-between items-center gap-3">
                <div>
                    <p class="font-display text-xl uppercase leading-tight">${esc(s.name)}</p>
                    <p class="text-xs font-bold uppercase text-gray-500">// ID ${esc(s.id)} · ${esc(s.stated_style)} · ${esc(s.pace)} · ${esc(s.target_role)}</p>
                </div>
                <div class="flex flex-wrap items-center gap-2">
                    ${s.login ? `<span class="chip bg-neo-green"><i class="ph-bold ph-key"></i> Login: ${esc(s.login)}</span>`
                              : '<span class="chip bg-white">No login yet</span>'}
                    <button class="chip bg-white hover:bg-neo-yellow" onclick="setStudentPassword(this, '${esc(s.id)}', ${Boolean(s.login)})">
                        ${s.login ? "Reset password" : "Create login"}</button>
                    ${s.login ? `<button class="chip bg-white hover:bg-neo-red hover:text-white" onclick="removeLogin(this, '${esc(s.id)}')">Remove login</button>` : ""}
                    <a class="chip bg-neo-black text-white hover:bg-neo-yellow hover:text-black" href="student.html?id=${encodeURIComponent(s.id)}">Open -></a>
                </div>
            </div>`).join("") : emptyState("No students yet");
    } catch (err) {
        $("student-accounts").innerHTML = emptyState(err.message);
    }
}

async function createStudent(event) {
    event.preventDefault();
    const form = event.target;
    $("student-result").innerHTML = "";
    await busy($("btn-student"), "Creating...", async () => {
        const body = Object.fromEntries(new FormData(form).entries());
        try {
            const r = await api("/api/faculty/students", { method: "POST", body });
            $("student-result").innerHTML = `<div class="border-4 border-black bg-neo-green p-3 text-sm font-bold">
                ${esc(r.message)}<br>Share the ID and password with the student.</div>`;
            form.reset();
            await loadStudentAccounts();
        } catch (err) {
            $("student-result").innerHTML = `<div class="border-4 border-black bg-neo-red text-white p-3 text-sm font-bold">${esc(err.message)}</div>`;
        }
    });
}

async function setStudentPassword(button, id, hasLogin) {
    const password = prompt(`${hasLogin ? "New password" : "Password for the new login"} of '${id}' (6+ characters):`);
    if (!password) return;
    await busy(button, "Saving...", async () => {
        const r = await api(`/api/faculty/students/${encodeURIComponent(id)}/password`, { method: "POST", body: { password } });
        toast(`${r.message}. Share it with the student.`);
        await loadStudentAccounts();
    });
}

async function removeLogin(button, id) {
    if (!confirm(`Remove the login of '${id}'? Their learning data is kept; they just can't log in.`)) return;
    await busy(button, "Removing...", async () => {
        await api(`/api/faculty/students/${encodeURIComponent(id)}/login`, { method: "DELETE" });
        toast("Login removed.");
        await loadStudentAccounts();
    });
}

const ME = requireRole("faculty");

async function init() {
    if (!ME) return;
    await Promise.all([loadSources().catch(err => toast(err.message, "error")), loadConcepts()]);
    await Promise.all([loadConflicts(), loadFreshness(), loadClassRadar(), loadStudentAccounts()]);
    initViews("sources");
}

function setSide(id, text) {
    if ($(id)) $(id).textContent = text;
}

VIEW_HOOKS.radar = loadClassRadar;
VIEW_HOOKS.students = loadStudentAccounts;

init();
