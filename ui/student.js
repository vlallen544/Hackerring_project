// Student screens: home, viva, learning path and lessons. All decisions come from the backend agents.
const params = new URLSearchParams(location.search);
let STUDENT_ID = params.get("id");
let STUDENT = null;
let VIVA_SESSION = null;
let CURRENT_LESSON = null;
let LESSON_PATH_ITEM = null;
let VIVA_PROGRESS = null;  // {current, total} while a viva is running  // path item a lesson was opened from, so it can be marked done afterwards

// Diagrams keep their natural size (wide ones scroll sideways) so labels stay readable
if (window.mermaid) mermaid.initialize({
    startOnLoad: false, theme: "neutral", securityLevel: "strict",
    flowchart: { useMaxWidth: false }, sequence: { useMaxWidth: false }, state: { useMaxWidth: false },
});

const sid = () => encodeURIComponent(STUDENT_ID);

// --------------------------------------------------------------------------- //
// Voice: read questions aloud and dictate answers (Web Speech API, Chrome/Edge)
// --------------------------------------------------------------------------- //
function speak(text) {
    if (!("speechSynthesis" in window)) return toast("Speech is not supported in this browser.", "error");
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-IN";  // Indian English voice
    speechSynthesis.speak(u);
}

function dictate(targetId, button) {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) return toast("Voice input needs Chrome or Edge.", "error");
    const rec = new Recognition();
    rec.lang = "en-IN";
    rec.interimResults = false;
    button.disabled = true;
    button.innerHTML = '<i class="ph-bold ph-record animate-pulse text-neo-red"></i> Listening...';
    rec.onresult = e => {
        const field = $(targetId);
        field.value = (field.value + " " + e.results[0][0].transcript).trim();
    };
    rec.onerror = e => toast(`Voice input failed: ${e.error}`, "error");
    rec.onend = () => {
        button.disabled = false;
        button.innerHTML = '<i class="ph-bold ph-microphone"></i> Speak';
    };
    rec.start();
}

function confidencePicker(containerId, name) {
    $(containerId).innerHTML = [1, 2, 3, 4, 5].map(n => `
        <label class="cursor-pointer">
            <input type="radio" name="${name}" value="${n}" class="peer hidden" ${n === 3 ? "checked" : ""}>
            <span class="block border-2 border-black px-3 py-2 font-bold peer-checked:bg-neo-yellow peer-checked:shadow-brutal-sm">${n}</span>
        </label>`).join("");
}

const chosen = name => Number(document.querySelector(`input[name="${name}"]:checked`)?.value || 3);

// --------------------------------------------------------------------------- //
// Shortcut used everywhere: open the Lessons step with a topic already chosen
// --------------------------------------------------------------------------- //
async function openLesson(conceptId, { format = "", kind = "lesson", pathItemId = null } = {}) {
    go("lessons");
    $("lesson-concept").value = conceptId;
    const fmt = kind === "lesson" ? "" : format;  // plain lessons: the agent decides (learned style may have changed)
    $("lesson-format").value = fmt;
    const override = { concept_id: conceptId, format: fmt };
    if (kind === "challenge") Object.assign(override, { level: "challenge", reason: "On the challenge track: all prerequisites are strong." });
    if (kind === "refresher") override.reason = "Refresher added by the Gap Predictor before an upcoming topic.";
    LESSON_PATH_ITEM = pathItemId;
    await requestLesson(document.querySelector("#view-lessons .btn"), override);
}

// --------------------------------------------------------------------------- //
// Home
// --------------------------------------------------------------------------- //
// A plain lesson on a topic the student already masters is optional, so "next" skips it
function isStrong(conceptId) {
    const m = (STUDENT?.mastery || []).find(x => x.concept_id === conceptId);
    return Boolean(m && m.score >= 0.75);
}

function isOptional(item) {
    return item.kind === "lesson" && isStrong(item.concept_id);
}

function nextPathItem(path = STUDENT.path || []) {
    return path.find(p => p.status !== "done" && !isOptional(p)) || path.find(p => p.status !== "done");
}

function renderNextStep() {
    const path = STUDENT.path || [];
    let title, text, button;
    if (!STUDENT.mastery.length) {
        title = "Start with the viva";
        text = "A 5-minute spoken interview, so the agents know where you stand.";
        button = `<a href="#viva" class="btn inline-block"><i class="ph-bold ph-microphone"></i> Take the viva</a>`;
    } else if (!path.length) {
        title = "Plan your path";
        text = "Your viva is done. Let the Gap Predictor build your plan and fix weak spots in advance.";
        button = `<button class="btn" onclick="go('path'); runPrediction(this)"><i class="ph-bold ph-crosshair"></i> Plan my path</button>`;
    } else {
        const next = nextPathItem();
        if (!next) {
            title = "Path complete!";
            text = "You have finished every topic. Retake the viva to measure your progress.";
            button = `<a href="#viva" class="btn inline-block">Retake viva -></a>`;
        } else {
            const label = { refresher: "Refresher", challenge: "Challenge" }[next.kind] || "Lesson";
            title = `Up next: ${cname(next.concept_id)}`;
            text = next.kind === "lesson" ? `${label} · ${next.format} · planned for ${next.scheduled_for}` : next.reason;
            button = `<button class="btn" onclick="openLesson('${esc(next.concept_id)}', {format: '${esc(next.format)}', kind: '${esc(next.kind)}', pathItemId: ${next.id}})">
                <i class="ph-bold ph-play"></i> Start ${esc(label.toLowerCase())}</button>
                <a href="#path" class="btn btn-light inline-block ml-2">See full path</a>`;
        }
    }
    $("next-step").innerHTML = `
        <section class="card p-6 bg-neo-yellow flex flex-wrap justify-between items-center gap-4">
            <div>
                <p class="text-xs font-bold uppercase">// What to do next</p>
                <h2 class="font-display text-3xl uppercase leading-tight">${esc(title)}</h2>
                <p class="mt-1 max-w-2xl">${esc(text)}</p>
            </div>
            <div class="flex flex-wrap items-center">${button}</div>
        </section>`;
}

function renderSidebarStatus() {
    const path = STUDENT.path || [];
    const done = path.filter(p => p.status === "done").length;
    const set = (id, text) => { if ($(id)) $(id).textContent = text; };
    set("side-viva", VIVA_PROGRESS ? `In progress · ${VIVA_PROGRESS.current} of ${VIVA_PROGRESS.total}`
        : STUDENT.mastery.length ? `Done · ${STUDENT.mastery.length} topics measured` : "Not taken yet: start here");
    set("side-path", path.length ? `${done} of ${path.length} done` : "Plan it after the viva");
    const next = path.length ? nextPathItem() : null;
    set("side-lessons", next ? `Next: ${cname(next.concept_id)}` : "Learn and practise each topic");
}

async function loadStudent() {
    STUDENT = await api(`/api/students/${sid()}`);
    $("student-name").innerHTML = `${esc(STUDENT.name)}<span class="text-neo-pink">_</span>`;
    const style = STUDENT.learned_style
        ? `<span class="chip bg-neo-pink text-white">Learned style: ${esc(STUDENT.learned_style)}</span>`
        : `<span class="chip bg-white">Stated style: ${esc(STUDENT.stated_style)}</span>`;
    $("student-meta").innerHTML = `
        ${style}
        <span class="chip bg-white">Pace: ${esc(STUDENT.pace)}</span>
        <span class="chip bg-neo-blue">${esc(STUDENT.target_role)}</span>`;

    $("mastery").innerHTML = STUDENT.mastery.length ? STUDENT.mastery
        .sort((a, b) => a.score - b.score)
        .map(m => {
            const band = masteryBand(m.score);
            const gap = (m.confidence ?? 0) - m.score;
            const calib = gap > 0.25 ? "overconfident" : gap < -0.25 ? "underconfident" : "calibrated";
            return `
            <button class="block w-full text-left mb-3 p-2 border-2 border-transparent hover:border-black hover:bg-slate-50 group"
                    onclick="openLesson('${esc(m.concept_id)}')">
                <div class="flex justify-between items-center mb-1 gap-2 flex-wrap">
                    <span class="font-bold uppercase">${esc(cname(m.concept_id))}
                        <span class="text-xs normal-case opacity-0 group-hover:opacity-100">-> study this</span></span>
                    <span class="flex gap-2">${bandChip(band)}<span class="chip bg-white">${esc(calib)}</span></span>
                </div>
                ${meter(m.score, band === "weak" ? "bg-neo-red" : band === "strong" ? "bg-neo-green" : "bg-neo-yellow")}
                <p class="text-xs font-bold mt-1">Mastery ${pct(m.score)} · felt ${pct(m.confidence)} sure · last practised ${esc(m.last_practiced || "—")}</p>
            </button>`;
        }).join("")
        : emptyState("No mastery yet. Take the viva first.");

    $("risk-events").innerHTML = STUDENT.risk_events.length ? STUDENT.risk_events.slice(0, 8).map(e => `
        <div class="border-2 border-black p-3 ${e.action.startsWith("refresher") ? "bg-neo-yellow" : "bg-neo-green"}">
            <p class="text-xs font-bold uppercase">${e.action.startsWith("refresher:")
                ? `Refresher on ${esc(cname(e.action.split(":")[1]))} · before ${esc(cname(e.concept_id))}`
                : `Challenge track · ${esc(cname(e.concept_id))}`}</p>
            <p class="text-sm">${esc(e.reason)}</p>
        </div>`).join("")
        : emptyState("No changes yet");

    renderNextStep();
    renderSidebarStatus();
}

// --------------------------------------------------------------------------- //
// 1. Viva
// --------------------------------------------------------------------------- //
function showQuestion(q) {
    $("viva-start").classList.add("hidden");
    $("viva-box").classList.remove("hidden");
    $("viva-progress").textContent = `Topic ${q.progress.concept} of ${q.progress.of}`;
    VIVA_PROGRESS = { current: q.progress.concept, total: q.progress.of };
    if (STUDENT) renderSidebarStatus();
    $("viva-dots").innerHTML = Array.from({ length: q.progress.of }, (_, i) => `
        <span class="h-3 flex-1 border-2 border-black ${i < q.progress.concept - 1 ? "bg-neo-black" : i === q.progress.concept - 1 ? "bg-neo-yellow" : "bg-white"}"></span>`).join("");
    $("viva-followup").classList.toggle("hidden", !q.is_follow_up);
    $("viva-concept").textContent = `// ${q.concept_name}`;
    $("viva-question").textContent = q.question;
    $("viva-answer").value = "";
    confidencePicker("viva-confidence", "viva-conf");
    $("viva-answer").focus();
}

async function startViva(button) {
    await busy(button, "Preparing questions...", async () => {
        const q = await post(`/api/viva/${sid()}/start`);
        VIVA_SESSION = q.session_id;
        $("viva-feedback").innerHTML = "";
        $("viva-summary").classList.add("hidden");
        showQuestion(q);
    });
}

function verdictCard(ev, decision) {
    const color = { correct: "bg-neo-green", partial: "bg-neo-yellow", vague: "bg-neo-blue", incorrect: "bg-neo-red text-white" }[ev.verdict];
    return `
        <div class="card p-4 animate-slam">
            <div class="flex justify-between items-center mb-2">
                <span class="chip ${color}">${esc(ev.verdict)}</span>
                <span class="font-display text-xl">${pct(ev.score)}</span>
            </div>
            <p class="mb-2">${esc(ev.feedback)}</p>
            ${ev.misconception ? `<p class="text-sm border-2 border-black bg-neo-red/10 p-2 mb-2"><b>MISCONCEPTION:</b> ${esc(ev.misconception)}</p>` : ""}
            ${ev.missing_prerequisite ? `<p class="text-sm"><b>WEAK PREREQUISITE:</b> ${esc(cname(ev.missing_prerequisite))}</p>` : ""}
            <p class="text-xs font-bold uppercase mt-2 text-gray-500">// Agent: ${esc(decision)}</p>
        </div>`;
}

async function answerViva(button) {
    const answer = $("viva-answer").value.trim();
    if (!answer) return toast("Type or speak an answer first.", "error");
    await busy(button, "Evaluating...", async () => {
        const r = await post(`/api/viva/session/${VIVA_SESSION}/answer`, { answer, confidence: chosen("viva-conf") });
        $("viva-feedback").insertAdjacentHTML("afterbegin", verdictCard(r.evaluation, r.agent_decision));
        if (r.done) {
            $("viva-box").classList.add("hidden");
            VIVA_PROGRESS = null;
            renderVivaSummary(r.summary);
            loadStudent();
        } else {
            showQuestion(r.next);
        }
    });
}

function renderVivaSummary(s) {
    const box = $("viva-summary");
    box.classList.remove("hidden");
    box.innerHTML = `
        <section class="card p-6 animate-slam">
            <h2 class="font-display text-3xl uppercase mb-4">Your result</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                ${s.results.map(r => `
                    <div class="border-4 border-black p-4">
                        <div class="flex justify-between mb-2"><b class="uppercase">${esc(r.concept_name)}</b>${bandChip(r.band)}</div>
                        ${meter(r.mastery, r.band === "weak" ? "bg-neo-red" : r.band === "strong" ? "bg-neo-green" : "bg-neo-yellow")}
                        <p class="text-xs font-bold mt-1">Mastery ${pct(r.mastery)} · confidence ${pct(r.confidence)} ·
                            <span class="${r.calibration === "calibrated" ? "" : "text-neo-pink"}">${esc(r.calibration)}</span></p>
                    </div>`).join("")}
            </div>
            ${s.misconceptions.length ? `<h3 class="font-display text-xl uppercase mb-2">Misconceptions found</h3>
                <ul class="list-disc pl-6 mb-4">${s.misconceptions.map(m => `<li><b>${esc(cname(m.concept_id))}:</b> ${esc(m.misconception)}</li>`).join("")}</ul>` : ""}
            ${s.missing_prerequisites.length ? `<p class="mb-4"><b>Weak prerequisites:</b> ${s.missing_prerequisites.map(m => esc(cname(m.prerequisite))).join(", ")}</p>` : ""}
            <div class="border-4 border-black bg-neo-yellow p-4 flex flex-wrap items-center justify-between gap-3">
                <p class="font-bold uppercase">Next: step 2, plan your path</p>
                <div class="flex flex-wrap gap-3">
                    <button class="btn" onclick="go('path'); runPrediction(this)"><i class="ph-bold ph-crosshair"></i> Plan my path</button>
                    <button class="btn btn-light" onclick="$('viva-summary').classList.add('hidden'); $('viva-start').classList.remove('hidden')">Retake viva</button>
                </div>
            </div>
        </section>`;
}

// --------------------------------------------------------------------------- //
// 2. Path + gap radar
// --------------------------------------------------------------------------- //
function renderRadar(radar) {
    $("radar-list").innerHTML = radar.length ? radar.map(r => {
        const f = r.factors;
        const fix = r.cause === "own" ? r.concept_id : r.weakest_prerequisite;
        return `
            <div class="border-4 border-black p-4 ${r.band === "high" ? "bg-neo-red/10" : "bg-white"}">
                <div class="flex justify-between items-center mb-2 gap-2">
                    <b class="uppercase">${esc(r.concept_name)}</b>
                    <span class="flex items-center gap-2">${bandChip(r.band)}<span class="font-display text-xl">${pct(r.risk)}</span></span>
                </div>
                ${meter(r.risk, r.band === "high" ? "bg-neo-red" : r.band === "medium" ? "bg-neo-yellow" : "bg-neo-green")}
                <p class="text-sm mt-2">${esc(r.reason_chain)}</p>
                <details class="mt-2 text-xs">
                    <summary class="cursor-pointer font-bold uppercase">Risk factors</summary>
                    <div class="flex flex-wrap gap-1 mt-2">
                        <span class="chip bg-white">${r.cause === "own" ? "own weakness" : "prerequisite weakness"} ${pct(f.prerequisite_weakness)}</span>
                        <span class="chip bg-white">forgetting ${pct(f.forgetting)}</span>
                        <span class="chip bg-white">behind schedule ${pct(f.pace_lag)}</span>
                        <span class="chip ${f.misconception ? "bg-neo-pink text-white" : "bg-white"}">misconception ${f.misconception ? "yes" : "no"}</span>
                    </div>
                </details>
                ${r.band !== "low" ? `<button class="btn btn-light text-xs mt-3" onclick="openLesson('${esc(fix)}')">
                    <i class="ph-bold ph-book-open"></i> Study ${esc(cname(fix))}</button>` : ""}
            </div>`;
    }).join("") : emptyState(STUDENT && STUDENT.mastery.length ? "No risks ahead" : "Take the viva first, so the agent has evidence");
}

function renderPath(path) {
    if (!path.length) {
        $("path-list").innerHTML = emptyState("No path yet. Press CHECK FOR GAPS.");
        return;
    }
    const firstOpen = nextPathItem(path);
    $("path-list").innerHTML = path.map(p => {
        const kind = { refresher: ["+ Refresher", "bg-neo-yellow"], challenge: ["* Challenge", "bg-neo-pink text-white"] }[p.kind]
            || ["Lesson", "bg-white"];
        const done = p.status === "done";
        const isNext = firstOpen && p.id === firstOpen.id;
        return `
            <div class="border-2 border-black p-3 flex flex-wrap sm:flex-nowrap items-start gap-3 ${done ? "opacity-50 bg-slate-100" : isNext ? "bg-neo-yellow/40 border-4" : "bg-white"}">
                <div class="text-xs font-bold w-20 shrink-0">${esc(p.scheduled_for)}${isNext ? '<br><span class="chip bg-neo-black text-white mt-1">Next</span>' : ""}</div>
                <div class="flex-1 min-w-[150px]">
                    <div class="flex flex-wrap gap-2 items-center"><span class="chip ${kind[1]}">${kind[0]}</span>
                        <b class="uppercase">${esc(cname(p.concept_id))}</b><span class="text-xs">(${esc(p.format)})</span>
                        ${!done && isOptional(p) ? '<span class="chip bg-neo-green">Already strong · optional</span>' : ""}</div>
                    ${p.kind !== "lesson" ? `<p class="text-xs mt-1">${esc(p.reason)}</p>` : ""}
                </div>
                <div class="flex gap-2 shrink-0">
                    ${done ? '<span class="chip bg-neo-green"><i class="ph-bold ph-check"></i> Done</span>' : `
                        <button class="chip bg-neo-black text-white hover:bg-neo-yellow hover:text-black"
                                onclick="openLesson('${esc(p.concept_id)}', {format: '${esc(p.format)}', kind: '${esc(p.kind)}', pathItemId: ${p.id}})">Start</button>
                        <button class="chip bg-white hover:bg-neo-green" onclick="completeItem(${p.id})">Done</button>`}
                </div>
            </div>`;
    }).join("");
}

async function loadPath() {
    if (!STUDENT_ID) return;
    try {
        const [radar, path] = await Promise.all([api(`/api/students/${sid()}/gap-radar`), api(`/api/students/${sid()}/path`)]);
        renderRadar(radar);
        renderPath(path);
    } catch (err) {
        toast(err.message, "error");
    }
}

async function runPrediction(button) {
    await busy(button, "Checking for gaps...", async () => {
        const r = await post(`/api/students/${sid()}/predict`);
        $("path-message").innerHTML = r.actions.length ? `
            <div class="card p-6 mb-8 bg-neo-yellow animate-slam">
                <h2 class="font-display text-2xl uppercase mb-2">${r.actions.length} change${r.actions.length > 1 ? "s" : ""} made to your path</h2>
                ${r.message ? `<p class="text-lg mb-3">${esc(r.message.student_message)}</p>` : ""}
                <details class="text-sm"><summary class="cursor-pointer font-bold uppercase">Exact reasons</summary>
                    <ul class="list-disc pl-6 mt-2">${r.actions.map(a => `<li>${esc(a.reason)}</li>`).join("")}</ul></details>
            </div>`
            : `<div class="mb-8 border-4 border-black bg-neo-green p-4 font-bold uppercase animate-slam">No new changes needed right now</div>`;
        renderRadar(r.gap_radar);
        renderPath(r.path);
        loadStudent();
    });
}

async function completeItem(id) {
    try {
        renderPath(await post(`/api/students/${sid()}/path/${id}/complete`));
        loadStudent();
        toast("Marked as done.");
    } catch (err) {
        toast(err.message, "error");
    }
}

// --------------------------------------------------------------------------- //
// 3. Lessons
// --------------------------------------------------------------------------- //
async function requestLesson(button, override = {}) {
    const body = { concept_id: override.concept_id || $("lesson-concept").value };
    const fromDropdown = override.format === undefined;  // TEACH ME pressed: use what the student picked
    const fmt = fromDropdown ? $("lesson-format").value : override.format;
    if (fmt) body.format = fmt;
    if (override.level) body.level = override.level;
    if (override.reason) body.reason = override.reason;
    else if (fromDropdown && fmt) body.reason = "Chosen by the student";
    if (!override.concept_id) LESSON_PATH_ITEM = null;  // chosen by hand, not from the path
    CURRENT_LESSON = null;
    $("lesson-body").innerHTML = `<div class="card p-8 text-center font-bold uppercase animate-pulse">
        <i class="ph-bold ph-sparkle text-4xl"></i><p class="mt-2">The Tutor is writing your ${esc(cname(body.concept_id))} lesson...</p>
        <p class="text-xs normal-case font-normal mt-1">A full lesson with diagrams and code takes about 30-90 seconds.</p></div>`;
    await busy(button, "Writing your lesson...", async () => {
        CURRENT_LESSON = await post(`/api/tutor/${sid()}/lesson`, body);
        await renderLesson(CURRENT_LESSON);
    });
    if (!CURRENT_LESSON) $("lesson-body").innerHTML = emptyState("The lesson could not be created. Try again.");
}

const LESSON_SECTIONS = [
    ["explain", "Explanation"], ["diagrams", "Diagrams"], ["walkthrough", "Step by step"], ["code", "Code"],
    ["complexity", "Complexity"], ["mistakes", "Mistakes"], ["points", "Key points"], ["practice", "Practice"],
];

function sectionTitle(id, title, icon) {
    return `<h3 id="ls-${id}" class="font-display text-2xl uppercase mb-4 mt-10 flex items-center gap-2 scroll-mt-24">
        <i class="ph-bold ${icon}"></i>${esc(title)}</h3>`;
}

function copyCode(button, index) {
    const code = CURRENT_LESSON.code_examples[index].code;
    navigator.clipboard.writeText(code).then(() => {
        button.textContent = "Copied!";
        setTimeout(() => { button.innerHTML = '<i class="ph-bold ph-copy"></i> Copy'; }, 1500);
    }).catch(() => toast("Copy is blocked in this browser.", "error"));
}

async function renderLesson(L) {
    const a = L.adaptation;
    const diagrams = L.diagrams || (L.diagram_mermaid ? [{ title: "", mermaid: L.diagram_mermaid, caption: "" }] : []);
    const code = L.code_examples || [];
    const steps = L.walkthrough || [];
    const complexity = L.complexity || [];
    const mistakes = L.common_mistakes || [];
    const points = L.key_points || [];
    const present = {
        explain: L.segments.length, diagrams: diagrams.length, walkthrough: steps.length, code: code.length,
        complexity: complexity.length, mistakes: mistakes.length || L.misconception_fix, points: points.length, practice: L.practice.length,
    };

    const segments = L.segments.map(seg => {
        const isMaterial = seg.origin === "material";
        const cite = isMaterial ? seg.sources.map(s => `
            <span class="chip bg-white mr-1 mt-1" title="${esc(s.quote)}">${esc(s.source)} · p.${esc(s.page)}</span>`).join("") : "";
        return `
            ${seg.heading ? `<h4 class="font-display text-lg uppercase mt-6">${esc(seg.heading)}</h4>` : ""}
            <div class="border-l-8 ${isMaterial ? "border-neo-green" : "border-neo-blue"} pl-4 py-1">
                <span class="chip ${isMaterial ? "bg-neo-green" : "bg-neo-blue"} mb-1">${isMaterial ? "From faculty material" : "AI-added"}</span>
                <p class="leading-relaxed">${esc(seg.text)}</p>
                <div>${cite}</div>
            </div>`;
    }).join("");

    const diagramHtml = diagrams.map((d, i) => `
        <figure class="border-4 border-black bg-white mb-6">
            ${d.title ? `<figcaption class="bg-neo-black text-white px-3 py-1 font-bold uppercase text-sm">${esc(d.title)}</figcaption>` : ""}
            <div id="diagram-${i}" class="diagram p-4"></div>
            ${d.caption ? `<p class="border-t-2 border-black px-3 py-2 text-sm">${esc(d.caption)}</p>` : ""}
        </figure>`).join("");

    const stepHtml = steps.length ? `
        <p class="font-bold mb-3">${esc(L.walkthrough_title || "")}</p>
        <ol class="space-y-3">${steps.map((st, i) => `
            <li class="flex gap-3">
                <span class="step-num shrink-0">${i + 1}</span>
                <div class="flex-1">
                    <p>${esc(st.step)}</p>
                    ${st.state ? `<pre class="mt-1 bg-slate-100 border-2 border-black px-3 py-1 text-sm whitespace-pre-wrap">${esc(st.state)}</pre>` : ""}
                </div>
            </li>`).join("")}</ol>` : "";

    const codeHtml = code.map((c, i) => `
        <div class="border-4 border-black mb-6">
            <div class="flex justify-between items-center gap-2 bg-neo-black text-white px-3 py-2">
                <span class="font-bold uppercase text-sm">${esc(c.title)}</span>
                <span class="flex items-center gap-2">
                    <span class="chip bg-neo-yellow text-black">${esc(c.language)}</span>
                    <button class="chip bg-white text-black hover:bg-neo-blue" onclick="copyCode(this, ${i})"><i class="ph-bold ph-copy"></i> Copy</button>
                </span>
            </div>
            <pre class="m-0"><code class="language-${esc(c.language)} text-sm">${esc(c.code)}</code></pre>
            ${c.output ? `<div class="border-t-2 border-black bg-slate-100 px-3 py-2 text-sm"><b>OUTPUT</b>
                <pre class="whitespace-pre-wrap mt-1">${esc(c.output)}</pre></div>` : ""}
            <p class="border-t-2 border-black px-3 py-2 text-sm bg-white">${esc(c.explanation)}</p>
        </div>`).join("");

    const complexityHtml = complexity.length ? `
        <table class="w-full border-4 border-black bg-white text-sm">
            <thead class="bg-neo-black text-white"><tr><th class="text-left p-2">Operation</th><th class="text-left p-2">Time</th><th class="text-left p-2">Extra space</th></tr></thead>
            <tbody>${complexity.map(r => `<tr class="border-t-2 border-black"><td class="p-2 font-bold">${esc(r.operation)}</td>
                <td class="p-2 font-mono">${esc(r.time)}</td><td class="p-2 font-mono">${esc(r.space)}</td></tr>`).join("")}</tbody>
        </table>` : "";

    const finish = LESSON_PATH_ITEM
        ? `<button class="btn" onclick="finishPathLesson(this)"><i class="ph-bold ph-check"></i> Mark done and go to my path</button>`
        : `<a href="#path" class="btn inline-block">Back to my path -></a>`;

    $("lesson-body").innerHTML = `
        <div class="grid grid-cols-1 xl:grid-cols-4 gap-8 animate-slam">
            <aside class="card p-6 bg-neo-yellow h-fit xl:sticky xl:top-24">
                <h3 class="font-display text-xl uppercase mb-3">Why this lesson looks like this</h3>
                <p class="text-sm mb-2"><b>LEVEL: ${esc(a.level)}</b><br>${esc(a.level_reason)}</p>
                <p class="text-sm mb-2"><b>FORMAT: ${esc(a.format)}</b><br>${esc(a.format_reason)}</p>
                ${a.targets_misconceptions.length ? `<p class="text-sm mb-2"><b>FIXES:</b> ${a.targets_misconceptions.map(esc).join("; ")}</p>` : ""}
                ${a.recapped_prerequisites.length ? `<p class="text-sm mb-2"><b>RECAPS:</b> ${a.recapped_prerequisites.map(c => esc(cname(c))).join(", ")}</p>` : ""}
                <p class="text-sm mt-4 mb-1"><b>FACULTY MATERIAL: ${esc(L.material_share_percent)}%</b> of the explanation</p>
                ${meter(L.material_share_percent / 100, "bg-neo-green")}
                <p class="text-xs mt-2">Diagrams, walkthrough and code are AI-written illustrations checked against the course's trusted facts.</p>
            </aside>
            <article class="card p-6 xl:col-span-3">
                <p class="text-xs font-bold uppercase text-gray-500">// ${esc(cname(L.concept_id))} · lesson #${esc(L.lesson_id)}</p>
                <h2 class="font-display text-3xl md:text-4xl uppercase leading-tight mb-3">${esc(L.title)}</h2>
                ${L.overview ? `<p class="text-lg border-l-8 border-neo-pink pl-4 mb-4">${esc(L.overview)}</p>` : ""}
                <nav class="flex flex-wrap gap-2 mb-2 sticky top-16 bg-white py-2 z-10 border-b-2 border-black">
                    ${LESSON_SECTIONS.filter(([id]) => present[id]).map(([id, label]) =>
                        `<button class="chip bg-white hover:bg-neo-yellow" onclick="$('ls-${id}').scrollIntoView({behavior: 'smooth'})">${label}</button>`).join("")}
                </nav>
                ${L.audio_script ? `<button class="btn mt-4" onclick="speak(CURRENT_LESSON.audio_script)"><i class="ph-bold ph-play"></i> Play audio lesson</button>` : ""}

                ${sectionTitle("explain", "Explanation", "ph-book-open")}
                <div class="space-y-4">${segments}</div>

                ${diagrams.length ? sectionTitle("diagrams", "How it works", "ph-flow-arrow") + diagramHtml : ""}
                ${steps.length ? sectionTitle("walkthrough", "Step by step", "ph-footprints") + stepHtml : ""}
                ${code.length ? sectionTitle("code", "Code examples", "ph-code") + codeHtml : ""}
                ${complexity.length ? sectionTitle("complexity", "Complexity", "ph-timer") + complexityHtml : ""}
                ${present.mistakes ? sectionTitle("mistakes", "Common mistakes", "ph-warning") + `
                    ${L.misconception_fix ? `<div class="border-4 border-black bg-neo-pink text-white p-4 mb-4"><b>YOUR MISCONCEPTION:</b> ${esc(L.misconception_fix)}</div>` : ""}
                    <ul class="space-y-2">${mistakes.map(m => `<li class="border-2 border-black bg-neo-red/10 p-3"><i class="ph-bold ph-x-circle text-neo-red"></i> ${esc(m)}</li>`).join("")}</ul>` : ""}
                ${points.length ? sectionTitle("points", "Key points", "ph-push-pin") + `
                    <ul class="border-4 border-black bg-neo-yellow p-4 space-y-2">${points.map(k => `<li><i class="ph-bold ph-check-square"></i> ${esc(k)}</li>`).join("")}</ul>` : ""}

                ${sectionTitle("practice", "Practice", "ph-pencil-simple-line")}
                <div class="space-y-6 mb-8">${L.practice.map((p, i) => `
                    <div class="border-4 border-black p-4">
                        <p class="font-bold mb-3 whitespace-pre-wrap">${i + 1}. ${esc(p.question)}</p>
                        <textarea id="practice-${i}" rows="4" class="field mb-2 font-mono" placeholder="Your answer or code..."></textarea>
                        <div class="flex flex-wrap items-center gap-3 mb-3">
                            <span class="font-bold uppercase text-xs">Sure?</span><div id="pconf-${i}" class="flex gap-1"></div>
                            <button class="btn" onclick="checkPractice(this, ${i})">Check -></button>
                        </div>
                        <div id="practice-result-${i}"></div>
                    </div>`).join("")}
                </div>
                <div class="border-t-4 border-black pt-6 flex flex-wrap gap-3">${finish}</div>
            </article>
        </div>`;
    L.practice.forEach((_, i) => confidencePicker(`pconf-${i}`, `pconf-${i}`));
    if (window.hljs) document.querySelectorAll("#lesson-body pre code").forEach(el => hljs.highlightElement(el));

    // Draw each diagram: as written, then with labels quoted, else show the source
    if (window.mermaid) {
        for (const [i, d] of diagrams.entries()) {
            let drawn = false;
            for (const variant of [d.mermaid, quoteMermaidLabels(d.mermaid)]) {
                try {
                    const { svg } = await mermaid.render(`mmd-${Date.now()}-${i}`, variant);
                    $(`diagram-${i}`).innerHTML = svg;
                    // Natural size, so wide diagrams scroll sideways instead of shrinking to unreadable text
                    const el = $(`diagram-${i}`).querySelector("svg");
                    const box = el && el.viewBox && el.viewBox.baseVal;
                    if (box && box.width) {
                        el.style.maxWidth = "none";
                        el.style.width = `${box.width}px`;
                        el.style.height = `${box.height}px`;
                    }
                    drawn = true;
                    break;
                } catch { /* try the next variant */ }
            }
            if (!drawn) $(`diagram-${i}`).innerHTML = `<pre class="text-xs whitespace-pre-wrap">${esc(d.mermaid)}</pre>`;
        }
    }
}

// Model-written labels often contain ( ) or other symbols that break Mermaid unless quoted: A[x (y)] -> A["x (y)"]
function quoteMermaidLabels(code) {
    return code
        .replace(/(\b[A-Za-z0-9_]+)\[([^\]"]+)\]/g, (_, id, label) => `${id}["${label.replace(/"/g, "'")}"]`)
        .replace(/(\b[A-Za-z0-9_]+)\{([^}"]+)\}/g, (_, id, label) => `${id}{"${label.replace(/"/g, "'")}"}`);
}

async function finishPathLesson(button) {
    await busy(button, "Saving...", async () => {
        await post(`/api/students/${sid()}/path/${LESSON_PATH_ITEM}/complete`);
        LESSON_PATH_ITEM = null;
        await loadStudent();
        go("path");
        toast("Marked as done. Here is what comes next.");
    });
}

async function checkPractice(button, index) {
    const answer = $(`practice-${index}`).value.trim();
    if (!answer) return toast("Write an answer first.", "error");
    await busy(button, "Checking...", async () => {
        const r = await post(`/api/tutor/lessons/${CURRENT_LESSON.lesson_id}/check`,
            { question_index: index, answer, confidence: chosen(`pconf-${index}`) });
        const ns = r.next_step;
        const next = ns.action === "reteach"
            ? `<button class="btn mt-2" onclick="requestLesson(this, {concept_id: CURRENT_LESSON.concept_id, level: '${esc(ns.level)}', format: '${esc(ns.format)}', reason: ${esc(JSON.stringify(ns.reason))}})">
                   <i class="ph-bold ph-arrow-counter-clockwise"></i> Re-teach as ${esc(ns.format)}</button>`
            : "";
        $(`practice-result-${index}`).innerHTML = `
            ${verdictCard(r.evaluation, ns.reason)}
            <p class="text-sm font-bold mt-2">Mastery ${pct(r.mastery.before)} -> ${pct(r.mastery.after)}
                ${r.learned_style ? ` · <span class="text-neo-pink">Learned style: ${esc(r.learned_style)}</span>` : ""}</p>
            ${next}`;
        loadStudent();
    });
}

// --------------------------------------------------------------------------- //
// Start
// --------------------------------------------------------------------------- //
VIEW_HOOKS.path = loadPath;

const ME = requireRole();  // students see only themselves; faculty can open any student

async function init() {
    if (!ME) return;
    if (ME.role === "student") {
        STUDENT_ID = ME.student_id;
        $("student-select").closest("label").remove();
    } else {
        const students = await api("/api/students").catch(() => []);
        if (!students.length) return toast("No students yet. Add them on the faculty Students page.", "error");
        if (!STUDENT_ID || !students.some(s => s.id === STUDENT_ID)) STUDENT_ID = students[0].id;
        $("student-select").innerHTML = students.map(s =>
            `<option value="${esc(s.id)}" ${s.id === STUDENT_ID ? "selected" : ""}>${esc(s.name)}</option>`).join("");
    }

    const graph = await loadConcepts();
    if (graph) {
        $("lesson-concept").innerHTML = graph.learning_order.map(id => `<option value="${esc(id)}">${esc(cname(id))}</option>`).join("");
    }
    await loadStudent();
    initViews("dashboard");
}

init();
