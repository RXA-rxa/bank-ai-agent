"""
银行 AI 智能体 - Streamlit 界面 v5（产品级）
"""
import json
import pandas as pd
import streamlit as st
import bank_agent as ba
import db

st.set_page_config(page_title="智汇银行 AI 助手", page_icon="🏦", layout="wide")
db.init_db()

# ---------- 会话状态 ----------
if "history" not in st.session_state:
    st.session_state.history = []
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

# ---------- Agent 核心 ----------
def run_agent(user_text, auto_confirm=True):
    steps = []
    inj = ba.sanitize(user_text)
    if inj:
        db.log_audit(user_text, "-", "拦截", "-", inj)
        return inj, [("🛡️ 安全拦截", inj, "error")]

    allowed = set()
    history = db.get_recent_chat(10)
    messages = [{"role": "system", "content": ba.SYSTEM_PROMPT}] + history + [
        {"role": "user", "content": user_text}]
    for _ in range(6):
        resp = ba.client.chat.completions.create(model=ba.MODEL, messages=messages, tools=ba.TOOLS)
        msg = resp.choices[0].message
        messages.append(msg)
        if not msg.tool_calls:
            reply = msg.content or "（无回复）"
            sus = ba.hallucination_check(reply, allowed)
            if sus:
                reply += f"\n\n⚠️ [系统] 可疑数字 {sus}，请核实。"
                db.log_audit(user_text, "幻觉检查", "可疑数字", "-", str(sus))
            db.save_chat("user", user_text)
            db.save_chat("assistant", reply)
            return reply, steps
        for call in msg.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments)
            level, note = ba.safety_gate(name, args)
            if level == "reject":
                result = {"ok": False, "msg": note}; color = "error"
            elif level == "confirm":
                result = {"ok": False, "msg": "演示模式需确认"} if not auto_confirm else ba.TOOL_MAP[name](args)
                color = "warning"
            else:
                result = ba.TOOL_MAP[name](args); color = "success"
            ba._extract_numbers(result, allowed)
            db.log_audit(user_text, f"{name}({args})", note, name, str(result))
            steps.append((f"🔧 {name}", f"{note}\n→ {result.get('msg', result)}", color))
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, ensure_ascii=False)})
    return "（达到最大步数）", steps

# ============ 侧边栏：登录 + 风控 ============
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/bank.png", width=60)
    st.title("智汇银行")
    st.caption("AI Banking Agent · v5")
    st.divider()
    st.subheader("👤 用户身份")
    name = st.text_input("你的名字", value=st.session_state.user_name, placeholder="输入姓名，如：张三")
    if name:
        st.session_state.user_name = name
        st.success(f"已登录：{name}")
    st.divider()
    st.subheader("🛡️ 风控概览")
    all_logs = db.get_recent_audit(100)
    blocked = sum(1 for l in all_logs if "拒绝" in l["gate"] or "拦截" in l["gate"])
    confirmed = sum(1 for l in all_logs if "确认" in l["gate"])
    st.metric("今日拦截", blocked)
    st.metric("需二次确认", confirmed)

# ============ 顶部账户卡片 ============
st.title(f"🏦 {st.session_state.user_name or '尊敬的客户'}，您好")
c1, c2, c3, c4 = st.columns(4)
c1.metric("账户余额", f"¥{db.get_balance():,.2f}")
txs = db.get_recent_transactions(50)
c2.metric("累计交易", len(txs))
subs = [s for s in db.get_subscriptions() if s["active"]]
c3.metric("生效自动续费", len(subs))
contacts = db.conn().execute("SELECT COUNT(*) n FROM contacts").fetchone()["n"]
c4.metric("已登记收款人", contacts)
st.divider()

# ============ 主区：聊天 + 决策 ============
left, right = st.columns([2, 1.3])

with left:
    st.subheader("💬 智能助手")
    for m in st.session_state.history:
        with st.chat_message(m["role"]):
            st.write(m["content"])
    user = st.chat_input("试试：把视频会员自动续费关掉，省的25块买成货币基金")
    if user:
        st.session_state.history.append({"role": "user", "content": user})
        with st.chat_message("user"): st.write(user)
        with st.chat_message("assistant"):
            with st.spinner("AI 思考中…"):
                reply, steps = run_agent(user)
            st.write(reply)
            if steps:
                with st.expander("🔍 本次决策过程"):
                    for title, detail, color in steps:
                        getattr(st, color)(f"**{title}**\n{detail}")
        st.session_state.history.append({"role": "assistant", "content": reply})
        st.rerun()

with right:
    st.subheader("🧾 最近交易")
    if txs:
        for t in txs[:6]:
            st.write(f"**{t['type']}** · {t['detail']}  `¥{t['amount']}`")
    else:
        st.caption("暂无交易")
    st.divider()
    st.subheader("🛡️ 审计日志")
    logs = db.get_recent_audit(5)
    for l in reversed(logs):
        if "拒绝" in l["gate"] or "拦截" in l["gate"]:
            st.error(f"`{l['time'][11:]}` {l['intent']}")
        elif "确认" in l["gate"]:
            st.warning(f"`{l['time'][11:]}` {l['intent']}")
        else:
            st.info(f"`{l['time'][11:]}` {l['intent']}")

# ============ 底部：账单可视化 ============
st.divider()
st.subheader("📊 9月消费分析")
bills = db.get_bills("2026-09")
if bills:
    df = pd.DataFrame(bills)
    bc1, bc2 = st.columns(2)
    with bc1:
        st.bar_chart(df.set_index("item")["amount"])
    with bc2:
        st.dataframe(df[["date", "item", "amount"]], use_container_width=True)
