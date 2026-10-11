# 最小连通性测试：验证 DeepSeek key 是否能用
import os
from openai import OpenAI

# 手动读 .env（不依赖额外库）
def load_env(path=".env"):
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)

resp = client.chat.completions.create(
    model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
    messages=[{"role": "user", "content": "用一句话告诉我你是谁。"}],
)
print("DeepSeek 回复:", resp.choices[0].message.content)
print("连通成功 ✓")
