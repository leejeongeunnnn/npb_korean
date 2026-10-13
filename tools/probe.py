import sys, os, json
sys.path.insert(0, os.getcwd())
import collect_profiles as P
for seg in ["慶應義塾大","青森山田高","白鴎大","つくば秀英高","社高（甲）","大阪桐蔭高","東海大相模高（甲）","福岡工大城東高","智辯和歌山高","履正社高",
            "横浜商科大","国士舘大","亜細亜大","花咲徳栄高","健大高崎高","八戸学院光星高","上武大","星槎道都大","九州国際大付高","東北福祉大","IMG高"]:
    stem, suf, k = P.split_school(seg)
    print(seg, "→", P.school_ko(stem, suf), "(고시엔)" if k else "")
for code in ["hawks", "tigers"]:
    d = json.load(open(f"data/profiles/{code}.json"))
    P.fill_career_ko(d["players"])
    for p in d["players"][:14]:
        print("  ", p["name"], " → ".join(c["ko"] + ("(고시엔)" if c.get("koshien") else "") for c in p["career"]))
