# -*- coding: utf-8 -*-
"""
일본어 가나(히라가나/가타카나) → 한글 표기 변환.
국립국어원 외래어 표기법(일본어)을 따른다.
  - カ·タ행은 어두에서 예사소리(가, 다), 어중·어말에서 거센소리(카, 타)
  - ツ → 쓰, ン → 받침 ㄴ, ッ → 받침 ㅅ
  - 장음은 표기하지 않음 (とうきょう → 도쿄, おおた → 오타)
예) いわざき・すぐる → 이와자키 스구루
"""

# 초성 인덱스
CHO = {"": 11, "ㄱ": 0, "ㄲ": 1, "ㄴ": 2, "ㄷ": 3, "ㄸ": 4, "ㄹ": 5, "ㅁ": 6, "ㅂ": 7, "ㅃ": 8,
       "ㅅ": 9, "ㅆ": 10, "ㅇ": 11, "ㅈ": 12, "ㅉ": 13, "ㅊ": 14, "ㅋ": 15, "ㅌ": 16, "ㅍ": 17, "ㅎ": 18}
JUNG = {"ㅏ": 0, "ㅐ": 1, "ㅑ": 2, "ㅒ": 3, "ㅓ": 4, "ㅔ": 5, "ㅕ": 6, "ㅖ": 7, "ㅗ": 8, "ㅘ": 9, "ㅙ": 10,
        "ㅚ": 11, "ㅛ": 12, "ㅜ": 13, "ㅝ": 14, "ㅞ": 15, "ㅟ": 16, "ㅠ": 17, "ㅡ": 18, "ㅢ": 19, "ㅣ": 20}
JONG_N, JONG_S = 4, 19

V = {"a": "ㅏ", "i": "ㅣ", "u": "ㅜ", "e": "ㅔ", "o": "ㅗ", "ya": "ㅑ", "yu": "ㅠ", "yo": "ㅛ",
     "wa": "ㅘ", "wi": "ㅟ", "we": "ㅞ", "wo": "ㅝ", "ye": "ㅖ"}

# 가나 → (자음 종류, 모음)   자음 종류 'K'/'T'/'C'는 위치에 따라 달라짐
BASE = {
    "あ": ("", "a"), "い": ("", "i"), "う": ("", "u"), "え": ("", "e"), "お": ("", "o"),
    "か": ("K", "a"), "き": ("K", "i"), "く": ("K", "u"), "け": ("K", "e"), "こ": ("K", "o"),
    "が": ("ㄱ", "a"), "ぎ": ("ㄱ", "i"), "ぐ": ("ㄱ", "u"), "げ": ("ㄱ", "e"), "ご": ("ㄱ", "o"),
    "さ": ("ㅅ", "a"), "し": ("ㅅ", "i"), "す": ("ㅅ", "u_"), "せ": ("ㅅ", "e"), "そ": ("ㅅ", "o"),
    "ざ": ("ㅈ", "a"), "じ": ("ㅈ", "i"), "ず": ("ㅈ", "u_"), "ぜ": ("ㅈ", "e"), "ぞ": ("ㅈ", "o"),
    "た": ("T", "a"), "ち": ("C", "i"), "つ": ("ㅆ", "u_"), "て": ("T", "e"), "と": ("T", "o"),
    "だ": ("ㄷ", "a"), "ぢ": ("ㅈ", "i"), "づ": ("ㅈ", "u_"), "で": ("ㄷ", "e"), "ど": ("ㄷ", "o"),
    "な": ("ㄴ", "a"), "に": ("ㄴ", "i"), "ぬ": ("ㄴ", "u"), "ね": ("ㄴ", "e"), "の": ("ㄴ", "o"),
    "は": ("ㅎ", "a"), "ひ": ("ㅎ", "i"), "ふ": ("ㅎ", "u"), "へ": ("ㅎ", "e"), "ほ": ("ㅎ", "o"),
    "ば": ("ㅂ", "a"), "び": ("ㅂ", "i"), "ぶ": ("ㅂ", "u"), "べ": ("ㅂ", "e"), "ぼ": ("ㅂ", "o"),
    "ぱ": ("ㅍ", "a"), "ぴ": ("ㅍ", "i"), "ぷ": ("ㅍ", "u"), "ぺ": ("ㅍ", "e"), "ぽ": ("ㅍ", "o"),
    "ま": ("ㅁ", "a"), "み": ("ㅁ", "i"), "む": ("ㅁ", "u"), "め": ("ㅁ", "e"), "も": ("ㅁ", "o"),
    "や": ("", "ya"), "ゆ": ("", "yu"), "よ": ("", "yo"),
    "ら": ("ㄹ", "a"), "り": ("ㄹ", "i"), "る": ("ㄹ", "u"), "れ": ("ㄹ", "e"), "ろ": ("ㄹ", "o"),
    "わ": ("", "wa"), "ゐ": ("", "i"), "ゑ": ("", "e"), "を": ("", "o"),
    "ゔ": ("ㅂ", "u"),
}
SMALL_Y = {"ゃ": "a", "ゅ": "u", "ょ": "o"}
SMALL_V = {"ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o"}


def _kata_to_hira(s):
    out = []
    for ch in s:
        o = ord(ch)
        if 0x30A1 <= o <= 0x30F6:
            out.append(chr(o - 0x60))
        elif ch == "ヴ":
            out.append("ゔ")
        else:
            out.append(ch)
    return "".join(out)


def _resolve(cons, initial):
    if cons == "K":
        return "ㄱ" if initial else "ㅋ"
    if cons == "T":
        return "ㄷ" if initial else "ㅌ"
    if cons == "C":
        return "ㅈ" if initial else "ㅊ"
    return cons


def _compose(cho, jung, jong=0):
    return chr(0xAC00 + (CHO[cho] * 21 + JUNG[jung]) * 28 + jong)


def _word(w):
    """한 단어(성 또는 이름) 변환."""
    w = _kata_to_hira(w)
    syl = []          # [초성, 중성, 종성]
    prev_vowel = ""
    i = 0
    while i < len(w):
        ch = w[i]
        nxt = w[i + 1] if i + 1 < len(w) else ""
        initial = len(syl) == 0
        if ch in ("ん",):
            if syl:
                syl[-1][2] = JONG_N
            else:
                syl.append(["ㅇ", "ㅡ", JONG_N])
            i += 1; prev_vowel = ""; continue
        if ch == "っ":
            if syl:
                syl[-1][2] = JONG_S
            i += 1; continue
        if ch in ("ー", "－", "-"):
            i += 1; continue            # 장음 표기 안 함
        if ch not in BASE:
            if ch in SMALL_V and syl:   # 단독 소문자 모음은 앞 음절에 흡수
                i += 1; continue
            i += 1; continue
        cons, vow = BASE[ch]

        # 요음 (きゃ, しゅ, ちょ ...)
        if nxt in SMALL_Y and vow == "i":
            v = SMALL_Y[nxt]
            if cons in ("ㅅ", "ㅈ", "C", "ㅆ"):
                vow = {"a": "a", "u": "u_", "o": "o"}[v]   # 샤·슈·쇼 / 자·주·조 / 차·추·초
                vk = {"a": "ㅑ" if cons == "ㅅ" else "ㅏ", "u_": "ㅠ" if cons == "ㅅ" else "ㅜ", "o": "ㅛ" if cons == "ㅅ" else "ㅗ"}[vow]
                syl.append([_resolve(cons, initial), vk, 0])
            else:
                syl.append([_resolve(cons, initial) or "ㅇ", V["y" + v], 0])
            prev_vowel = v; i += 2; continue

        # 외래어 소문자 모음 조합 (ティ, ファ, ウィ, デュ, シェ ...)
        if nxt in SMALL_V:
            sv = SMALL_V[nxt]
            if ch in ("う",) :
                syl.append(["ㅇ", V.get("w" + sv, "ㅜ"), 0])
            elif ch in ("ふ",):
                syl.append(["ㅍ", V[sv], 0])
            elif ch in ("ゔ",):
                syl.append(["ㅂ", V[sv], 0])
            elif ch in ("て", "で"):
                syl.append([("ㅌ" if ch == "て" else "ㄷ"), V[sv] if sv != "u" else "ㅜ", 0])
            elif ch in ("と", "ど"):
                syl.append([("ㅌ" if ch == "と" else "ㄷ"), V[sv] if sv != "u" else "ㅜ", 0])
            elif ch in ("し", "じ", "ち"):
                c = {"し": "ㅅ", "じ": "ㅈ", "ち": "ㅊ"}[ch]
                syl.append([c, "ㅖ" if (sv == "e" and ch == "し") else V[sv], 0])
            elif ch == "い" and sv == "e":
                syl.append(["ㅇ", "ㅖ", 0])
            else:
                syl.append([_resolve(cons, initial) or "ㅇ", V[sv], 0])
            prev_vowel = sv; i += 2; continue
        # デュ/テュ (て/で + ゅ)
        if nxt == "ゅ" and ch in ("て", "で"):
            syl.append([("ㅌ" if ch == "て" else "ㄷ"), "ㅠ", 0]); i += 2; prev_vowel = "u"; continue

        # 장모음 생략: お段+う/お, う段+う, え段+え
        base_v = vow.rstrip("_")
        if ch == "う" and prev_vowel in ("o", "u"):
            i += 1; continue
        if ch == "お" and prev_vowel == "o":
            i += 1; continue

        c = _resolve(cons, initial) or "ㅇ"
        if vow == "u_":
            jung = "ㅡ" if c in ("ㅅ", "ㅈ", "ㅆ") else "ㅜ"
        else:
            jung = V[vow]
        syl.append([c, jung, 0])
        prev_vowel = base_v[-1] if base_v else ""
        i += 1
    return "".join(_compose(c, j, k) for c, j, k in syl)


def kana_to_hangul(kana):
    """'いわざき・すぐる' → '이와자키 스구루'"""
    if not kana:
        return ""
    import re
    parts = [p for p in re.split(r"[・･\s　/]+", kana.strip()) if p]
    return " ".join(_word(p) for p in parts)


if __name__ == "__main__":
    tests = ["いわざき・すぐる", "さとう・てるあき", "むらかみ・しょうき", "ちかもと・こうじ", "とうきょう",
             "おおたに・しょうへい", "たなか・まさひろ", "デュプランティエ", "ウィーラー", "ファーガソン",
             "きくち・ゆうせい", "ちゃ", "いっしき", "しんのすけ", "ヴィクター", "ティモンズ", "シェパード"]
    for t in tests:
        print(t, "→", kana_to_hangul(t))
