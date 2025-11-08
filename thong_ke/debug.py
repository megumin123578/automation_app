import re

def extract_phpsessid_dict(cookie_str: str):

    match = re.search(r"(?:^|;\s*)PHPSESSID=([^;]+)", cookie_str, flags=re.IGNORECASE)
    if match:
        phpsessid = match.group(1).strip()
        return {"PHPSESSID": phpsessid}
    else:
        return {"PHPSESSID": None}


# ==== Ví dụ dùng ====
cookie_str = """2da111a6a5b587c2375d81aca01578af7cb71ab21217e58539199d7064581ef0=757133aaabdd65f49bc8dc781ed2055e331b4be3634265019630db0f29c2da67a%3A2%3A%7Bi%3A0%3Bs%3A64%3A%222da111a6a5b587c2375d81aca01578af7cb71ab21217e58539199d7064581ef0%22%3Bi%3A1%3Bs%3A64%3A%22e788c01f5bd98bea27b96b6ca0a9e7c8dad2f088b2f4277f424fb2370bde2643%22%3B%7D; _gcl_au=1.1.1891180875.1760066500; usrtrcng=37d50603f658d03c89a3219d3b4a7a3af649eadd90d0e73fc93bb492b25c6362a%3A2%3A%7Bi%3A0%3Bs%3A8%3A%22usrtrcng%22%3Bi%3A1%3Bs%3A75%3A%22%7B%22first_visit_at%22%3A1760144647%2C%22uuid%22%3A%220d693945-d89d-4820-be33-18b3433b341b%22%7D%22%3B%7D; FooBar=true; PHPSESSID=er9miqb70ooj4bk7iono0cn42l; _identity_user=1a541380a46ed1b896c4e518c280028330745566a30f0f7fd5a2c85b2ddde27ba%3A2%3A%7Bi%3A0%3Bs%3A14%3A%22_identity_user%22%3Bi%3A1%3Bs%3A18%3A%22%5B42838%2C%22%22%2C2592000%5D%22%3B%7D"""

cookies = extract_phpsessid_dict(cookie_str)
print(cookies)
