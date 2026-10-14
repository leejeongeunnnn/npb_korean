import os, requests, sys
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
out = "/tmp/pub"; os.makedirs(out, exist_ok=True)
GIDS=['2021051118', '2021051119', '2021051120', '2021051133', '2021051134', '2021051699', '2021038874', '2021039258', '2021039208', '2021038762', '2021039013', '2021039271', '2021039135', '2021039293', '2021039245', '2021038691', '2021039273', '2021038635', '2021039130', '2021038897']
for g in GIDS:
    for k in ['text']:
        r=requests.get(f'https://baseball.yahoo.co.jp/npb/game/{g}/{k}',headers=H,timeout=20)
        open(f'{out}/{g}_{k}.html','w',encoding='utf-8').write(r.text); print(g,k,r.status_code,len(r.text))
for g in ['2021039486','2021039480']:
    for k in ['top','text']:
        r=requests.get(f'https://baseball.yahoo.co.jp/npb/game/{g}/{k}',headers=H,timeout=20)
        open(f'{out}/today_{g}_{k}.html','w',encoding='utf-8').write(r.text); print(g,k,r.status_code)
