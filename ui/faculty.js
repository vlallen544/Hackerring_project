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
async function loadSources() {
    const sources = await api("/api/sources");
    SOURCES = Object.fromEntries(sources.map(s => [s.id, s]));
    setSide("side-sources", `${sources.length} sources loaded`);
    $("source-list").innerHTML = sources.map(s => {
        const [label, color] = TYPE_STYLE[s.type] || [s.type, "bg-white"];
        return `
            <div class="card p-4 flex flex-wrap justify-between items-center gap-3">
                <div>
                    <p class="font-display text-xl uppercase leading-tight">${esc(s.title)}</p>
                    <p class="text-xs font-bold uppercase text-gray-500">// ${esc(s.file)}</p>
                </div>
                <div class="flex gap-2"><span class="chip ${color}">${esc(label)}</span><span class="chip bg-white">${esc(s.year)}</span></div>
            </div>`;
    }).join("");
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
        const res = await fetch("/api/sources/upload", { method: "POST", body: new FormData(form) });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || "Upload failed");
        form.reset();
        toast(data.message);
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
                        <p class="text-xs">weakest: ${esc(cname(s.weakest_prerequisite))}</p>
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
async function init() {
    await Promise.all([loadSources().catch(err => toast(err.message, "error")), loadConcepts()]);
    await Promise.all([loadConflicts(), loadFreshness(), loadClassRadar()]);
    initViews("sources");
}

function setSide(id, text) {
    if ($(id)) $(id).textContent = text;
}

VIEW_HOOKS.radar = loadClassRadar;

init();
