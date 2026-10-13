import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "fugashi", "unidic-lite", "pykakasi"], check=False)
from fugashi import Tagger
import pykakasi
tg = Tagger(); kk = pykakasi.kakasi()
def mecab(s):
    out = []
    for w in tg(s):
        f = w.feature
        kana = getattr(f, "kana", None) or getattr(f, "pron", None)
        out.append(f"{w.surface}/{kana}")
    return " ".join(out)
names = ["慶應義塾","慶応義塾","白鴎","社","つくば秀英","大阪桐蔭","青森山田","東海大相模","福岡工大城東","智辯和歌山","履正社","横浜商科","国士舘",
         "亜細亜","駒澤","法政","明治","立教","中京","帝京","花咲徳栄","仙台育英","健大高崎","日大三","東北福祉","佐久長聖","報徳学園","沖縄尚学",
         "九州国際大付","明徳義塾","創価","八戸学院光星","聖光学院","敦賀気比","神村学園","作新学院","天理","常総学院","浦和学院","東洋","上武","星槎道都"]
for n in names:
    print(n, "| mecab:", mecab(n), "| kakasi:", "".join(x["hira"] for x in kk.convert(n)))
