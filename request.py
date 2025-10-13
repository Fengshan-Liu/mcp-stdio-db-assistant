import requests

print("欢迎使用消息客户端！输入消息并回车发送（输入 'quit' 退出）")

while True:
    # 在终端实时输入消息
    user_input = input("\n 请输入消息: ")

    # 输入 'quit' 退出循环
    if user_input.lower() == 'quit':
        print(" 退出客户端，再见！")
        break

    # 发送 POST 请求到 FastAPI
    response = requests.post(
        "http://localhost:8000/chat/",
        json={"message": user_input}  # 把输入的内容作为 message 发送
    )
    if response.status_code == 200:
        result = response.json()
        print(f"返回结果:, {result}")
    else:
        print("error")    