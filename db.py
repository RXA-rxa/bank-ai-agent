"""
数据库层：SQLite 持久化 + 审计日志
- account    账户余额
- bills      账单
- subscriptions  订阅/代扣
- transactions   交易流水
- audit_logs     每一步 agent 操作审计
"""
import os, sqlite3, datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "bank.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    """建表 + 灌入种子数据（只跑一次）"""
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY, balance REAL);
    CREATE TABLE IF NOT EXISTS contacts(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, account TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS bills(id INTEGER PRIMARY KEY AUTOINCREMENT, month TEXT, item TEXT, amount REAL, date TEXT);
    CREATE TABLE IF NOT EXISTS subscriptions(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, amount REAL, cycle TEXT, active INTEGER);
    CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, type TEXT, detail TEXT, amount REAL, balance_after REAL);
    CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, user_text TEXT, intent TEXT, gate TEXT, action TEXT, result TEXT);
    CREATE TABLE IF NOT EXISTS chat_history(id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, role TEXT, content TEXT);
    """)
    # 种子数据
    if c.execute("SELECT COUNT(*) FROM account").fetchone()[0] == 0:
        c.execute("INSERT INTO account(balance) VALUES(11300)")
    if c.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 0:
        c.executemany("INSERT INTO contacts(name,account,created_at) VALUES(?,?,?)", [
            ("妈妈", "6222****8888", "2026-01-01 09:00:00"),
            ("老张", "6222****1234", "2026-01-01 09:00:00"),
        ])
    if c.execute("SELECT COUNT(*) FROM bills").fetchone()[0] == 0:
        c.executemany("INSERT INTO bills(month,item,amount,date) VALUES(?,?,?,?)", [
            ("2026-09", "视频会员自动续费", 25.0, "2026-09-03"),
            ("2026-09", "超市购物", 320.5, "2026-09-12"),
            ("2026-09", "滴滴打车", 68.0, "2026-09-15"),
        ])
        c.executemany("INSERT INTO subscriptions(name,amount,cycle,active) VALUES(?,?,?,?)", [
            ("视频会员", 25.0, "每月", 1),
            ("音乐App", 15.0, "每月", 1),
            ("云存储", 6.0, "每月", 0),
        ])
    c.commit(); c.close()

# ---------- 联系人 ----------
def get_contact(name):
    r = conn().execute("SELECT * FROM contacts WHERE name=?", (name,)).fetchone()
    return dict(r) if r else None

def add_contact(name, account):
    c = conn()
    try:
        c.execute("INSERT INTO contacts(name,account,created_at) VALUES(?,?,?)",
                  (name, account, now()))
        c.commit()
        ok = True
    except Exception:
        ok = False
    finally:
        c.close()
    return ok

def is_new_contact(created_at):
    """判断是否24小时内新加的联系人"""
    try:
        t = datetime.datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        return (datetime.datetime.now() - t).total_seconds() < 86400
    except Exception:
        return False

# ---------- 读取 ----------
def get_balance():
    return conn().execute("SELECT balance FROM account WHERE id=1").fetchone()[0]

def get_bills(month):
    rows = conn().execute("SELECT * FROM bills WHERE month=?", (month,)).fetchall()
    return [dict(r) for r in rows]

def get_subscriptions():
    return [dict(r) for r in conn().execute("SELECT * FROM subscriptions").fetchall()]

# ---------- 写入（自动记交易流水 + 审计） ----------
def log_transaction(type_, detail, amount, balance_after):
    c = conn()
    c.execute("INSERT INTO transactions(time,type,detail,amount,balance_after) VALUES(?,?,?,?,?)",
              (now(), type_, detail, amount, balance_after))
    c.commit(); c.close()

def log_audit(user_text, intent, gate, action, result):
    c = conn()
    c.execute("INSERT INTO audit_logs(time,user_text,intent,gate,action,result) VALUES(?,?,?,?,?,?)",
              (now(), user_text, intent, gate, action, result))
    c.commit(); c.close()

def get_recent_audit(limit=20):
    c = conn()
    rows = c.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]

def get_recent_transactions(limit=10):
    rows = conn().execute("SELECT * FROM transactions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]

# ---------- 对话历史（多轮记忆） ----------
def save_chat(role, content):
    c = conn()
    c.execute("INSERT INTO chat_history(time,role,content) VALUES(?,?,?)", (now(), role, content))
    c.commit(); c.close()

def get_recent_chat(limit=10):
    rows = conn().execute(
        "SELECT role,content FROM (SELECT * FROM chat_history ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
        (limit,)).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]

def clear_chat():
    c = conn()
    c.execute("DELETE FROM chat_history")
    c.commit(); c.close()

if __name__ == "__main__":
    init_db()
    print("数据库初始化完成：", DB_PATH)
