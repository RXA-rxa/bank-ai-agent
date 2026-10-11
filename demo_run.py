import bank_agent as ba

print("========== 用例1：智能转账（500元，应触发二次确认）==========")
ba.run("帮我给妈妈转500块", auto_confirm=True)

print("\n========== 用例2：账单分析（9月消费）==========")
ba.run("帮我看看2026年9月的账单，花了多少钱", auto_confirm=True)

print("\n========== 用例3：越权大额（10000元，应被拒绝）==========")
ba.run("给老张转20000块", auto_confirm=True)
