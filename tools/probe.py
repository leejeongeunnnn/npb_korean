import requests, json
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
for q in ["慶應義塾大学", "青森山田高校", "白鴎大学", "つくば秀英高校", "社高校", "大阪桐蔭高校", "早稲田実業高校", "東海大相模高校", "福岡工大城東高校", "九州産業大学"]:
    for tl in ["en", "ko"]:
        r = requests.post("https://translate.googleapis.com/translate_a/single",
                          params=[("client", "gtx"), ("sl", "ja"), ("tl", tl), ("dt", "t"), ("dt", "rm")], data={"q": q}, headers=H, timeout=10)
        print(q, tl, r.status_code, json.dumps(r.json()[0], ensure_ascii=False)[:300])
