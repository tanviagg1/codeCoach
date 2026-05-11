"""
CodeCoach AI — Streamlit Dashboard (Phase 5)

Run:
    streamlit run app.py

Pages:
  - Review: paste code, run the pipeline, see results per agent
  - History: past reviews table + debt score trend chart
"""

import time
import threading
from datetime import datetime
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from agents.context import AgentContext
from agents.langgraph_pipeline import LangGraphPipeline
from agents.pipeline import SequentialPipeline
from agents.review_agent import ReviewAgent
from agents.test_gen_agent import TestGenAgent
from agents.explainer_agent import ExplainerAgent
from agents.tech_debt_agent import TechDebtAgent
from agents.pr_summary_agent import PRSummaryAgent
from memory.vector_store import VectorStore

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="CodeCoach AI",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

if "context" not in st.session_state:
    st.session_state.context = None
if "running" not in st.session_state:
    st.session_state.running = False
if "vector_store" not in st.session_state:
    try:
        st.session_state.vector_store = VectorStore()
    except Exception:
        st.session_state.vector_store = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEVERITY_COLORS = {
    "CRITICAL": "#ff4444",
    "HIGH":     "#ff8800",
    "MEDIUM":   "#ffcc00",
    "LOW":      "#44bb44",
}

AGENT_REGISTRY = {
    "review": ReviewAgent,
    "tests": TestGenAgent,
    "explain": ExplainerAgent,
    "debt": TechDebtAgent,
    "pr": PRSummaryAgent,
}

PIPELINE_ORDER = ["review", "tests", "explain", "debt", "pr"]


def severity_badge(severity: str) -> str:
    color = SEVERITY_COLORS.get(severity, "#888888")
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold">{severity}</span>'


def debt_color(score: int) -> str:
    if score < 20:   return "#44bb44"
    if score < 40:   return "#88cc44"
    if score < 60:   return "#ffcc00"
    if score < 80:   return "#ff8800"
    return "#ff4444"


def debt_label(score: int) -> str:
    if score < 20:  return "PRISTINE"
    if score < 40:  return "LOW"
    if score < 60:  return "MODERATE"
    if score < 80:  return "HIGH"
    return "CRITICAL"


def run_pipeline(code: str, filename: str, model: str, use_rag: bool, selected_agents: list[str]) -> AgentContext:
    """Run the pipeline and return the enriched context."""
    vector_store = st.session_state.vector_store if use_rag else None

    context = AgentContext(
        code=code,
        filename=filename,
        language=_detect_language(filename),
        model=model,
    )

    all_selected = set(selected_agents) == set(PIPELINE_ORDER)
    if all_selected:
        pipeline = LangGraphPipeline(model=model, vector_store=vector_store)
    else:
        ordered = [name for name in PIPELINE_ORDER if name in selected_agents]
        if "review" in ordered and vector_store:
            agents = [
                ReviewAgent(model=model, vector_store=vector_store) if name == "review"
                else AGENT_REGISTRY[name](model=model)
                for name in ordered
            ]
        else:
            agents = [AGENT_REGISTRY[name](model=model) for name in ordered]
        pipeline = SequentialPipeline(agents)

    context = pipeline.run(context)

    # Store in ChromaDB after run
    if vector_store and context.review_summary:
        try:
            vector_store.store_review(context)
        except Exception:
            pass

    return context


def _detect_language(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".go": "go", ".java": "java", ".rb": "ruby", ".rs": "rust",
    }.get(ext, "python")


def export_markdown(context: AgentContext) -> str:
    """Export the full review as a Markdown string."""
    lines = [
        f"# CodeCoach AI Review — `{context.filename}`",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
    ]

    if context.review_issues:
        lines += ["## Code Review Issues", ""]
        for issue in sorted(context.review_issues, key=lambda i: ["CRITICAL","HIGH","MEDIUM","LOW"].index(i.get("severity","LOW"))):
            lines.append(f"- **Line {issue.get('line','?')}** `[{issue.get('severity','?')}]` {issue.get('message','')}")
        lines += ["", f"**Summary:** {context.review_summary}", ""]

    if context.debt_score is not None:
        lines += [f"## Tech Debt Score: {context.debt_score}/100 ({debt_label(context.debt_score)})", ""]
        if context.debt_hotspots:
            lines.append("### Hotspots")
            for h in context.debt_hotspots:
                lines.append(f"- **Line {h.get('line','?')}** `[{h.get('severity','?')}]` {h.get('description','')}")
            lines.append("")

    if context.explanation:
        lines += ["## Code Explanation", "", context.explanation, ""]

    if context.generated_tests:
        lines += ["## Generated Tests", "", "```python", context.generated_tests, "```", ""]

    if context.pr_title:
        lines += [f"## PR Summary", "", f"**{context.pr_title}**", "", context.pr_body, ""]

    if context.alert_message:
        lines += ["## ⚠️ Critical Debt Alert", "", f"```\n{context.alert_message}\n```", ""]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🔍 CodeCoach AI")
    st.markdown("Multi-agent code review powered by Ollama")
    st.divider()

    page = st.radio("Navigate", ["Review", "History"], label_visibility="collapsed")
    st.divider()

    st.subheader("Settings")
    model = st.selectbox("Model", ["llama3.1:8b", "llama3.2:3b", "codellama:7b"], index=0)
    use_rag = st.toggle("RAG (use past reviews)", value=True,
                         disabled=st.session_state.vector_store is None,
                         help="Inject similar past reviews into the prompt")
    if st.session_state.vector_store is None:
        st.caption("⚠️ ChromaDB unavailable — RAG disabled")

    st.subheader("Agents")
    selected_agents = []
    for name in PIPELINE_ORDER:
        checked = st.checkbox(name.capitalize(), value=True, key=f"agent_{name}")
        if checked:
            selected_agents.append(name)


# ---------------------------------------------------------------------------
# Page: Review
# ---------------------------------------------------------------------------

if page == "Review":
    st.title("Code Review")

    col1, col2 = st.columns([3, 1])
    with col1:
        code_input = st.text_area(
            "Paste your code here",
            height=300,
            placeholder="def authenticate(user, password):\n    ...",
            label_visibility="collapsed",
        )
    with col2:
        filename = st.text_input("Filename", value="code.py")
        st.markdown("&nbsp;")
        run_clicked = st.button("▶ Run Review", type="primary", use_container_width=True,
                                 disabled=not code_input.strip() or not selected_agents)
        if not selected_agents:
            st.warning("Select at least one agent.")

    # Run pipeline
    if run_clicked and code_input.strip():
        with st.spinner("Running CodeCoach pipeline..."):
            start = time.time()
            try:
                ctx = run_pipeline(code_input, filename, model, use_rag, selected_agents)
                st.session_state.context = ctx
                elapsed = round(time.time() - start, 1)
                st.success(f"Review complete in {elapsed}s")
            except Exception as e:
                st.error(f"Pipeline error: {e}")
                st.session_state.context = None

    # Results
    ctx = st.session_state.context
    if ctx:
        st.divider()

        # Alert banner
        if ctx.alert_message:
            st.error(f"⚠️ **Critical Debt Alert**\n\n{ctx.alert_message}")

        tabs = st.tabs(["📋 Review", "📊 Tech Debt", "💡 Explanation", "🧪 Tests", "📝 PR Summary", "⏱ Timings"])

        # --- Review tab ---
        with tabs[0]:
            if ctx.review_issues:
                st.markdown(f"**{len(ctx.review_issues)} issue(s) found**")

                # Severity breakdown
                counts = {s: sum(1 for i in ctx.review_issues if i.get("severity") == s)
                          for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]}
                c1, c2, c3, c4 = st.columns(4)
                for col, (sev, count) in zip([c1, c2, c3, c4], counts.items()):
                    col.metric(sev, count)

                st.markdown("---")
                sorted_issues = sorted(ctx.review_issues,
                    key=lambda i: ["CRITICAL","HIGH","MEDIUM","LOW"].index(i.get("severity","LOW")))
                for issue in sorted_issues:
                    sev = issue.get("severity", "?")
                    color = SEVERITY_COLORS.get(sev, "#888")
                    with st.container():
                        st.markdown(
                            f'<div style="border-left:4px solid {color};padding:8px 12px;margin:4px 0;background:#1a1a1a;border-radius:4px">'
                            f'<b>Line {issue.get("line","?")} </b>'
                            f'{severity_badge(sev)} &nbsp; {issue.get("message","")}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
            else:
                st.success("✅ No issues found — clean code!")

            if ctx.review_summary:
                st.markdown("**Summary**")
                st.info(ctx.review_summary)

        # --- Debt tab ---
        with tabs[1]:
            if ctx.debt_score is not None:
                col1, col2 = st.columns([1, 2])
                with col1:
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=ctx.debt_score,
                        domain={"x": [0, 1], "y": [0, 1]},
                        title={"text": "Debt Score"},
                        gauge={
                            "axis": {"range": [0, 100]},
                            "bar": {"color": debt_color(ctx.debt_score)},
                            "steps": [
                                {"range": [0, 20],  "color": "#1a2a1a"},
                                {"range": [20, 40], "color": "#1a2a10"},
                                {"range": [40, 60], "color": "#2a2a10"},
                                {"range": [60, 80], "color": "#2a1a10"},
                                {"range": [80, 100],"color": "#2a1010"},
                            ],
                        },
                    ))
                    fig.update_layout(height=250, margin=dict(t=30, b=0, l=20, r=20),
                                      paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown(f"**{debt_label(ctx.debt_score)}** — {ctx.debt_score}/100")

                with col2:
                    if ctx.debt_hotspots:
                        st.markdown("**Hotspots**")
                        for h in ctx.debt_hotspots:
                            sev = h.get("severity", "?")
                            color = SEVERITY_COLORS.get(sev, "#888")
                            st.markdown(
                                f'<div style="border-left:4px solid {color};padding:8px 12px;margin:4px 0;background:#1a1a1a;border-radius:4px">'
                                f'<b>Line {h.get("line","?")}</b> {severity_badge(sev)}<br>'
                                f'{h.get("description","")}'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.info("No hotspots identified.")
            else:
                st.info("Debt agent was not run.")

        # --- Explanation tab ---
        with tabs[2]:
            if ctx.explanation:
                st.markdown(ctx.explanation)
            else:
                st.info("Explainer agent was not run.")

        # --- Tests tab ---
        with tabs[3]:
            if ctx.generated_tests:
                count = ctx.generated_tests.count("def test_")
                st.markdown(f"**{count} test function(s) generated**")
                st.code(ctx.generated_tests, language="python")
                st.download_button(
                    "⬇ Download tests.py",
                    data=ctx.generated_tests,
                    file_name=f"{Path(ctx.filename).stem}_tests.py",
                    mime="text/plain",
                )
            else:
                st.info("Test generation agent was not run.")

        # --- PR Summary tab ---
        with tabs[4]:
            if ctx.pr_title:
                st.markdown(f"### {ctx.pr_title}")
                st.markdown(ctx.pr_body)
            else:
                st.info("PR summary agent was not run.")

        # --- Timings tab ---
        with tabs[5]:
            if ctx.timings:
                fig = px.bar(
                    x=list(ctx.timings.keys()),
                    y=list(ctx.timings.values()),
                    labels={"x": "Agent", "y": "Time (s)"},
                    color=list(ctx.timings.values()),
                    color_continuous_scale="Blues",
                )
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white",
                                  showlegend=False, coloraxis_showscale=False)
                st.plotly_chart(fig, use_container_width=True)
                total = sum(ctx.timings.values())
                st.caption(f"Total pipeline time: {total:.1f}s")

            if ctx.errors:
                st.warning(f"{len(ctx.errors)} warning(s):")
                for err in ctx.errors:
                    st.caption(f"• {err}")

        # Export
        st.divider()
        md = export_markdown(ctx)
        st.download_button(
            "⬇ Export as Markdown",
            data=md,
            file_name=f"{Path(ctx.filename).stem}_review.md",
            mime="text/markdown",
        )


# ---------------------------------------------------------------------------
# Page: History
# ---------------------------------------------------------------------------

elif page == "History":
    st.title("Review History")

    vs = st.session_state.vector_store
    if vs is None:
        st.error("ChromaDB is not available. Start Ollama and restart the app.")
        st.stop()

    reviews = vs.list_reviews(limit=50)
    total = vs.count()

    if not reviews:
        st.info("No reviews stored yet. Run some reviews first!")
        st.stop()

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Reviews", total)

    scores = [r["debt_score"] for r in reviews if r.get("debt_score", -1) >= 0]
    if scores:
        c2.metric("Avg Debt Score", f"{sum(scores) / len(scores):.0f}/100")
        c3.metric("Highest Debt", f"{max(scores)}/100")
        c4.metric("Files Reviewed", len({r["filename"] for r in reviews}))

    st.divider()

    # Debt score trend chart
    if scores:
        st.subheader("Debt Score Over Time")
        chart_reviews = [r for r in reversed(reviews) if r.get("debt_score", -1) >= 0]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(range(1, len(chart_reviews) + 1)),
            y=[r["debt_score"] for r in chart_reviews],
            mode="lines+markers",
            marker=dict(
                color=[debt_color(r["debt_score"]) for r in chart_reviews],
                size=10,
            ),
            line=dict(color="#4488ff", width=2),
            text=[r["filename"] for r in chart_reviews],
            hovertemplate="<b>%{text}</b><br>Debt: %{y}/100<extra></extra>",
        ))
        fig.add_hline(y=80, line_dash="dash", line_color="#ff4444",
                      annotation_text="Critical threshold (80)")
        fig.update_layout(
            xaxis_title="Review #",
            yaxis_title="Debt Score",
            yaxis=dict(range=[0, 105]),
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            height=300,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Reviews table
    st.subheader("Past Reviews")
    for r in reviews:
        score = r.get("debt_score", -1)
        score_str = f"{score}/100" if score >= 0 else "—"
        color = debt_color(score) if score >= 0 else "#888"
        critical = r.get("critical_count", 0)
        issues = r.get("issue_count", 0)

        with st.expander(
            f"{'🔴' if critical > 0 else '🟡' if issues > 0 else '🟢'} "
            f"**{r['filename']}** — Debt: {score_str} — {issues} issue(s) — {r['reviewed_at'][:16]}"
        ):
            col1, col2, col3 = st.columns(3)
            col1.metric("Debt Score", score_str)
            col2.metric("Issues", issues)
            col3.metric("Critical", critical)

            if r.get("review_summary"):
                st.markdown("**Summary**")
                st.info(r["review_summary"])
