# ── app.py ─────────────────────────────────────────────────
# Self-Improving Code Agent — Final (Week 5)
# Run with: streamlit run app.py

import streamlit as st
import json, os, sys
from datetime import datetime
from groq import Groq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sandbox import run_code
from critique import critique_code
from benchmark import benchmark_code, benchmark_memory_only, compare, log_benchmark
from evaluate import evaluate_all, run_agent, run_baseline
from humaneval_problems import PROBLEMS
from config import GROQ_API_KEY, AVAILABLE_MODELS, MAX_RETRIES, MAX_CRITIQUE_ROUNDS, LOG_DIR, BENCHMARK_RUNS

try:
    from memory import store_failure, build_memory_context, retrieve_similar_failures, memory_stats, clear_memory
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False

st.set_page_config(page_title="Code Agent", page_icon="🤖", layout="wide")
st.markdown("<style>#MainMenu{visibility:hidden},footer,header{visibility:hidden}.stCode{border-radius:8px}</style>", unsafe_allow_html=True)

SYSTEM_PROMPT = """You are an expert Python programmer.
Return ONLY raw Python code. No markdown. No backticks. No explanations.
Code must be complete and runnable. Do not use input(). Only use standard library."""

for k, v in {"history":[],"total_tasks":0,"total_success":0,"task_input":"","he_results":None}.items():
    if k not in st.session_state: st.session_state[k] = v

def log(task, attempt, code, result, phase="generate"):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(os.path.join(LOG_DIR,"attempts.jsonl"),"a",encoding="utf-8") as f:
        f.write(json.dumps({"timestamp":datetime.now().isoformat(),"phase":phase,"task":task,
            "attempt":attempt,"code":code,"success":result["success"],
            "error":result.get("error"),"output":result.get("output")})+"\n")

def gen_messages(task, error=None, attempt=1, memory_context=""):
    system = SYSTEM_PROMPT + (f"\n\n{memory_context}" if memory_context else "")
    msgs = [{"role":"system","content":system}]
    if error and attempt > 1:
        msgs.append({"role":"user","content":f"Task: {task}\n\nAttempt {attempt-1} failed:\n{error}\n\nFix it. Return only corrected Python code."})
    else:
        msgs.append({"role":"user","content":f"Task: {task}\n\nWrite Python code to solve this."})
    return msgs

def stream_code(client, messages, model, widget):
    code = ""
    resp = client.chat.completions.create(model=model, messages=messages, temperature=0.1, max_tokens=2048, stream=True)
    for chunk in resp:
        code += chunk.choices[0].delta.content or ""
        widget.code(code, language="python")
    return code

def render_comparison(cmp):
    if not cmp or not cmp.get("valid"): return
    st.markdown("#### Before vs After Critique")
    c1,c2,c3 = st.columns(3)
    rt = cmp["runtime_delta_ms"]
    c1.metric("Runtime", f"{'▲' if cmp['runtime_improved'] else '▼'} {abs(rt)}ms ({abs(cmp['runtime_pct'])}%)",
        delta="Faster" if cmp["runtime_improved"] else "Slower", delta_color="normal" if cmp["runtime_improved"] else "inverse")
    mem = cmp["memory_delta_kb"]
    c2.metric("Memory", f"{'▲' if cmp['memory_improved'] else '▼'} {abs(mem)}KB ({abs(cmp['memory_pct'])}%)",
        delta="Less" if cmp["memory_improved"] else "More", delta_color="normal" if cmp["memory_improved"] else "inverse")
    if cmp["overall_improved"]:
        c3.success("✅ Critique improved code")
    else:
        c3.warning("⚠️ No measurable gain")

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.title("🤖 Code Agent")
    st.caption("Final build · All 4 systems active · Zero cost")
    st.divider()
    api_key = GROQ_API_KEY

    if not api_key:
        st.error("Groq API key not configured in Streamlit secrets.")
        st.stop()
    model = st.selectbox("Model", AVAILABLE_MODELS, index=0)
    c1,c2 = st.columns(2)
    max_retries  = c1.number_input("Fix retries", 1, 10, MAX_RETRIES)
    crit_rounds  = c2.number_input("Critique rounds", 1, 5, MAX_CRITIQUE_ROUNDS)
    bench_runs   = st.number_input("Benchmark runs", 1, 10, BENCHMARK_RUNS)
    st.divider()
    st.subheader("🔧 Features")
    enable_critique  = st.toggle("Critique Agent",  value=True)
    enable_memory    = st.toggle("Vector Memory",   value=MEMORY_AVAILABLE, disabled=not MEMORY_AVAILABLE)
    enable_benchmark = st.toggle("Benchmarking",    value=True)
    if not MEMORY_AVAILABLE:
        st.caption("`pip install chromadb sentence-transformers`")
    st.divider()
    st.subheader("🧠 Memory")
    if MEMORY_AVAILABLE and enable_memory:
        stats = memory_stats()
        st.metric("Failures stored", stats["total_failures_stored"])
        if st.button("Clear memory", use_container_width=True):
            clear_memory(); st.rerun()
    else:
        st.caption("Off or not installed.")
    st.divider()
    st.subheader("📊 Stats")
    total = st.session_state.total_tasks
    m1,m2 = st.columns(2)
    m1.metric("Tasks", total)
    m2.metric("Success", f"{(st.session_state.total_success/total*100):.0f}%" if total else "—")
    if total:
        m3,m4 = st.columns(2)
        m3.metric("Avg fix attempts", f"{sum(h['attempts'] for h in st.session_state.history)/total:.1f}")
        m4.metric("Avg critique rds", f"{sum(h.get('critique_rounds',0) for h in st.session_state.history)/total:.1f}")
    st.divider()
    if st.button("Clear session", use_container_width=True):
        st.session_state.update({"history":[],"total_tasks":0,"total_success":0})
        st.rerun()

# ── Tabs ──────────────────────────────────────────────────────
tab_agent, tab_eval = st.tabs(["🤖 Agent", "🏆 HumanEval Benchmark"])

# ════════════════════════════════════════════════════════════
# TAB 1 — Agent
# ════════════════════════════════════════════════════════════
with tab_agent:
    st.header("Self-Improving Code Agent", divider="gray")

    with st.expander("💡 Examples", expanded=False):
        for ex in [
            "Find all primes up to 100 using Sieve of Eratosthenes and print them.",
            "Sort [{'name':'Alice','score':88},{'name':'Bob','score':73},{'name':'Charlie','score':95}] by score descending, print name + rank.",
            "Binary search [2,5,8,12,16,23,38,56,72,91] for 23. Print its index.",
            "Count word frequency in 'the cat sat on the mat the cat' and print top 3.",
            "Generate Pascal's triangle with 6 rows and print it.",
            "Implement merge sort on [38,27,43,3,9,82,10] and print sorted result.",
        ]:
            if st.button(f"↗ {ex[:75]}", use_container_width=True, key=f"ex_{ex[:10]}"):
                st.session_state.task_input = ex; st.rerun()

    task = st.text_area("Your task", value=st.session_state.task_input, height=100,
        placeholder="Describe the task — be specific about inputs, outputs, and edge cases.")
    r_col,c_col = st.columns([4,1])
    run_clicked = r_col.button("▶  Run Agent", type="primary", use_container_width=True, disabled=not task or not api_key)
    if c_col.button("✕ Clear", use_container_width=True):
        st.session_state.task_input = ""; st.rerun()

    if run_clicked and task and api_key:
        st.session_state.task_input = task
        client = Groq(api_key=api_key)
        st.divider()
        pn = [1]
        def ph(title, icon="⚙️"):
            st.subheader(f"{icon} Phase {pn[0]} — {title}"); pn[0]+=1

        # Phase 1: Memory
        memory_context, memories_found = "", []
        if MEMORY_AVAILABLE and enable_memory:
            ph("Memory Lookup","🧠")
            with st.container(border=True):
                with st.spinner("Searching…"):
                    memories_found = retrieve_similar_failures(task)
                    memory_context = build_memory_context(task)
                if memories_found:
                    st.warning(f"Found **{len(memories_found)}** past failure(s) — injecting as context.")
                    for i,m in enumerate(memories_found,1):
                        with st.expander(f"Memory {i} — similarity: {m['similarity']}", expanded=False):
                            st.caption("Task"); st.info(m["task"])
                            st.caption("Failed code"); st.code(m["code"],language="python")
                            st.caption("Error"); st.code(m["error"],language="bash")
                else:
                    st.success("No similar failures — generating fresh.")
        else:
            pn[0]+=1

        # Phase 2: Generator
        ph("Generator Agent")
        progress = st.progress(0.0)
        error_feedback = None
        working_code = working_output = None
        gen_attempts = 0

        for attempt in range(1, int(max_retries)+1):
            progress.progress(attempt/max_retries, text=f"Attempt {attempt} of {int(max_retries)}")
            with st.container(border=True):
                hc,bc = st.columns([5,1])
                hc.markdown(f"**Attempt {attempt}**" + (f" · 🧠 {len(memories_found)} context(s)" if attempt==1 and memories_found else ""))
                badge = bc.empty(); badge.info("Generating…")
                display = st.empty()
                try:
                    ctx = memory_context if attempt==1 else ""
                    code = stream_code(client, gen_messages(task,error_feedback,attempt,ctx), model, display)
                except Exception as e:
                    st.error(f"LLM error: {e}"); break
                badge.warning("Running…")
                result = run_code(code)
                log(task, attempt, code, result, "generate")
                gen_attempts += 1
                if result["success"]:
                    badge.success("✅ Passed")
                    if result["output"]: st.caption("Output"); st.code(result["output"],language="text")
                    working_code = code; working_output = result["output"] or ""; break
                else:
                    badge.error("❌ Error")
                    with st.expander("Traceback",expanded=False): st.code(result["error"],language="bash")
                    if MEMORY_AVAILABLE and enable_memory:
                        store_failure(task, code, result["error"]); st.caption("🧠 Stored in memory.")
                    error_feedback = result["error"]

        progress.empty()
        if not working_code:
            st.error(f"Failed after {int(max_retries)} attempts.")
            st.session_state.total_tasks+=1
            st.session_state.history.append({"task":task,"success":False,"attempts":gen_attempts,"critique_rounds":0,"code":None,"output":None,"benchmark":None,"timestamp":datetime.now().strftime("%H:%M:%S")})
            st.stop()
        st.success(f"✅ Working code found in {gen_attempts} attempt(s).")

        # Benchmark before critique
        bm_before = None
        if enable_benchmark and enable_critique:
            with st.spinner(f"Benchmarking original ({int(bench_runs)} runs)…"):
                bm_before = benchmark_code(working_code, runs=int(bench_runs))
                bm_before["peak_memory_kb"] = benchmark_memory_only(working_code)

        final_code, final_output, crit_count = working_code, working_output, 0

        # Phase 3: Critique
        if enable_critique:
            ph("Critique Agent","🔍")
            for rnd in range(1, int(crit_rounds)+1):
                crit_count+=1
                with st.container(border=True):
                    ch,cb = st.columns([5,1]); ch.markdown(f"**Round {rnd}**")
                    cbadge = cb.empty(); cbadge.info("Reviewing…")
                    with st.expander("Code under review", expanded=(rnd==1)): st.code(final_code,language="python")
                    verdict = critique_code(task,final_code,final_output,client_override=client,model_override=model)
                    if verdict["verdict"]=="APPROVED":
                        cbadge.success("✅ Approved"); st.success("Code is clean and efficient."); break
                    cbadge.warning("🔁 Rewrite requested")
                    for issue in verdict["issues"]: st.warning(f"• {issue}")
                    with st.expander("Instructions",expanded=False): st.info(verdict["instructions"])
                    rw_display = st.empty()
                    try:
                        new_code = stream_code(client,[
                            {"role":"system","content":"Return ONLY raw Python code. No markdown."},
                            {"role":"user","content":f"Task: {task}\n\nCode:\n{final_code}\n\nIssues:\n{verdict['instructions']}\n\nRewrite fixing all issues."}
                        ], model, rw_display)
                    except Exception as e:
                        st.error(f"Rewrite error: {e}"); break
                    recheck = run_code(new_code)
                    log(task,rnd,new_code,recheck,"critique")
                    if recheck["success"]:
                        final_code=new_code; final_output=recheck["output"] or ""
                        st.success("✅ Rewrite valid.")
                        if recheck["output"]: st.caption("New output"); st.code(recheck["output"],language="text")
                    else:
                        st.error("Rewrite broke code — keeping previous."); break

        # Phase 4: Benchmark
        bm_after = bm_comparison = None
        if enable_benchmark:
            ph("Benchmark Results","📊")
            with st.container(border=True):
                if enable_critique and bm_before:
                    with st.spinner(f"Benchmarking optimised ({int(bench_runs)} runs)…"):
                        bm_after = benchmark_code(final_code, runs=int(bench_runs))
                        bm_after["peak_memory_kb"] = benchmark_memory_only(final_code)
                    c1,c2 = st.columns(2)
                    with c1:
                        st.caption("Before critique")
                        st.metric("Avg runtime", f"{bm_before['avg_runtime_ms']} ms")
                        st.metric("Peak memory", f"{bm_before['peak_memory_kb']} KB")
                    with c2:
                        st.caption("After critique")
                        st.metric("Avg runtime", f"{bm_after['avg_runtime_ms']} ms")
                        st.metric("Peak memory", f"{bm_after['peak_memory_kb']} KB")
                    st.divider()
                    bm_comparison = compare(bm_before, bm_after)
                    render_comparison(bm_comparison)
                    log_benchmark(task, bm_before, bm_after, bm_comparison)
                else:
                    with st.spinner(f"Benchmarking ({int(bench_runs)} runs)…"):
                        bm_after = benchmark_code(final_code, runs=int(bench_runs))
                        bm_after["peak_memory_kb"] = benchmark_memory_only(final_code)
                    st.metric("Avg runtime", f"{bm_after['avg_runtime_ms']} ms")
                    st.metric("Peak memory", f"{bm_after['peak_memory_kb']} KB")

        # Final Result
        st.divider(); st.subheader("🏁 Final Result")
        cols = st.columns(4)
        cols[0].metric("Generator attempts", gen_attempts)
        cols[1].metric("Critique rounds", crit_count)
        cols[2].metric("Memories used", len(memories_found))
        cols[3].metric("Status","✅ Success")
        st.caption("Final code"); st.code(final_code, language="python")
        if final_output: st.caption("Output"); st.code(final_output, language="text")
        st.success("Agent completed.")
        st.session_state.total_tasks+=1; st.session_state.total_success+=1
        st.session_state.history.append({"task":task,"success":True,"attempts":gen_attempts,
            "critique_rounds":crit_count,"memories_used":len(memories_found),
            "code":final_code,"output":final_output,"benchmark_before":bm_before,
            "benchmark_after":bm_after,"comparison":bm_comparison,
            "timestamp":datetime.now().strftime("%H:%M:%S")})

    if st.session_state.history:
        st.divider(); st.subheader("📋 Session History")
        for item in reversed(st.session_state.history):
            icon = "✅" if item["success"] else "🔴"
            short = item["task"][:65]+"..." if len(item["task"])>65 else item["task"]
            with st.expander(f"{icon}  [{item['timestamp']}]  {short}", expanded=False):
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("Result","Success" if item["success"] else "Failed")
                c2.metric("Fix attempts",item["attempts"])
                c3.metric("Critique rounds",item.get("critique_rounds",0))
                c4.metric("Memories used",item.get("memories_used",0))
                if item.get("comparison"): render_comparison(item["comparison"])
                if item.get("code"): st.caption("Final code"); st.code(item["code"],language="python")
                if item.get("output"): st.caption("Output"); st.code(item["output"],language="text")

# ════════════════════════════════════════════════════════════
# TAB 2 — HumanEval Benchmark
# ════════════════════════════════════════════════════════════
with tab_eval:
    st.header("HumanEval Benchmark", divider="gray")
    st.markdown("Runs your agent against **20 real HumanEval problems** and compares pass@1 vs plain Llama with no agent loop.")

    # Problem overview
    with st.expander("📋 All 20 problems", expanded=False):
        easy   = [p for p in PROBLEMS if p["difficulty"]=="easy"]
        medium = [p for p in PROBLEMS if p["difficulty"]=="medium"]
        hard   = [p for p in PROBLEMS if p["difficulty"]=="hard"]
        for label, group in [("🟢 Easy", easy),("🟡 Medium", medium),("🔴 Hard", hard)]:
            st.markdown(f"**{label}**")
            for p in group:
                st.caption(f"`{p['id']}` — `{p['entry_point']}`")

    # Controls
    col_a, col_b, col_c = st.columns(3)
    run_subset  = col_a.checkbox("Quick run (easy only, 8 problems)", value=True)
    run_he_btn  = col_b.button("▶  Run Benchmark", type="primary",
        disabled=not api_key, use_container_width=True)
    clear_he    = col_c.button("Clear results", use_container_width=True)

    if clear_he:
        st.session_state.he_results = None; st.rerun()

    if run_he_btn and api_key:
        client  = Groq(api_key=api_key)
        subset  = [p for p in PROBLEMS if p["difficulty"]=="easy"] if run_subset else PROBLEMS
        total_p = len(subset)

        st.info(f"Running {total_p} problems × 2 (agent + baseline) = {total_p*2} total LLM evaluations. This takes a few minutes.")
        prog  = st.progress(0.0, text="Starting…")
        table = st.empty()
        rows  = []

        def on_progress(i, total, pid):
            prog.progress(i/total, text=f"Problem {i}/{total} — {pid}")

        with st.spinner("Evaluating…"):
            results = evaluate_all(subset, client, model,
                max_retries=int(max_retries), progress_cb=on_progress)

        prog.empty()
        st.session_state.he_results = results

    # Show results
    if st.session_state.he_results:
        r = st.session_state.he_results

        # ── Top-line scores ───────────────────────────────────
        st.divider()
        st.subheader("📊 Results")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Agent pass@1",    f"{r['agent']['pass_at_1']}%",
            delta=f"+{r['improvement_pct']}% vs baseline",
            delta_color="normal" if r['improvement_pct']>=0 else "inverse")
        c2.metric("Baseline pass@1", f"{r['baseline']['pass_at_1']}%")
        c3.metric("Agent avg attempts", r['agent']['avg_attempts'])
        c4.metric("Problems run", r['total_problems'])

        # ── By difficulty ─────────────────────────────────────
        st.divider()
        st.subheader("By difficulty")
        diff_cols = st.columns(3)
        for i, diff in enumerate(["easy","medium","hard"]):
            ag = r["agent"]["by_difficulty"].get(diff)
            bl = r["baseline"]["by_difficulty"].get(diff)
            if ag and bl:
                with diff_cols[i]:
                    label = {"easy":"🟢 Easy","medium":"🟡 Medium","hard":"🔴 Hard"}[diff]
                    st.markdown(f"**{label}**")
                    st.metric("Agent",    f"{ag['pass']}/{ag['total']}  ({ag['pct']}%)")
                    st.metric("Baseline", f"{bl['pass']}/{bl['total']}  ({bl['pct']}%)")

        # ── Per-problem table ─────────────────────────────────
        st.divider()
        st.subheader("Per-problem breakdown")
        agent_map    = {r["problem_id"]: r for r in r["agent_results"]}
        baseline_map = {r["problem_id"]: r for r in r["baseline_results"]}

        header = st.columns([1,2,1,1,1,1])
        for h,t in zip(header,["ID","Function","Difficulty","Agent","Baseline","Attempts"]):
            h.markdown(f"**{t}**")

        for p in (PROBLEMS if not run_subset else [p for p in PROBLEMS if p["difficulty"]=="easy"]):
            ag = agent_map.get(p["id"])
            bl = baseline_map.get(p["id"])
            if not ag: continue
            cols = st.columns([1,2,1,1,1,1])
            cols[0].caption(p["id"])
            cols[1].caption(f"`{p['entry_point']}`")
            cols[2].caption(p["difficulty"])
            cols[3].markdown("✅" if ag["passed"] else "❌")
            cols[4].markdown("✅" if bl["passed"] else "❌")
            cols[5].caption(str(ag["attempts"]))

            # Expandable detail
            if not ag["passed"] and ag.get("error"):
                with st.expander(f"Agent error for {p['id']}", expanded=False):
                    st.code(ag["error"], language="bash")

        # ── Resume-ready summary ──────────────────────────────
        st.divider()
        st.subheader("📄 Resume-ready summary")
        st.success(
            f"Self-Improving Code Agent achieved **{r['agent']['pass_at_1']}% pass@1** on HumanEval "
            f"vs **{r['baseline']['pass_at_1']}% baseline** (plain {model}, single call) — "
            f"a **+{r['improvement_pct']}% improvement** across {r['total_problems']} problems. "
            f"Average {r['agent']['avg_attempts']} fix attempts per problem."
        )
        st.caption("Copy this directly into your README and resume Projects section.")
