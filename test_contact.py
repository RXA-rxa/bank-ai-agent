import bank_agent as ba
import db

print("===== 1. 添加收款人 小李 =====")
ba.run("帮我把小李加成收款人，账号6222****9999", auto_confirm=True)

print("\n===== 2. 给小李转200（<500，应成功）=====")
ba.run("给小李转200块", auto_confirm=True)

print("\n===== 3. 给小李转600（>500，应被新联系人限额拦住）=====")
ba.run("给小李转600块", auto_confirm=True)

print("\n当前余额:", db.get_balance())
