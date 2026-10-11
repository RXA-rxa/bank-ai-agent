"""重置演示环境：余额调大、清掉测试数据"""
import db

c = db.conn()
# 1. 余额重置为 10 万
c.execute("UPDATE account SET balance=100000 WHERE id=1")
# 2. 清掉测试产生的交易流水、审计日志、对话历史
c.execute("DELETE FROM transactions")
c.execute("DELETE FROM audit_logs")
c.execute("DELETE FROM chat_history")
# 3. 清掉测试加的联系人，只留妈妈、老张
c.execute("DELETE FROM contacts WHERE name NOT IN ('妈妈','老张')")
# 4. 恢复订阅状态（视频会员、音乐App 重新生效）
c.execute("UPDATE subscriptions SET active=1 WHERE name IN ('视频会员','音乐App')")
c.commit(); c.close()

print("演示环境已重置：")
print("  余额:", db.get_balance())
print("  联系人:", [s["name"] for s in db.conn().execute("SELECT name FROM contacts").fetchall()])
print("  生效订阅:", [s["name"] for s in db.get_subscriptions() if s["active"]])
