from openai import OpenAI
import random

# Khởi tạo client (sử dụng API key từ biến môi trường OPENAI_API_KEY)
client = OpenAI()

context_good = [{"role": "system", "content": "you're Alph and you only tell the truth"}]
context_bad  = [{"role": "system", "content": "you're Ralph and you only tell lies"}]

def call(ctx):
    return client.chat.completions.create(
        model="gpt-4o-mini",  # hoặc gpt-5 nếu tài khoản bạn có quyền
        messages=ctx
    )

def process(line):
    context_good.append({"role": "user", "content": line})
    context_bad.append({"role": "user", "content": line})

    if random.choice([True, False]):
        response = call(context_good)
    else:
        response = call(context_bad)

    reply = response.choices[0].message.content
    context_good.append({"role": "assistant", "content": reply})
    context_bad.append({"role": "assistant", "content": reply})
    return reply

print(process("Are you real?"))
