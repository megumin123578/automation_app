import requests

API_URL = "https://smmstore.pro/api/v2"
API_KEY = '0f06dab474e72deb25b69026871433af'

def api_request(params: dict):
    params["key"] = API_KEY
    response = requests.post(API_URL, data=params, timeout=30)
    response.raise_for_status()
    return response.json()


# # 2) Thêm đơn mới (ví dụ dịch vụ ID = 1, link = “https://…” , số lượng = 1000)
# add_resp = api_request({
#     "action": "add",
#     "service": 1,
#     "link": "https://www.instagram.com/yourpost/",
#     "quantity": 1000
# })
# print("Add order response:", add_resp)

# # 3) Kiểm tra trạng thái đơn
# order_id = add_resp.get("order")
# if order_id:
#     status_resp = api_request({"action": "status", "order": order_id})
#     print("Status:", status_resp)

# 4) Lấy balance
balance_resp = api_request({"action": "balance"})
print("Balance:", balance_resp)
