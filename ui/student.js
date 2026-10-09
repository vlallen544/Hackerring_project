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
// Voice: dictate answers (Web Speech API, Chrome/Edge). Reading aloud is speak()/readAloud() in vp.js.
// --------------------------------------------------------------------------- //
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
// Lessons are saved: the path opens the saved lesson for a topic at once, and "Make a fresh lesson" writes a new one
let SAVED_LESSONS = [];

async function loadSavedLessons() {
    if (!STUDENT_ID) return;
    SAVED_LESSONS = await api(`/api/students/${sid()}/lessons`).catch(() => []);
    $("lesson-saved").innerHTML = SAVED_LESSONS.length ? `
        <p class="text-xs font-bold uppercase text-gray-500 mb-2">// Your saved lessons (open instantly)</p>
        <div class="flex flex-wrap gap-2">${SAVED_LESSONS.map(l => `
            <button class="chip bg-white hover:bg-neo-yellow" onclick="openSavedLesson(${l.id})">
                <i class="ph-bold ph-book-open"></i> ${esc(cname(l.concept_id))} · ${esc(l.format)} · ${esc(l.created_at.slice(0, 10))}</button>`).join("")}
        </div>` : "";
}

async function openSavedLesson(id, { pathItemId = null, fresh = null } = {}) {
    try {
        CURRENT_LESSON = await api(`/api/tutor/lessons/${id}`);
        LESSON_PATH_ITEM = pathItemId;
        go("lessons");
        await renderLesson(CURRENT_LESSON);
        const saved = SAVED_LESSONS.find(l => l.id === id);
        $("lesson-body").insertAdjacentHTML("afterbegin", `
            <div class="border-4 border-black bg-white p-3 mb-6 flex flex-wrap items-center justify-between gap-3">
                <p class="font-bold"><i class="ph-bold ph-floppy-disk"></i> Your saved lesson${saved ? ` from ${esc(saved.created_at.slice(0, 10))}` : ""}</p>
                ${fresh ? `<button class="btn btn-light" onclick='requestLesson(this, ${esc(JSON.stringify(fresh))})'>
                    <i class="ph-bold ph-sparkle"></i> Make a fresh lesson</button>` : ""}
            </div>`);
        $("lesson-body").scrollIntoView({ behavior: "smooth" });
    } catch (err) {
        toast(err.message, "error");
    }
}

async function openLesson(conceptId, { format = "", kind = "lesson", pathItemId = null } = {}) {
    go("lessons");
    $("lesson-concept").value = conceptId;
    const fmt = kind === "lesson" ? "" : format;  // plain lessons: the agent decides (learned style may have changed)
    $("lesson-format").value = fmt;
    const override = { concept_id: conceptId, format: fmt };
    if (kind === "challenge") Object.assign(override, { level: "challenge", reason: "On the challenge track: all prerequisites are strong." });
    if (kind === "refresher") override.reason = "Refresher added by the Gap Predictor before an upcoming topic.";
    LESSON_PATH_ITEM = pathItemId;
    if (!SAVED_LESSONS.length) await loadSavedLessons();
    const saved = SAVED_LESSONS.find(l => l.concept_id === conceptId && (!fmt || l.format === fmt)
                                        && (kind !== "challenge" || l.level === "challenge"));  // newest first
    if (saved) return openSavedLesson(saved.id, { pathItemId, fresh: override });
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

// Saved vivas: a finished one reopens its result instantly, an unfinished one can be resumed
async function loadVivaHistory() {
    if (!STUDENT_ID) return;
    const vivas = await api(`/api/viva/${sid()}/sessions`).catch(() => []);
    $("viva-history").innerHTML = vivas.length ? `
        <p class="text-xs font-bold uppercase text-gray-500 mb-2">// Your vivas</p>
        <div class="flex flex-wrap gap-2">${vivas.map(v => v.status === "done"
            ? `<button class="chip bg-white hover:bg-neo-yellow" onclick="openVivaResult(${v.id})">
                   <i class="ph-bold ph-chart-bar"></i> Result · ${esc(v.created_at.slice(0, 10))} · ${v.concepts.length} topics</button>`
            : `<button class="chip bg-neo-yellow hover:bg-white" onclick="resumeViva(${v.id})">
                   <i class="ph-bold ph-play"></i> Resume · ${esc(v.created_at.slice(0, 10))} · ${v.answered} answer${v.answered === 1 ? "" : "s"} so far</button>`).join("")}
        </div>` : "";
}

async function openVivaResult(id) {
    try {
        const v = await api(`/api/viva/session/${id}`);
        $("viva-box").classList.add("hidden");
        $("viva-start").classList.add("hidden");
        renderVivaSummary(v.summary);
        $("viva-summary").scrollIntoView({ behavior: "smooth" });
    } catch (err) {
        toast(err.message, "error");
    }
}

async function resumeViva(id) {
    try {
        const v = await api(`/api/viva/session/${id}`);
        if (!v.question) return openVivaResult(id);
        VIVA_SESSION = id;
        $("viva-feedback").innerHTML = "";
        $("viva-summary").classList.add("hidden");
        showQuestion(v.question);
    } catch (err) {
        toast(err.message, "error");
    }
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
        <div class="card p-4 animate-slam" data-speak>
            <div class="flex justify-between items-center mb-2">
                <span class="chip ${color}">${esc(ev.verdict)}</span>
                <span class="flex items-center gap-2">${readAloudButton()}<span class="font-display text-xl">${pct(ev.score)}</span></span>
            </div>
            <p class="mb-2">${esc(ev.feedback)}</p>
            ${ev.misconception ? `<p class="text-sm border-2 border-black bg-neo-red/10 p-2 mb-2"><b>MISCONCEPTION:</b> ${esc(ev.misconception)}</p>` : ""}
            ${ev.missing_prerequisite ? `<p class="text-sm"><b>WEAK PREREQUISITE:</b> ${esc(cname(ev.missing_prerequisite))}</p>` : ""}
            <p class="text-xs font-bold uppercase mt-2 text-gray-500 no-read">// Agent: ${esc(decision)}</p>
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
            if (r.phone && r.phone.status === "sent") toast("The mix-ups found were sent to your phone.");
            loadStudent();
            loadVivaHistory();
        } else {
            showQuestion(r.next);
        }
    });
}

function renderVivaSummary(s) {
    const box = $("viva-summary");
    box.classList.remove("hidden");
    box.innerHTML = `
        <section class="card p-6 animate-slam" data-speak>
            <div class="flex flex-wrap justify-between items-center gap-2 mb-4">
                <h2 class="font-display text-3xl uppercase">Your result</h2>${readAloudButton()}
            </div>
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
        if (!$("path-message").dataset.fresh) renderLastCheck();
    } catch (err) {
        toast(err.message, "error");
    }
}

// --------------------------------------------------------------------------- //
// Phone nudges (Telegram): connect once; the agents then message the phone when the path changes
// --------------------------------------------------------------------------- //
const NUDGE_KIND = { path_change: "Path changed", misconception: "Mix-up found", reminder: "Due tomorrow", welcome: "Connected", test: "Test" };

function phoneResult(phone) {
    if (!phone || phone.status === "not_configured") return "";
    if (phone.status === "sent") return `<p class="mt-3 font-bold"><i class="ph-bold ph-device-mobile"></i> Sent to your phone ✓</p>`;
    if (phone.status === "not_linked") return `<p class="mt-3 text-sm"><i class="ph-bold ph-device-mobile"></i> Connect your phone below to get this as a message.</p>`;
    return `<p class="mt-3 text-sm"><i class="ph-bold ph-warning"></i> Could not reach your phone (${esc(phone.error || "unknown error")}). Your path is updated anyway.</p>`;
}

async function loadPhone() {
    if (!STUDENT_ID) return;
    const st = await api(`/api/notify/${sid()}`).catch(() => null);
    if (!st || !st.configured) return ($("phone-card").innerHTML = "");
    const item = n => `
            <li class="border-2 border-black p-2 bg-white text-sm">
                <span class="chip ${n.status === "sent" ? "bg-neo-green" : "bg-neo-red text-white"}">${n.status === "sent" ? "✓ Sent" : "✕ Failed"}</span>
                <span class="chip bg-white">${esc(NUDGE_KIND[n.kind] || n.kind)}</span>
                <span class="text-xs text-gray-500">${esc(n.created_at.slice(0, 16))} UTC</span>
                <p class="mt-1 whitespace-pre-wrap">${esc(n.text)}</p>
                ${n.error ? `<p class="text-xs mt-1">${esc(n.error)}</p>` : ""}
            </li>`;
    const older = st.recent.slice(3);
    const log = st.recent.length ? `
        <p class="text-xs font-bold uppercase text-gray-500 mt-4 mb-2">// Recent messages</p>
        <ul class="space-y-2">${st.recent.slice(0, 3).map(item).join("")}</ul>
        ${older.length ? `<details class="mt-2"><summary class="cursor-pointer text-sm font-bold uppercase">Older messages (${older.length})</summary>
            <ul class="space-y-2 mt-2">${older.map(item).join("")}</ul></details>` : ""}` : "";
    $("phone-card").innerHTML = st.linked ? `
        <section class="card p-6 mb-8">
            <div class="flex flex-wrap justify-between items-center gap-3">
                <p class="font-display text-xl uppercase"><i class="ph-bold ph-device-mobile"></i> Phone connected ✓</p>
                <span class="flex flex-wrap gap-2">
                    <button class="btn btn-light" onclick="testPhone(this)"><i class="ph-bold ph-paper-plane-tilt"></i> Send test</button>
                    <button class="btn btn-light" onclick="unlinkPhone(this)">Disconnect</button>
                </span>
            </div>
            <p class="text-sm mt-1">The agents message you on Telegram when they change your path or spot a mix-up.</p>
            ${log}
        </section>` : `
        <section class="card p-6 mb-8">
            <p class="font-display text-xl uppercase mb-1"><i class="ph-bold ph-device-mobile"></i> Get nudges on your phone</p>
            <p class="text-sm mb-4">Connect Telegram once. When the agents add a refresher or spot a mix-up, you get a message,
                without opening VidyaPath. You can disconnect any time.</p>
            <div id="phone-steps"><button class="btn" onclick="linkPhone(this)"><i class="ph-bold ph-telegram-logo"></i> Connect Telegram</button></div>
            ${log}
        </section>`;
}

async function linkPhone(button) {
    await busy(button, "Creating your link...", async () => {
        const r = await post(`/api/notify/${sid()}/link`);
        $("phone-steps").innerHTML = `
            <div class="flex flex-wrap gap-6 items-start">
                <div id="phone-qr" class="bg-white p-2 border-4 border-black" aria-label="QR code that opens the Telegram bot"></div>
                <ol class="list-decimal pl-6 space-y-2 flex-1 min-w-[220px]">
                    <li>Scan the code with your phone, or <a class="underline font-bold" href="${esc(r.url)}" target="_blank" rel="noopener">open @${esc(r.bot)}</a>.</li>
                    <li>In Telegram, tap <b>Start</b>.</li>
                    <li><button class="btn mt-1" onclick="verifyPhone(this)"><i class="ph-bold ph-check"></i> I've pressed Start</button></li>
                </ol>
            </div>`;
        if (window.QRCode) new QRCode($("phone-qr"), { text: r.url, width: 148, height: 148 });
        else $("phone-qr").remove();
    });
}

async function verifyPhone(button) {
    await busy(button, "Checking...", async () => {
        await post(`/api/notify/${sid()}/verify`);
        toast("Phone connected. Check Telegram for a welcome message.");
        loadPhone();
    });
}

async function testPhone(button) {
    await busy(button, "Sending...", async () => {
        await post(`/api/notify/${sid()}/test`);
        toast("Test message sent.");
        loadPhone();
    });
}

async function unlinkPhone(button) {
    await busy(button, "Disconnecting...", async () => {
        await api(`/api/notify/${sid()}`, { method: "DELETE" });
        loadPhone();
    });
}

// The last "Check for gaps" result, rebuilt from the saved risk events (one check = events within two minutes)
function renderLastCheck() {
    const events = (STUDENT && STUDENT.risk_events) || [];
    if (!events.length) return;
    const time = e => Date.parse(e.created_at.replace(" ", "T") + "Z");
    const run = events.filter(e => time(events[0]) - time(e) < 120000);
    $("path-message").innerHTML = `
        <div class="card p-6 mb-8 bg-white" data-speak>
            <div class="flex flex-wrap justify-between items-center gap-2 mb-2">
                <h2 class="font-display text-2xl uppercase">Last gap check: ${run.length} change${run.length > 1 ? "s" : ""}</h2>${readAloudButton()}
            </div>
            <p class="text-xs font-bold uppercase text-gray-500 mb-2 no-read">// ${esc(events[0].created_at.slice(0, 16))} UTC · saved</p>
            <ul class="list-disc pl-6 text-sm space-y-1">${run.map(e => `<li>${esc(e.reason)}</li>`).join("")}</ul>
        </div>`;
}

async function runPrediction(button) {
    await busy(button, "Checking for gaps...", async () => {
        const r = await post(`/api/students/${sid()}/predict`);
        $("path-message").dataset.fresh = "1";  // keep this result instead of the saved last check
        $("path-message").innerHTML = r.actions.length ? `
            <div class="card p-6 mb-8 bg-neo-yellow animate-slam" data-speak>
                <div class="flex flex-wrap justify-between items-center gap-2 mb-2">
                    <h2 class="font-display text-2xl uppercase">${r.actions.length} change${r.actions.length > 1 ? "s" : ""} made to your path</h2>${readAloudButton()}
                </div>
                ${r.message ? `<p class="text-lg mb-3">${esc(r.message.student_message)}</p>` : ""}
                <details class="text-sm"><summary class="cursor-pointer font-bold uppercase no-read">Exact reasons</summary>
                    <ul class="list-disc pl-6 mt-2">${r.actions.map(a => `<li>${esc(a.reason)}</li>`).join("")}</ul></details>
                <div class="no-read">${phoneResult(r.phone)}</div>
            </div>`
            : `<div class="mb-8 border-4 border-black bg-neo-green p-4 font-bold uppercase animate-slam">No new changes needed right now</div>`;
        renderRadar(r.gap_radar);
        renderPath(r.path);
        loadStudent();
        if (r.phone) loadPhone();
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
        loadSavedLessons();
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
            <aside class="card p-6 bg-neo-yellow h-fit xl:sticky xl:top-24 order-2 xl:order-1">
                <h3 class="font-display text-xl uppercase mb-3">Why this lesson looks like this</h3>
                <p class="text-sm mb-2"><b>LEVEL: ${esc(a.level)}</b><br>${esc(a.level_reason)}</p>
                <p class="text-sm mb-2"><b>FORMAT: ${esc(a.format)}</b><br>${esc(a.format_reason)}</p>
                ${a.targets_misconceptions.length ? `<p class="text-sm mb-2"><b>FIXES:</b> ${a.targets_misconceptions.map(esc).join("; ")}</p>` : ""}
                ${a.recapped_prerequisites.length ? `<p class="text-sm mb-2"><b>RECAPS:</b> ${a.recapped_prerequisites.map(c => esc(cname(c))).join(", ")}</p>` : ""}
                <p class="text-sm mt-4 mb-1"><b>FACULTY MATERIAL: ${esc(L.material_share_percent)}%</b> of the explanation</p>
                ${meter(L.material_share_percent / 100, "bg-neo-green")}
                <p class="text-xs mt-2">Diagrams, walkthrough and code are AI-written illustrations checked against the course's trusted facts.</p>
            </aside>
            <article class="card p-6 xl:col-span-3 order-1 xl:order-2" data-speak>
                <p class="text-xs font-bold uppercase text-gray-500 no-read">// ${esc(cname(L.concept_id))} · lesson #${esc(L.lesson_id)}</p>
                <h2 class="font-display text-3xl md:text-4xl uppercase leading-tight mb-3">${esc(L.title)}</h2>
                ${L.overview ? `<p class="text-lg border-l-8 border-neo-pink pl-4 mb-4">${esc(L.overview)}</p>` : ""}
                <nav class="lesson-nav flex flex-wrap gap-2 mb-2 sticky top-16 bg-white py-2 z-10 border-b-2 border-black">
                    ${LESSON_SECTIONS.filter(([id]) => present[id]).map(([id, label]) =>
                        `<button class="chip bg-white hover:bg-neo-yellow" onclick="$('ls-${id}').scrollIntoView({behavior: 'smooth'})">${label}</button>`).join("")}
                </nav>
                <div class="flex flex-wrap gap-3 mt-4">
                    ${L.audio_script ? `<button class="btn" onclick="speak(CURRENT_LESSON.audio_script, this)"><i class="ph-bold ph-play"></i> Play audio lesson</button>` : ""}
                    <button class="btn btn-light" onclick="readAloud(this)"><i class="ph-bold ph-speaker-high"></i> Read lesson aloud</button>
                </div>

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
                <div class="border-t-4 border-black pt-6 flex flex-wrap gap-3">${finish}
                    <button class="btn btn-light" onclick="doubtAbout('${esc(L.concept_id)}')"><i class="ph-bold ph-chat-circle-dots"></i> Have a doubt?</button></div>
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
// Doubt assistant
// --------------------------------------------------------------------------- //
let DOUBTS = [];

function doubtCard(d) {
    const cites = d.citations.map(c => `
        <span class="chip bg-white mr-1 mt-1" title="${esc(c.quote)}"><i class="ph-bold ph-book-open"></i> ${esc(c.source)} · p.${esc(c.page)}</span>`).join("");
    const looksLikeCode = d.example && /[;{}()=]|^\s{2,}/m.test(d.example);
    return `
        <article class="animate-slam">
            <div class="flex justify-end mb-2">
                <p class="max-w-2xl bg-neo-black text-white border-2 border-black px-4 py-2 font-bold">${esc(d.question)}</p>
            </div>
            <div class="card p-5 ${d.answerable ? "" : "bg-neo-yellow"}">
                <div class="flex flex-wrap justify-between items-center gap-2 mb-2">
                    <span class="flex flex-wrap gap-2">
                        ${d.answerable ? '<span class="chip bg-neo-green"><i class="ph-bold ph-seal-check"></i> From your course material</span>'
                                       : '<span class="chip bg-white"><i class="ph-bold ph-prohibit"></i> Not covered in your course</span>'}
                        ${d.concept_id ? `<span class="chip bg-white">${esc(cname(d.concept_id))}</span>` : ""}
                    </span>
                    <button class="chip bg-white hover:bg-neo-blue" onclick="speak(DOUBTS.find(x => x.id === ${d.id}).answer, this)">
                        <i class="ph-bold ph-speaker-high"></i> Read aloud</button>
                </div>
                <p class="leading-relaxed whitespace-pre-wrap">${esc(d.answer)}</p>
                ${d.example ? (looksLikeCode
                    ? `<pre class="mt-3 border-2 border-black"><code class="text-sm">${esc(d.example)}</code></pre>`
                    : `<p class="mt-3 border-l-8 border-neo-blue pl-3 text-sm"><b>EXAMPLE:</b> ${esc(d.example)}</p>`) : ""}
                ${cites ? `<div class="mt-3">${cites}</div>` : ""}
                ${!d.answerable && d.closest_topic ? `<button class="btn btn-light text-sm mt-3" onclick="openLesson('${esc(d.closest_topic)}')">
                    <i class="ph-bold ph-book-open"></i> Study ${esc(cname(d.closest_topic))} instead</button>` : ""}
                ${d.follow_ups.length ? `<div class="mt-4 pt-3 border-t-2 border-black border-dashed">
                    <p class="text-xs font-bold uppercase text-gray-500 mb-2">// Ask next</p>
                    <div class="flex flex-wrap gap-2">${d.follow_ups.map(f => `
                        <button class="chip bg-white hover:bg-neo-yellow text-left normal-case !font-normal" onclick="askFollowUp(this)">${esc(f)}</button>`).join("")}</div>
                </div>` : ""}
            </div>
        </article>`;
}

function renderDoubts() {
    $("doubt-list").innerHTML = DOUBTS.length ? DOUBTS.map(doubtCard).join("")
        : emptyState("No doubts yet. Ask anything about your course.");
    if (window.hljs) document.querySelectorAll("#doubt-list pre code").forEach(el => hljs.highlightElement(el));
}

async function loadDoubts() {
    if (!STUDENT_ID) return;
    try {
        DOUBTS = await api(`/api/doubts/${sid()}`);
        renderDoubts();
    } catch (err) {
        toast(err.message, "error");
    }
}

async function askDoubt(event) {
    if (event) event.preventDefault();
    const question = $("doubt-question").value.trim();
    if (!question) return toast("Type or speak your question first.", "error");
    await busy($("btn-doubt"), "Thinking...", async () => {
        const d = await post(`/api/doubts/${sid()}`, { question, concept_id: $("doubt-concept").value || null });
        DOUBTS.unshift(d);
        $("doubt-question").value = "";
        renderDoubts();
        window.scrollTo({ top: $("doubt-list").offsetTop - 120, behavior: "smooth" });
    });
}

function askFollowUp(button) {
    $("doubt-question").value = button.textContent.trim();
    askDoubt();
}

// From a lesson: open the doubt assistant with that topic already chosen
function doubtAbout(conceptId) {
    go("doubts");
    $("doubt-concept").value = conceptId;
    $("doubt-question").focus();
}

// --------------------------------------------------------------------------- //
// Start
// --------------------------------------------------------------------------- //
VIEW_HOOKS.path = () => { loadPath(); loadPhone(); };
VIEW_HOOKS.viva = loadVivaHistory;
VIEW_HOOKS.lessons = loadSavedLessons;
VIEW_HOOKS.doubts = loadDoubts;

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
        $("doubt-concept").insertAdjacentHTML("beforeend",
            graph.learning_order.map(id => `<option value="${esc(id)}">${esc(cname(id))}</option>`).join(""));
    }
    await loadStudent();
    initViews("dashboard");
}

init();
