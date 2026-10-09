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
        await post("/api/course/build");
        await loadCourseStats();
        $("build-result").innerHTML = `
            <div class="border-4 border-black bg-neo-yellow p-4 mb-8 flex flex-wrap justify-between items-center gap-3">
                <p class="font-bold uppercase">Done. Next: step 2, check what the agent trusted</p>
                <a href="#conflicts" class="btn inline-block">Review conflicts -></a>
            </div>`;
        await Promise.all([loadConflicts(), loadFreshness(), loadSources()]);
        toast("Course knowledge base updated.");
    });
}

// --------------------------------------------------------------------------- //
// Course stat tiles: each opens the details behind the number
// --------------------------------------------------------------------------- //
let COURSE_DATA = null;  // {graph, claims, rejected, conflicts, freshness} of the active course

async function loadCourseStats() {
    try {
        const [graph, claims, rejected, conflicts, freshness] = await Promise.all([
            api("/api/course/graph"), api("/api/course/claims"), api("/api/course/rejected-claims"),
            api("/api/course/conflicts"), api("/api/course/freshness")]);
        COURSE_DATA = { graph, claims, rejected, conflicts, freshness };
    } catch {
        COURSE_DATA = null;
        $("course-stats-tiles").innerHTML = "";  // course not built yet
        return;
    }
    const d = COURSE_DATA;
    const tile = (kind, n, label, color) => `
        <button class="border-4 border-black ${color} p-4 text-center shadow-brutal-sm hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all group"
                onclick="showDetail('${kind}')" title="Show the ${esc(label)}">
            <p class="font-display text-4xl">${esc(n)}</p>
            <p class="text-xs font-bold uppercase">${esc(label)}</p>
            <p class="text-xs font-bold uppercase mt-1 opacity-60 group-hover:opacity-100"><i class="ph-bold ph-eye"></i> View</p>
        </button>`;
    $("course-stats-tiles").innerHTML = `
        <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8 animate-slam">
            ${tile("concepts", d.graph.nodes.length, "concepts", "bg-white")}
            ${tile("claims", d.claims.length, "claims verified", "bg-neo-green")}
            ${tile("rejected", d.rejected.length, "made-up quotes caught", "bg-neo-red text-white")}
            ${tile("conflicts", d.conflicts.length, "conflicts found", "bg-neo-yellow")}
            ${tile("freshness", `${d.freshness.score ?? "—"}%`, "syllabus fresh", "bg-neo-blue")}
        </div>`;
}

const CLAIM_STATUS_STYLE = {
    trusted: "bg-neo-green", outdated: "bg-neo-pink text-white", superseded: "bg-neo-yellow",
    unreliable: "bg-neo-red text-white", needs_review: "bg-neo-blue",
};

function sourceTitle(id) {
    return (SOURCES[id] || {}).title || id;
}

function claimCard(c, extra = "") {
    return `
        <div class="border-2 border-black p-3 bg-white">
            <div class="flex flex-wrap gap-2 items-center mb-1">
                ${c.status ? `<span class="chip ${CLAIM_STATUS_STYLE[c.status] || "bg-white"}">${esc(c.status.replace("_", " "))}</span>` : ""}
                <span class="chip bg-white">${esc(cname(c.concept_id))}</span>
                <span class="text-xs font-bold uppercase text-gray-500">${esc(sourceTitle(c.source_id))} · p.${esc(c.page)}</span>
            </div>
            <p class="font-bold">${esc(c.statement)}</p>
            <p class="text-sm italic text-gray-600 mt-1">"${esc(c.quote)}"</p>
            ${extra}
        </div>`;
}

function renderClaimList(filter) {
    const claims = COURSE_DATA.claims.filter(c => filter === "all" || c.status === filter);
    const counts = {};
    COURSE_DATA.claims.forEach(c => { counts[c.status] = (counts[c.status] || 0) + 1; });
    $("detail-body").innerHTML = `
        <div class="flex flex-wrap gap-2 mb-4">
            ${["all", ...Object.keys(counts)].map(k => `
                <button class="chip !px-3 !py-1 ${filter === k ? "bg-neo-yellow shadow-brutal-sm" : "bg-white"}"
                        onclick="renderClaimList('${k}')">${esc(k.replace("_", " "))} (${k === "all" ? COURSE_DATA.claims.length : counts[k]})</button>`).join("")}
        </div>
        <div class="space-y-3">${claims.map(c => claimCard(c)).join("") || emptyState("No claims in this group")}</div>`;
}

function showDetail(kind) {
    if (!COURSE_DATA) return;
    const d = COURSE_DATA;
    const open = (kicker, title, body) => {
        $("detail-kicker").textContent = kicker;
        $("detail-title").textContent = title;
        $("detail-body").innerHTML = body;
        $("detail").classList.remove("hidden");
    };
    if (kind === "concepts") {
        const needs = {};
        d.graph.edges.forEach(e => { (needs[e.target] = needs[e.target] || []).push(e.source); });
        const perConcept = {};
        d.claims.forEach(c => { perConcept[c.concept_id] = (perConcept[c.concept_id] || 0) + 1; });
        const byId = Object.fromEntries(d.graph.nodes.map(n => [n.id, n]));
        open("// In learning order", `${d.graph.nodes.length} concepts`, `<ol class="space-y-3">${d.graph.learning_order.map((id, i) => `
            <li class="border-2 border-black p-3 bg-white flex gap-3">
                <span class="step-num">${i + 1}</span>
                <div class="flex-1">
                    <p class="font-display text-lg uppercase leading-tight">${esc(byId[id] ? byId[id].label : id)}</p>
                    <p class="text-sm">${esc(byId[id] ? byId[id].description : "")}</p>
                    <p class="text-xs font-bold uppercase text-gray-500 mt-1">
                        ${needs[id] ? `Needs: ${needs[id].map(n => esc(cname(n))).join(", ")}` : "Foundational: no prerequisites"}
                        · ${perConcept[id] || 0} claims</p>
                </div>
            </li>`).join("")}</ol>`);
    } else if (kind === "claims") {
        open("// Every claim has a quote checked against its source page", `${d.claims.length} claims verified`, "");
        renderClaimList("all");
    } else if (kind === "rejected") {
        open("// Quotes the model wrote that do not exist in the sources", `${d.rejected.length} made-up quotes caught`,
            d.rejected.length ? `<div class="space-y-3">${d.rejected.map(c => claimCard(c,
                `<p class="text-xs font-bold uppercase text-neo-red mt-2"><i class="ph-bold ph-x-circle"></i> Rejected: ${esc(c.reject_reason || "quote not found")}</p>`)).join("")}</div>`
            : emptyState("Nothing caught in this build: every quote was found in its source"));
    } else if (kind === "conflicts") {
        open("// Where sources disagree, and what was trusted", `${d.conflicts.length} conflicts found`, `
            <div class="space-y-3 mb-6">${d.conflicts.map(c => {
                const [label, color] = DECISION_STYLE[c.decision] || [c.decision, "bg-white"];
                const winner = c.winner_side !== undefined && c.winner_side !== null ? c.sides[c.winner_side] : null;
                return `<div class="border-2 border-black p-3 bg-white">
                    <div class="flex flex-wrap justify-between gap-2 mb-1"><b class="uppercase">${esc(c.topic)}</b>
                        <span class="flex gap-2"><span class="chip bg-white">${esc(c.type)}</span><span class="chip ${color}">${esc(label)}</span></span></div>
                    <p class="text-sm">${esc(c.summary)}</p>
                    ${winner ? `<p class="text-sm mt-1"><b>Trusted:</b> ${esc(winner.label)} (${winner.score.trust.toFixed(2)})</p>` : ""}
                </div>`; }).join("")}</div>
            <a href="#conflicts" class="btn inline-block" onclick="closeDetail()">Open the conflicts page -></a>`);
    } else if (kind === "freshness") {
        const coverage = { covered: "bg-neo-green", partial: "bg-neo-yellow", outdated: "bg-neo-pink text-white", missing: "bg-neo-red text-white" };
        open("// How well your notes cover what employers ask for", `${d.freshness.score ?? "—"}% aligned with industry`, `
            <div class="space-y-3 mb-6">${d.freshness.skills.map(s => `
                <div class="border-2 border-black p-3 bg-white">
                    <div class="flex flex-wrap justify-between gap-2"><b class="uppercase">${esc(s.skill)}</b>
                        <span class="chip ${coverage[s.faculty_coverage] || "bg-white"}">${esc(s.faculty_coverage)}</span></div>
                    <p class="text-sm mt-1">${esc(s.note)}</p>
                </div>`).join("")}</div>
            <a href="#freshness" class="btn inline-block" onclick="closeDetail()">Open the freshness page -></a>`);
    }
}

function closeDetail() {
    $("detail").classList.add("hidden");
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
        <section class="card p-6 animate-slam" id="card-${esc(c.id)}" data-speak>
            <div class="flex flex-wrap justify-between items-start gap-3 mb-2">
                <div>
                    <p class="text-xs font-bold uppercase text-gray-500 no-read">// ${esc(c.id)} · ${esc(cname(c.concept_id))} · ${esc(c.type)}</p>
                    <h2 class="font-display text-2xl uppercase leading-tight">${esc(c.topic)}</h2>
                </div>
                <div class="flex flex-wrap gap-2">${readAloudButton()}<span class="chip ${color}">${esc(label)}</span>
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

// --------------------------------------------------------------------------- //
// Class-Ready Kit
// --------------------------------------------------------------------------- //
let KIT = null;
let KIT_TAB = "outline";
let KIT_LEVEL = "all";
let KIT_ANSWERS = false;
const LEVEL_STYLE = { easy: "bg-neo-green", medium: "bg-neo-yellow", hard: "bg-neo-red text-white" };

async function loadKitPage() {
    if (COURSE_GRAPH) {
        const current = $("kit-concept").value;
        $("kit-concept").innerHTML = COURSE_GRAPH.learning_order.map(id => `<option value="${esc(id)}">${esc(cname(id))}</option>`).join("");
        if (current) $("kit-concept").value = current;
    }
    try {
        const kits = await api("/api/faculty/kits");
        setSide("side-kit", kits.length ? `${kits.length} kit${kits.length > 1 ? "s" : ""} made` : "Outline, handout, quiz, assignment");
        $("kit-recent").innerHTML = kits.length ? `
            <p class="text-xs font-bold uppercase text-gray-500 mb-2">// Recent kits</p>
            <div class="flex flex-wrap gap-2">${kits.map(k => `
                <button class="chip bg-white hover:bg-neo-yellow !py-1" onclick="openKit(${k.id})">${esc(cname(k.concept_id))} · ${k.class_minutes} min · ${esc(k.created_at.slice(0, 10))}</button>`).join("")}</div>` : "";
    } catch (err) {
        toast(err.message, "error");
    }
}

async function generateKit(event) {
    event.preventDefault();
    const concept = $("kit-concept").value;
    $("kit-body").innerHTML = `<div class="card p-8 text-center font-bold uppercase animate-pulse">
        <i class="ph-bold ph-sparkle text-4xl"></i><p class="mt-2">Building your ${esc(cname(concept))} class pack...</p>
        <p class="text-xs normal-case font-normal mt-1">About 20-60 seconds.</p></div>`;
    await busy($("btn-kit"), "Building...", async () => {
        KIT = await post("/api/faculty/kit", { concept_id: concept, class_minutes: Number($("kit-minutes").value) });
        KIT_TAB = "outline"; KIT_LEVEL = "all"; KIT_ANSWERS = false;
        renderKit();
        loadKitPage();
    });
    if (!KIT || KIT.concept_id !== concept) $("kit-body").innerHTML = emptyState("The kit could not be built. Try again.");
}

async function openKit(id) {
    try {
        KIT = await api(`/api/faculty/kits/${id}`);
        KIT_TAB = "outline"; KIT_LEVEL = "all"; KIT_ANSWERS = false;
        renderKit();
    } catch (err) {
        toast(err.message, "error");
    }
}

function kitSourceChips(item) {
    return item.origin === "material"
        ? item.sources.map(s => `<span class="chip bg-white mr-1" title="${esc(s.quote)}">${esc(s.source)} · p.${esc(s.page)}</span>`).join("")
        : '<span class="chip bg-neo-blue">AI-added</span>';
}

// Each tab renders twice: on screen (with source chips) and for printing (clean, no buttons)
function kitSection(tab, forPrint = false) {
    const k = KIT;
    if (tab === "outline") {
        return `<ol class="space-y-3">${k.outline.map((p, i) => `
            <li class="flex gap-3 border-2 border-black p-3 bg-white">
                <span class="step-num">${i + 1}</span>
                <div class="flex-1"><p class="font-bold uppercase">${esc(p.point)}</p><p class="text-sm">${esc(p.details)}</p></div>
                <span class="chip bg-neo-yellow h-fit">${esc(p.minutes)} min</span>
            </li>`).join("")}</ol>
            <p class="font-bold mt-3">Total: ${esc(k.outline_minutes)} of ${esc(k.class_minutes)} minutes</p>`;
    }
    if (tab === "handout") {
        return `<h3 class="font-display text-2xl uppercase mb-3">${esc(k.handout_title)}</h3>
            <div class="space-y-3">${k.handout.map(h => `
                ${h.heading ? `<h4 class="font-bold uppercase mt-4">${esc(h.heading)}</h4>` : ""}
                <div class="${forPrint ? "" : `border-l-8 ${h.origin === "material" ? "border-neo-green" : "border-neo-blue"} pl-3`}">
                    <p>${esc(h.text)}</p>
                    ${forPrint ? (h.origin === "material" ? `<p class="src">Source: ${h.sources.map(s => `${esc(s.source)}, p.${esc(s.page)}`).join("; ")}</p>` : "")
                               : `<div class="mt-1">${kitSourceChips(h)}</div>`}
                </div>`).join("")}</div>
            ${k.common_mistakes.length ? `<h4 class="font-bold uppercase mt-6 mb-2">Common mistakes</h4>
                <ul class="space-y-2">${k.common_mistakes.map(m => `<li class="border-2 border-black p-2 ${forPrint ? "" : "bg-neo-red/10"}">
                    <b>Mistake:</b> ${esc(m.mistake)}<br><b>Correct:</b> ${esc(m.correction)}
                    ${m.from_class_data && !forPrint ? '<span class="chip bg-neo-pink text-white ml-1">From your class</span>' : ""}</li>`).join("")}</ul>` : ""}`;
    }
    if (tab === "quiz") {
        const qs = k.quiz.filter(q => KIT_LEVEL === "all" || q.difficulty === KIT_LEVEL);
        return `<ol class="space-y-4">${qs.map((q, i) => `
            <li class="border-2 border-black p-3 bg-white">
                <div class="flex flex-wrap gap-2 mb-1">
                    <span class="chip ${forPrint ? "bg-white" : LEVEL_STYLE[q.difficulty]}">${esc(q.difficulty)}</span>
                    ${q.targets_misconception && !forPrint ? '<span class="chip bg-neo-pink text-white">Checks a class misconception</span>' : ""}
                </div>
                <p class="font-bold whitespace-pre-wrap">${i + 1}. ${esc(q.question)}</p>
                ${q.options.length ? `<ol class="list-[upper-alpha] pl-6 mt-1">${q.options.map(o => `<li>${esc(o)}</li>`).join("")}</ol>`
                                   : (forPrint && !KIT_ANSWERS ? '<div class="answer-space"></div>' : "")}
                ${KIT_ANSWERS ? `<p class="mt-2 border-t-2 border-dashed border-black pt-2 text-sm"><b>Answer:</b> ${esc(q.answer)}<br>
                    <span class="text-gray-600">${esc(q.explanation)}</span></p>` : ""}
            </li>`).join("") || "<li>No questions at this level.</li>"}</ol>`;
    }
    if (tab === "assignment") {
        return k.assignment.map((a, i) => `
            <div class="border-2 border-black p-4 bg-white mb-4">
                <h3 class="font-display text-xl uppercase">${i + 1}. ${esc(a.title)}</h3>
                ${a.industry_link && !forPrint ? `<span class="chip bg-neo-blue mt-1">Industry: ${esc(a.industry_link)}</span>` : ""}
                <p class="mt-2 whitespace-pre-wrap">${esc(a.task)}</p>
                <p class="mt-2"><b>Submit:</b> ${esc(a.deliverable)}</p>
                <p class="mt-2 font-bold">Graded on:</p><ul class="list-disc pl-6">${a.rubric.map(r => `<li>${esc(r)}</li>`).join("")}</ul>
                ${KIT_ANSWERS ? `<p class="mt-2 border-t-2 border-dashed border-black pt-2 text-sm whitespace-pre-wrap"><b>Solution outline (teacher):</b> ${esc(a.solution_outline)}</p>` : ""}
            </div>`).join("");
    }
    return "";
}

function renderKit() {
    const k = KIT, ci = k.class_insight;
    const tabs = [["outline", "Outline", "ph-list-numbers"], ["handout", "Handout", "ph-file-text"],
                  ["quiz", `Quiz (${k.quiz.length})`, "ph-question"], ["assignment", "Assignment", "ph-code"]];
    const insight = ci.students_assessed ? `
        <div class="border-4 border-black bg-neo-pink text-white p-3 mb-4 font-bold">
            <i class="ph-bold ph-users-three"></i> Your class on this topic: ${ci.students_assessed} assessed ·
            ${ci.students_weak} weak · ${ci.students_with_misconceptions} with a misconception · average mastery ${pct(ci.average_mastery)}.
            ${ci.students_with_misconceptions ? "The kit adds a common-mistakes section and quiz questions for it." : ""}
        </div>` : `<div class="border-4 border-dashed border-black p-3 mb-4 text-sm font-bold">No students assessed on this topic yet,
            so the kit uses general common mistakes.</div>`;
    const controls = KIT_TAB === "quiz" ? `
        <div class="flex flex-wrap items-center gap-2 mb-4">
            <span class="text-xs font-bold uppercase">Version:</span>
            ${["all", "easy", "medium", "hard"].map(l => `<button class="chip !px-3 !py-1 ${KIT_LEVEL === l ? "bg-neo-yellow shadow-brutal-sm" : "bg-white"}"
                onclick="KIT_LEVEL='${l}'; renderKit()">${l} (${l === "all" ? k.quiz.length : k.quiz.filter(q => q.difficulty === l).length})</button>`).join("")}
        </div>` : "";
    const answersToggle = KIT_TAB === "quiz" || KIT_TAB === "assignment" ? `
        <label class="chip bg-white !py-1 cursor-pointer"><input type="checkbox" ${KIT_ANSWERS ? "checked" : ""}
            onchange="KIT_ANSWERS=this.checked; renderKit()"> ${KIT_TAB === "quiz" ? "Show answers" : "Show solution outline"}</label>` : "";
    $("kit-body").innerHTML = `
        <section class="card p-6 animate-slam">
            <div class="flex flex-wrap justify-between items-start gap-3 mb-4">
                <div>
                    <p class="text-xs font-bold uppercase text-gray-500">// ${esc(k.course)} · ${esc(k.concept_name)} · ${esc(k.class_minutes)}-minute class · kit #${esc(k.id)}</p>
                    <h2 class="font-display text-3xl uppercase leading-tight">${esc(k.title)}</h2>
                    <p class="text-xs font-bold uppercase mt-1">Handout: ${esc(k.material_share_percent)}% from your own material · outdated claims left out</p>
                </div>
            </div>
            ${insight}
            ${k.warnings.length ? `<div class="border-2 border-black bg-neo-yellow p-2 mb-4 text-sm">${k.warnings.map(w => `<p><i class="ph-bold ph-warning"></i> ${esc(w)}</p>`).join("")}</div>` : ""}
            <div class="flex flex-wrap justify-between items-center gap-2 border-b-4 border-black pb-3 mb-4">
                <div class="flex flex-wrap gap-2">${tabs.map(([id, label, icon]) => `
                    <button class="chip !px-3 !py-2 ${KIT_TAB === id ? "bg-neo-black text-white" : "bg-white hover:bg-neo-yellow"}"
                            onclick="KIT_TAB='${id}'; renderKit()"><i class="ph-bold ${icon}"></i> ${label}</button>`).join("")}</div>
                <div class="flex flex-wrap items-center gap-2">${answersToggle}${readAloudButton("kit-section")}
                    <button class="btn" onclick="printKit()"><i class="ph-bold ph-printer"></i> Print</button></div>
            </div>
            ${controls}
            <div id="kit-section">${kitSection(KIT_TAB)}</div>
        </section>`;
}

// Prints the current tab as a clean page (quiz without answers unless "Show answers" is on)
function printKit() {
    const titles = { outline: "Lecture outline", handout: "Handout", quiz: KIT_ANSWERS ? "Quiz - answer key" : "Quiz", assignment: "Assignment" };
    const level = KIT_TAB === "quiz" && KIT_LEVEL !== "all" ? ` (${KIT_LEVEL})` : "";
    const win = window.open("", "_blank");
    if (!win) return toast("Allow pop-ups to print the kit.", "error");
    win.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${esc(KIT.concept_name)} - ${titles[KIT_TAB]}</title>
        <style>
            body { font-family: Georgia, serif; max-width: 760px; margin: 32px auto; padding: 0 16px; color: #111; line-height: 1.5; }
            h1 { font-size: 22px; margin: 0; } .meta { color: #555; font-size: 13px; margin-bottom: 18px; border-bottom: 2px solid #111; padding-bottom: 8px; }
            h3 { font-size: 18px; margin: 14px 0 6px; } h4 { font-size: 15px; margin: 14px 0 4px; text-transform: uppercase; }
            ol, ul { padding-left: 22px; } li { margin-bottom: 10px; } .src { color: #555; font-size: 11px; font-style: italic; margin: 2px 0 8px; }
            .chip { display: inline-block; border: 1px solid #111; padding: 0 6px; font-size: 11px; text-transform: uppercase; margin-right: 4px; }
            .answer-space { border-bottom: 1px solid #999; height: 56px; } .step-num { font-weight: bold; margin-right: 8px; }
            .flex { display: flex; gap: 8px; } .flex-1 { flex: 1; } .space-y-3 > *, .space-y-4 > * { margin-top: 8px; } .text-sm { font-size: 13px; }
            .font-bold { font-weight: bold; } .uppercase { text-transform: uppercase; } .list-\\[upper-alpha\\] { list-style: upper-alpha; }
            .border-2, .border-l-8 { border: none; padding: 0; } .whitespace-pre-wrap { white-space: pre-wrap; }
        </style></head><body>
        <h1>${esc(KIT.concept_name)}: ${titles[KIT_TAB]}${level}</h1>
        <div class="meta">${esc(KIT.course)} · ${esc(KIT.class_minutes)}-minute class</div>
        ${kitSection(KIT_TAB, true)}
        <script>window.onload = () => window.print();<\/script></body></html>`);
    win.document.close();
}

const ME = requireRole("faculty");

async function init() {
    if (!ME) return;
    await Promise.all([loadSources().catch(err => toast(err.message, "error")), loadConcepts()]);
    await Promise.all([loadConflicts(), loadFreshness(), loadClassRadar(), loadStudentAccounts(), loadCourseStats()]);
    initViews("sources");
}

// --------------------------------------------------------------------------- //
// 7. Placement Readiness Forecast
// --------------------------------------------------------------------------- //
const READY_STATUS = {  // status colours always come with an icon and a label
    ready: { label: "Ready", icon: "ph-check-circle", fill: "bg-neo-green", text: "" },
    on_track: { label: "On track", icon: "ph-clock", fill: "bg-neo-yellow", text: "" },
    at_risk: { label: "At risk", icon: "ph-warning-circle", fill: "bg-neo-red", text: "text-white" },
    not_assessed: { label: "No viva yet", icon: "ph-question", fill: "hatch", text: "" },
};
const STATUS_ORDER = ["ready", "on_track", "at_risk", "not_assessed"];

function statusChip(status, extra = "") {
    const s = READY_STATUS[status];
    return `<span class="chip ${s.fill} ${s.text}"><i class="ph-bold ${s.icon}"></i> ${s.label}${extra}</span>`;
}

function readinessBar(role) {
    const parts = STATUS_ORDER.filter(k => role.counts[k]).map(k => {
        const s = READY_STATUS[k], n = role.counts[k], p = role.percent[k];
        return `<div class="${s.fill} ${s.text} border-2 border-black h-10 flex items-center justify-center gap-1 font-bold text-sm min-w-[2.25rem]"
                     style="flex: ${n} 1 0" title="${s.label}: ${n} of ${role.total} students (${p}%)">
                    <i class="ph-bold ${s.icon}"></i>${n}</div>`;
    }).join("");
    const legend = STATUS_ORDER.map(k => statusChip(k, ` · ${role.counts[k]} (${role.percent[k]}%)`)).join("");
    return `<div class="flex gap-[2px] mb-2" role="img" aria-label="${STATUS_ORDER.map(k => `${READY_STATUS[k].label} ${role.counts[k]}`).join(", ")}">${parts}</div>
            <div class="flex flex-wrap gap-2 mb-6">${legend}</div>`;
}

function gapAction(g) {
    if (!g.in_course) return "No topic in this course teaches it: add material for it, or treat it as outside the course.";
    if (g.coverage === "missing") return `Your notes don't cover ${g.concept_name}: upload material on it (Sources), then Build course.`;
    if (g.coverage === "outdated") return `Your notes on ${g.concept_name} are outdated: update them so lessons teach the current practice.`;
    return `Students who are not ready on ${g.concept_name} get it in their path; Class radar shows who needs a refresher.`;
}

function placementRole(role, days) {
    const ready = role.percent.ready;
    const gaps = role.gaps.slice(0, 5).map(g => `
        <li class="border-2 border-black p-3 bg-white">
            <div class="flex flex-wrap justify-between gap-2">
                <b>${esc(g.skill)}</b>
                <span class="flex flex-wrap gap-1">
                    ${g.syllabus_gap ? `<span class="chip bg-neo-pink text-white">Syllabus gap · ${esc(g.in_course ? g.coverage : "not in course")}</span>` : ""}
                    <span class="chip bg-white">${g.students_not_ready} of ${role.total} not ready</span>
                </span>
            </div>
            <p class="text-sm mt-1">${esc(gapAction(g))}</p>
        </li>`).join("");
    const skills = role.skills.filter(s => s.in_course);
    const cell = p => {
        const s = READY_STATUS[p.status];
        const m = p.mastery === null || p.mastery === undefined ? "untested" : pct(p.mastery);
        const when = p.scheduled_for ? ` · ${p.scheduled_for.slice(5)}` : "";
        return `<td class="p-2 border-t-2 border-black"><span class="chip ${s.fill} ${s.text} !normal-case" title="${s.label}">
                    <i class="ph-bold ${s.icon}"></i> ${m}${when}</span></td>`;
    };
    const table = `
        <details class="mt-4">
            <summary class="cursor-pointer font-bold uppercase">Per student (${role.total})</summary>
            <div class="overflow-x-auto mt-3">
                <table class="w-full border-4 border-black bg-white text-sm">
                    <thead class="bg-neo-black text-white"><tr>
                        <th class="text-left p-2">Student</th><th class="text-left p-2">Status</th><th class="text-left p-2">Readiness</th>
                        ${skills.map(s => `<th class="text-left p-2">${esc(s.concept_name)}</th>`).join("")}</tr></thead>
                    <tbody>${role.students.map(st => `<tr>
                        <td class="p-2 border-t-2 border-black font-bold"><a class="underline" href="student.html?id=${encodeURIComponent(st.id)}">${esc(st.name)}</a></td>
                        <td class="p-2 border-t-2 border-black">${statusChip(st.status)}</td>
                        <td class="p-2 border-t-2 border-black font-mono">${st.readiness === null ? "—" : pct(st.readiness)}</td>
                        ${st.skills.map(cell).join("")}</tr>`).join("")}</tbody>
                </table>
            </div>
            <p class="text-xs mt-2">Readiness: average progress towards ${pct(0.75)} mastery on this role's skills. Dates are when a topic is scheduled in the student's path.</p>
        </details>`;
    return `
        <section class="card p-6 mb-8 animate-slam">
            <p class="text-xs font-bold uppercase text-gray-500">// Job role from your job descriptions · ${skills.length} course skill${skills.length === 1 ? "" : "s"}</p>
            <h2 class="font-display text-2xl md:text-3xl uppercase leading-tight mb-3">${esc(role.title)}</h2>
            <p class="mb-4"><span class="font-display text-5xl">${ready}%</span>
                <span class="font-bold uppercase">ready</span> · ${role.total} students · drive in ${days} day${days === 1 ? "" : "s"}</p>
            ${readinessBar(role)}
            ${gaps ? `<h3 class="font-display text-xl uppercase mb-2">What holds them back</h3><ul class="space-y-2">${gaps}</ul>` : ""}
            ${table}
        </section>`;
}

let PLACEMENT = null;

function renderPlacement(f) {
    PLACEMENT = f;
    $("drive-date").value = f.drive_date;
    $("drive-note").innerHTML = f.drive_date_set
        ? `Drive on <b>${esc(f.drive_date)}</b> (${f.days_to_drive} days away).`
        : `No drive date set yet: assuming the end of the course plan, <b>${esc(f.drive_date)}</b>. Set the real date for an accurate forecast.`;
    const legend = `<p class="text-sm mb-6 max-w-3xl"><b>Ready:</b> ${pct(f.ready_threshold)}+ mastery on every skill the role needs ·
        <b>On track:</b> the remaining topics are scheduled in the student's path before the drive ·
        <b>At risk:</b> a needed topic is weak or untested and not scheduled before the drive ·
        <b>No viva yet:</b> no evidence either way.</p>`;
    $("placement-body").innerHTML = f.roles.length ? legend + f.roles.map(r => placementRole(r, f.days_to_drive)).join("")
        : emptyState("No job descriptions in this course yet. Upload one on Sources (type: job description) and press Build course.");
    const best = f.roles[0];
    setSide("side-placement", best ? `${best.percent.ready}% ready · ${best.title}` : "Who is ready for which job role");
}

async function loadPlacement() {
    try {
        renderPlacement(await api("/api/placement/forecast"));
    } catch (err) {
        $("placement-body").innerHTML = emptyState(err.message);
    }
}

async function saveDriveDate(event) {
    event.preventDefault();
    await busy($("btn-drive"), "Updating...", async () => {
        renderPlacement(await api("/api/placement/drive-date", { method: "PUT", body: { drive_date: $("drive-date").value } }));
        toast("Forecast updated for the new drive date.");
    });
}

function setSide(id, text) {
    if ($(id)) $(id).textContent = text;
}

VIEW_HOOKS.radar = loadClassRadar;
VIEW_HOOKS.students = loadStudentAccounts;
VIEW_HOOKS.kit = loadKitPage;
VIEW_HOOKS.placement = loadPlacement;

init();
