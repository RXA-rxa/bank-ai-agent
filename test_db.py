import bank_agent as ba
import db

print("转账前余额:", db.get_balance())
ba.run("帮我给妈妈转200块", auto_confirm=True)
print("转账后余额:", db.get_balance())

print("\n===== 最近交易流水 =====")
for t in db.get_recent_transactions(5):
    print(t)

print("\n===== 最近审计日志 =====")
for a in db.get_recent_audit(5):
    print(a["time"], "|", a["intent"], "|", a["gate"])
