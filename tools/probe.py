import requests, json, time
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
URL = "https://translate.googleapis.com/translate_a/single"
for q in ["慶應義塾大学", "青森山田高校", "白鴎大学", "つくば秀英高校", "社高校", "大阪桐蔭高校", "東海大相模高校", "福岡工大城東高校"]:
    for method in ["get", "post"]:
        p = [("client", "gtx"), ("sl", "ja"), ("tl", "en"), ("dt", "t"), ("dt", "rm")]
        try:
            r = requests.get(URL, params=p + [("q", q)], headers=H, timeout=10) if method == "get" else requests.post(URL, params=p, data={"q": q}, headers=H, timeout=10)
            body = r.text
            try:
                print(q, method, r.status_code, json.dumps(r.json()[0], ensure_ascii=False)[:260])
            except Exception:
                print(q, method, r.status_code, "NONJSON", body[:200].replace("\n", " "))
        except Exception as e:
            print(q, method, "ERR", e)
        time.sleep(1)
