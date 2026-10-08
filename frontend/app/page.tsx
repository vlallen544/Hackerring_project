"use client";

import { useState } from "react";
import {
  ArrowDownToLine,
  ArrowUpRight,
  BookOpen,
  Check,
  CircleHelp,
  Clock3,
  FileText,
  GraduationCap,
  Headphones,
  Mic,
  Plus,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
} from "lucide-react";

type Role = "Faculty" | "Student";
type FacultyView = "Sources" | "Trust Board";
type StudentView = "Viva" | "My Lesson";

const sources = [
  { name: "DBMS Lecture Notes.pdf", detail: "Faculty material · 24 pages", status: "Reviewed", color: "green" },
  { name: "Database System Concepts.pptx", detail: "Lecture slides · 18 slides", status: "Needs review", color: "amber" },
  { name: "Data Analyst Role Profile.pdf", detail: "Industry reference · Updated Aug 2026", status: "Reviewed", color: "green" },
];

export default function Home() {
  const [role, setRole] = useState<Role>("Faculty");
  const [facultyView, setFacultyView] = useState<FacultyView>("Sources");
  const [studentView, setStudentView] = useState<StudentView>("Viva");
  const [listening, setListening] = useState(false);

  const navigation = role === "Faculty" ? ["Sources", "Trust Board"] : ["Viva", "My Lesson"];
  const activeView = role === "Faculty" ? facultyView : studentView;
  const selectView = (view: string) => {
    if (role === "Faculty") setFacultyView(view as FacultyView);
    else setStudentView(view as StudentView);
  };

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#home" aria-label="VidyaPath home">
          <span className="brand-mark"><BookOpen size={19} strokeWidth={2.2} /></span>
          <span>vidyapath<span className="brand-period">.</span></span>
        </a>
        <div className="workspace-label">WORKSPACE</div>
        <div className="course-switcher">
          <span className="course-glyph">D</span>
          <span className="course-copy"><strong>DBMS</strong><small>Semester IV</small></span>
          <span className="switch-chevron">⌄</span>
        </div>
        <div className="workspace-label nav-label">YOUR SPACE</div>
        <nav className="side-nav" aria-label={`${role} navigation`}>
          {navigation.map((item) => (
            <button
              className={`nav-item ${activeView === item ? "selected" : ""}`}
              key={item}
              onClick={() => selectView(item)}
            >
              {item === "Sources" && <FileText size={17} />}
              {item === "Trust Board" && <ShieldCheck size={17} />}
              {item === "Viva" && <Mic size={17} />}
              {item === "My Lesson" && <BookOpen size={17} />}
              <span>{item}</span>
              {item === "Trust Board" && <span className="nav-count">2</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="help-link"><CircleHelp size={16} /><span>Help & feedback</span></div>
          <div className="profile-row">
            <span className="avatar">{role === "Faculty" ? "AK" : "AS"}</span>
            <span className="profile-copy"><strong>{role === "Faculty" ? "Ananya Kumar" : "Aarav Shah"}</strong><small>{role}</small></span>
            <span className="switch-chevron">⌄</span>
          </div>
        </div>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <div className="breadcrumb"><span>Learning Studio</span><span className="crumb-separator">/</span><strong>{activeView}</strong></div>
          <div className="role-switch" aria-label="Choose workspace role">
            {(["Faculty", "Student"] as Role[]).map((option) => (
              <button
                key={option}
                className={role === option ? "role-active" : ""}
                onClick={() => setRole(option)}
                aria-pressed={role === option}
              >
                {option === "Faculty" ? <GraduationCap size={15} /> : <BookOpen size={15} />}
                {option}
              </button>
            ))}
          </div>
        </header>

        {role === "Faculty" && facultyView === "Sources" && (
          <div className="content-area">
            <div className="page-heading">
              <div><div className="eyebrow">FACULTY WORKSPACE <span>·</span> DBMS</div><h1>Sources</h1><p>Your course knowledge starts with material you trust.</p></div>
              <button className="primary-button"><Plus size={17} /> Add source</button>
            </div>
            <div className="overview-strip">
              <div><span className="overview-icon icon-mint"><FileText size={17} /></span><span><strong>3</strong><small>Sources added</small></span></div>
              <div><span className="overview-icon icon-yellow"><ShieldCheck size={17} /></span><span><strong>2</strong><small>Claims verified</small></span></div>
              <div><span className="overview-icon icon-coral"><TriangleAlert size={17} /></span><span><strong>1</strong><small>Needs attention</small></span></div>
              <div className="updated-copy"><Clock3 size={15} /> Updated 12 minutes ago</div>
            </div>
            <section className="section-block">
              <div className="section-heading"><div><h2>Course material</h2><p>Documents used to build lessons and answer student questions.</p></div><button className="text-button"><ArrowDownToLine size={16} /> Export list</button></div>
              <div className="source-table">
                <div className="table-head"><span>NAME</span><span>TYPE</span><span>STATUS</span><span>ADDED</span></div>
                {sources.map((source, index) => (
                  <div className="source-row" key={source.name}>
                    <span className="source-name"><span className="file-icon"><FileText size={18} /></span><span><strong>{source.name}</strong><small>{source.detail}</small></span></span>
                    <span className="source-type">{index === 1 ? "Slides" : "PDF"}</span>
                    <span><span className={`status-pill ${source.color}`}><i />{source.status}</span></span>
                    <span className="date-copy">{index === 2 ? "Today" : index === 1 ? "Yesterday" : "Oct 02"}</span>
                  </div>
                ))}
              </div>
            </section>
            <div className="bottom-note"><Sparkles size={16} /><span><strong>Next up</strong> Review one flagged claim in your Trust Board before generating the next lesson.</span><button onClick={() => setFacultyView("Trust Board")}>Open Trust Board <ArrowUpRight size={15} /></button></div>
          </div>
        )}

        {role === "Faculty" && facultyView === "Trust Board" && (
          <div className="content-area">
            <div className="page-heading"><div><div className="eyebrow">FACULTY WORKSPACE <span>·</span> DBMS</div><h1>Trust Board</h1><p>Review source conflicts and keep course knowledge current.</p></div><button className="secondary-button"><ShieldCheck size={16} /> Trust settings</button></div>
            <div className="trust-summary"><span className="summary-check"><Check size={19} /></span><div><strong>Knowledge base is mostly aligned</strong><p>2 claims verified across 3 sources. One item needs your review.</p></div><span className="summary-score">82<small>/100</small></span></div>
            <section className="section-block"><div className="section-heading"><div><h2>Claims to review</h2><p>AI suggestions are grounded in your uploaded materials.</p></div><span className="review-count">1 needs review</span></div>
              <article className="claim-row"><div className="claim-status"><TriangleAlert size={17} /></div><div className="claim-content"><span className="claim-label">RECENCY CONFLICT</span><h3>Are database indexes always beneficial for query performance?</h3><p>Lecture slides present indexes as a general optimization. Your notes mention write overhead, which adds important context.</p><div className="evidence-line"><FileText size={15} /><span>Database System Concepts.pptx <b>·</b> Slide 12</span></div></div><button className="outline-button">Review claim <ArrowUpRight size={15} /></button></article>
              <article className="claim-row verified-row"><div className="claim-status verified"><Check size={17} /></div><div className="claim-content"><span className="claim-label verified-label">VERIFIED</span><h3>Primary keys uniquely identify each record in a table.</h3><p>Consistent across faculty lecture notes and the course textbook.</p><div className="evidence-line"><FileText size={15} /><span>2 supporting sources <b>·</b> Last checked today</span></div></div><span className="accepted-label">Accepted</span></article>
            </section>
          </div>
        )}

        {role === "Student" && studentView === "Viva" && (
          <div className="content-area student-area">
            <div className="page-heading"><div><div className="eyebrow">STUDENT WORKSPACE <span>·</span> DBMS</div><h1>Viva practice</h1><p>A short check-in helps shape what you learn next.</p></div><span className="duration-label"><Clock3 size={15} /> About 5 min</span></div>
            <section className="viva-stage"><div className="stage-top"><span className="stage-tag"><Sparkles size={14} /> ADAPTIVE CHECK-IN</span><span className="stage-progress">01 <i /> 05</span></div><div className="question-content"><span className="question-topic">DATABASE DESIGN <b>·</b> KEYS</span><h2>In your own words, what makes a primary key different from a unique key?</h2><p>Take a moment to think it through. You can answer by voice or type.</p><textarea aria-label="Your answer" placeholder="Type your answer here..." /></div><div className="answer-actions"><button className={`primary-button record-button ${listening ? "recording" : ""}`} onClick={() => setListening(!listening)}><Mic size={17} />{listening ? "Listening..." : "Answer by voice"}</button><button className="text-button" onClick={() => setListening(false)}>Continue with text <ArrowUpRight size={15} /></button></div></section>
            <div className="provenance-note"><ShieldCheck size={17} /><span>This question is based on your faculty&apos;s DBMS notes.</span><button aria-label="About this question"><CircleHelp size={16} /></button></div>
          </div>
        )}

        {role === "Student" && studentView === "My Lesson" && (
          <div className="content-area student-area"><div className="page-heading"><div><div className="eyebrow">STUDENT WORKSPACE <span>·</span> DBMS</div><h1>My lesson</h1><p>Your learning path adjusts as you practice.</p></div><span className="duration-label">Week 4 <span className="week-dot" /></span></div>
            <section className="lesson-feature"><div className="lesson-copy"><span className="lesson-kicker"><BookOpen size={15} /> UP NEXT</span><h2>Relational algebra:<br />selection & projection</h2><p>A focused lesson based on your recent practice. Start with a quick refresher, then try two examples.</p><div className="lesson-meta"><span><Clock3 size={15} /> 12 min</span><span><ShieldCheck size={15} /> From faculty notes</span></div><button className="primary-button">Start lesson <ArrowUpRight size={16} /></button></div><div className="lesson-visual"><div className="diagram-chip chip-one">SELECT <span>σ</span></div><div className="diagram-chip chip-two">PROJECT <span>π</span></div><div className="diagram-line" /><div className="diagram-table"><span>student</span><span>course</span><span>grade</span><i /><i /><i /></div></div></section>
            <section className="progress-section"><div className="section-heading"><div><h2>Your progress</h2><p>Small steps, steady understanding.</p></div><button className="text-button">View all <ArrowUpRight size={15} /></button></div><div className="progress-list"><div><span className="progress-number">01</span><span className="progress-title"><strong>Relational model</strong><small>Completed · strong understanding</small></span><span className="progress-state complete"><Check size={15} /></span></div><div><span className="progress-number">02</span><span className="progress-title"><strong>Keys & constraints</strong><small>In progress · revisit one concept</small></span><span className="progress-state current"><span /></span></div><div><span className="progress-number">03</span><span className="progress-title"><strong>Relational algebra</strong><small>Up next · personalized refresher</small></span><span className="progress-state upcoming"><Headphones size={15} /></span></div></div></section>
          </div>
        )}
        <footer className="page-footer"><span>VidyaPath <i>·</i> Learning with trust</span><span>DBMS <i>·</i> Semester IV</span></footer>
      </section>
    </main>
  );
}