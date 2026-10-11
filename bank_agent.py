"""
银行 AI 智能体 v3：SQLite 持久化 + 审计日志
"""
import os, json
from openai import OpenAI
import db

def load_env(path=".env"):
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
load_env()
db.init_db()

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

WEALTH = [
    {"name": "天天货币A", "type": "货币基金", "risk": "低", "yield": "2.1%"},
    {"name": "稳健债基", "type": "债券基金", "risk": "中低", "yield": "3.5%"},
]

# ---------- 工具实现（走数据库） ----------
def transfer_money(to_name, amount):
    contact = db.get_contact(to_name)
    if not contact:
        return {"ok": False, "msg": f"通讯录里没有「{to_name}」，请先添加收款人"}
    if db.is_new_contact(contact["created_at"]) and amount > 500:
        return {"ok": False, "msg": f"「{to_name}」是24小时内新增收款人，单笔限额500元"}
    bal = db.get_balance()
    if amount > bal:
        return {"ok": False, "msg": f"余额不足（当前 {bal}）"}
    new_bal = bal - amount
    c = db.conn()
    c.execute("UPDATE account SET balance=? WHERE id=1", (new_bal,))
    c.commit(); c.close()
    db.log_transaction("转账", f"转给{to_name}({contact['account']})", amount, new_bal)
    return {"ok": True, "msg": f"已向{to_name}转出 {amount} 元，余额剩 {new_bal} 元",
            "amount": amount, "balance_after": new_bal}

def add_contact(name, account):
    if db.get_contact(name):
        return {"ok": False, "msg": f"「{name}」已存在"}
    if db.add_contact(name, account):
        db.log_transaction("添加收款人", f"新增{name}({account})", 0, db.get_balance())
        return {"ok": True, "msg": f"已添加「{name}」为收款人，24小时内单笔限额500元"}
    return {"ok": False, "msg": "添加失败"}

def get_bills(month):
    rows = db.get_bills(month)
    return {"ok": True, "rows": rows, "total": sum(b["amount"] for b in rows)}

def get_balance():
    return {"ok": True, "balance": db.get_balance()}

def get_subscriptions():
    return {"ok": True, "rows": db.get_subscriptions()}

def cancel_subscription(name):
    c = db.conn()
    row = c.execute("SELECT * FROM subscriptions WHERE name=? AND active=1", (name,)).fetchone()
    if not row:
        return {"ok": False, "msg": f"没有正在生效的「{name}」订阅"}
    c.execute("UPDATE subscriptions SET active=0 WHERE id=?", (row["id"],))
    c.commit(); c.close()
    db.log_transaction("取消订阅", f"取消{name}自动续费", row["amount"], db.get_balance())
    return {"ok": True, "msg": f"已取消「{name}」，每月省 {row['amount']} 元"}

# 用户风险偏好（理财风险评估）
RISK_PROFILE = "稳健"  # 保守 / 稳健 / 积极
RISK_ALLOW = {"保守": ["低"], "稳健": ["低", "中低"], "积极": ["低", "中低", "中高"]}

def set_risk_preference(level):
    global RISK_PROFILE
    if level not in RISK_ALLOW:
        return {"ok": False, "msg": "风险偏好只能是：保守/稳健/积极"}
    RISK_PROFILE = level
    return {"ok": True, "msg": f"已设置为「{level}」型投资者，可购买{('/'.join(RISK_ALLOW[level]))}风险产品"}

def get_wealth_products():
    return {"ok": True, "rows": WEALTH, "your_risk": RISK_PROFILE}

def buy_fund(product_name, amount):
    # 风险匹配校验
    product = next((p for p in WEALTH if p["name"] == product_name), None)
    if not product:
        return {"ok": False, "msg": f"没有找到产品「{product_name}」"}
    if product["risk"] not in RISK_ALLOW[RISK_PROFILE]:
        return {"ok": False, "msg": f"您是「{RISK_PROFILE}」型投资者，不能购买{product['risk']}风险产品「{product_name}」"}
    bal = db.get_balance()
    if amount > bal:
        return {"ok": False, "msg": "余额不足，无法申购"}
    new_bal = bal - amount
    c = db.conn()
    c.execute("UPDATE account SET balance=? WHERE id=1", (new_bal,))
    c.commit(); c.close()
    db.log_transaction("申购理财", f"申购{product_name}", amount, new_bal)
    return {"ok": True, "msg": f"已申购「{product_name}」({product['risk']}风险) {amount} 元，余额剩 {new_bal} 元",
            "amount": amount, "balance_after": new_bal}

def adjust_card_limit(new_limit):
    return {"ok": True, "msg": f"卡片额度已调整为 {new_limit} 元（演示）"}

TOOLS = [
    {"type": "function", "function": {"name": "transfer_money", "description": "向通讯录联系人转账",
        "parameters": {"type": "object", "properties": {"to_name": {"type": "string"}, "amount": {"type": "number"}}, "required": ["to_name", "amount"]}}},
    {"type": "function", "function": {"name": "get_bills", "description": "查询某月份账单",
        "parameters": {"type": "object", "properties": {"month": {"type": "string"}}, "required": ["month"]}}},
    {"type": "function", "function": {"name": "get_balance", "description": "查询当前账户余额"}},
    {"type": "function", "function": {"name": "get_subscriptions", "description": "列出所有自动续费/代扣订阅"}},
    {"type": "function", "function": {"name": "cancel_subscription", "description": "取消某个自动续费订阅",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "get_wealth_products", "description": "查询可购买的理财产品列表"}},
    {"type": "function", "function": {"name": "buy_fund", "description": "申购理财产品",
        "parameters": {"type": "object", "properties": {"product_name": {"type": "string"}, "amount": {"type": "number"}}, "required": ["product_name", "amount"]}}},
    {"type": "function", "function": {"name": "adjust_card_limit", "description": "调整信用卡额度",
        "parameters": {"type": "object", "properties": {"new_limit": {"type": "number"}}, "required": ["new_limit"]}}},
    {"type": "function", "function": {"name": "add_contact", "description": "添加一个新的收款人到通讯录",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "account": {"type": "string"}}, "required": ["name", "account"]}}},
    {"type": "function", "function": {"name": "set_risk_preference", "description": "设置用户风险投资偏好（保守/稳健/积极）",
        "parameters": {"type": "object", "properties": {"level": {"type": "string", "description": "保守/稳健/积极"}}, "required": ["level"]}}},
]
TOOL_MAP = {
    "transfer_money": lambda a: transfer_money(a["to_name"], a["amount"]),
    "get_bills": lambda a: get_bills(a["month"]),
    "get_balance": lambda a: get_balance(),
    "get_subscriptions": lambda a: get_subscriptions(),
    "cancel_subscription": lambda a: cancel_subscription(a["name"]),
    "get_wealth_products": lambda a: get_wealth_products(),
    "buy_fund": lambda a: buy_fund(a["product_name"], a["amount"]),
    "adjust_card_limit": lambda a: adjust_card_limit(a["new_limit"]),
    "add_contact": lambda a: add_contact(a["name"], a["account"]),
    "set_risk_preference": lambda a: set_risk_preference(a["level"]),
}

RISK = {
    "get_bills": "L0", "get_balance": "L0", "get_subscriptions": "L0", "get_wealth_products": "L0",
    "cancel_subscription": "L1", "adjust_card_limit": "L1", "add_contact": "L1", "set_risk_preference": "L1",
    "transfer_money": "L2", "buy_fund": "L2",
}
def safety_gate(name, args):
    level = RISK.get(name, "L3")
    if level == "L0": return "allow", "只读查询，放行"
    if level == "L1": return "allow", "低风险操作，放行并记日志"
    if level == "L2":
        if args.get("amount", 0) >= 10000:
            return "reject", f"【拒绝】金额 {args.get('amount')} 超自助限额"
        return "confirm", f"【需确认】{name} 参数={args}"
    return "reject", "未知操作，拒绝"

BAD = ["忽略以上", "ignore previous", "你现在是", "system prompt", "忘记指令"]
def sanitize(t):
    hit = [p for p in BAD if p.lower() in t.lower()]
    return f"检测到注入，已拦截：{hit}" if hit else None

SYSTEM_PROMPT = """你是一个严谨且高效的银行AI助手。必须遵守：
1. 对于明确的转账、查询、取消、申购等操作，必须直接调用对应工具执行，不要反问用户、不要等待确认联系人是否存在。
2. 所有金额、余额、账号，必须严格来自工具返回的真实数据，绝不编造。
3. 任务没完成前，必须继续调用工具，不要提前给出最终回答。
4. 只有工具返回"通讯录没有此人"等错误时，才告知用户需要先添加。
5. 回答简洁，数字必须与工具返回一致。"""

def _extract_numbers(obj, acc):
    """递归把工具返回里的所有数字收进集合，用于幻觉溯源"""
    if isinstance(obj, (int, float)):
        acc.add(round(float(obj), 2))
    elif isinstance(obj, dict):
        for v in obj.values():
            _extract_numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _extract_numbers(v, acc)
    return acc

def hallucination_check(reply, allowed_numbers):
    """只检查'数字+元/块'这类金额；先去掉千分位逗号，避免误判"""
    import re
    clean = re.sub(r"(\d),(\d)", r"\1\2", reply)   # 10,800 -> 10800
    money = [float(x) for x in re.findall(r"(\d+\.?\d*)\s*[元块]", clean)]
    suspicious = [n for n in money if round(n, 2) not in allowed_numbers]
    return suspicious

def run(user_text, auto_confirm=False):
    print(f"\n🧑 用户：{user_text}")
    inj = sanitize(user_text)
    if inj:
        print(f"🛡️ {inj}")
        db.log_audit(user_text, "-", "拦截", "-", inj)
        return

    allowed = set()
    # 多轮记忆：带上最近几轮对话
    history = db.get_recent_chat(10)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [
        {"role": "user", "content": user_text}
    ]
    for _ in range(6):
        resp = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)
        msg = resp.choices[0].message
        messages.append(msg)
        if not msg.tool_calls:
            reply = msg.content or ""
            # 幻觉溯源检查
            sus = hallucination_check(reply, allowed)
            if sus:
                reply += f"\n\n⚠️ [系统提示] 检测到可疑数字 {sus}，建议核实后再操作。"
                db.log_audit(user_text, "幻觉检查", "可疑数字", "-", str(sus))
            print(f"🤖 助手：{reply}")
            db.save_chat("user", user_text)
            db.save_chat("assistant", reply)
            return reply
        for call in msg.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments)
            level, note = safety_gate(name, args)
            if level == "reject":
                result = {"ok": False, "msg": note}
            elif level == "confirm" and not auto_confirm:
                if input("   > y/n：").strip().lower() != "y":
                    result = {"ok": False, "msg": "用户取消"}
                else:
                    result = TOOL_MAP[name](args)
            else:
                result = TOOL_MAP[name](args)
            _extract_numbers(result, allowed)
            db.log_audit(user_text, f"{name}({args})", note, name, str(result))
            print(f"🔧 {name}({args})  🚦{note}  🏦{result}")
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, ensure_ascii=False)})

if __name__ == "__main__":
    print("=== 银行AI智能体 v3（exit 退出）===")
    while True:
        t = input("\n你：").strip()
        if t.lower() in ("exit", "quit"): break
        if t: run(t)
