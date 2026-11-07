"""Idioma de una letra y su romanización, sin internet.

- idioma(): por el tipo de escritura (hiragana/katakana → japonés, hangul → coreano, cirílico → ruso…);
  en alfabeto latino, por palabras comunes de cada idioma.
- romanizar(): coreano (Romanización Revisada), japonés (Hepburn; los kanji se leen con el diccionario de pykakasi),
  cirílico (ruso/ucraniano), griego y, aproximados, árabe, hebreo y tailandés (no escriben las vocales cortas).
  El chino necesita un diccionario que no viene aquí: se deja sin romanizar.
"""
import re
import unicodedata

NOMBRES = {
    "ja": "Japonés", "ko": "Coreano", "zh": "Chino", "ru": "Ruso", "uk": "Ucraniano", "el": "Griego", "ar": "Árabe",
    "he": "Hebreo", "hi": "Hindi", "th": "Tailandés", "es": "Español", "en": "Inglés", "pt": "Portugués",
    "fr": "Francés", "it": "Italiano", "de": "Alemán",
}
ROMANIZABLES = {"ja", "ko", "ru", "uk", "el", "ar", "he", "th"}

_PALABRAS = {
    "es": {"el", "la", "de", "que", "y", "en", "los", "las", "un", "una", "por", "con", "no", "mi", "te", "me", "tu", "es", "lo", "se", "como", "pero", "yo", "amor", "quiero"},
    "en": {"the", "and", "you", "i", "to", "a", "of", "my", "in", "is", "it", "me", "that", "your", "on", "be", "love", "we", "don't", "i'm", "oh", "baby", "can't"},
    "pt": {"o", "a", "de", "que", "e", "do", "da", "em", "um", "uma", "você", "não", "eu", "meu", "minha", "com", "pra", "é", "tô", "coração"},
    "fr": {"le", "la", "les", "de", "et", "je", "tu", "que", "un", "une", "pas", "dans", "est", "mon", "ma", "moi", "toi", "c'est", "nous", "vous"},
    "it": {"il", "la", "di", "che", "e", "un", "una", "non", "per", "mi", "ti", "io", "sono", "del", "della", "amore", "come", "più"},
    "de": {"der", "die", "das", "und", "ich", "du", "nicht", "ist", "ein", "eine", "mit", "mich", "dich", "auf", "wir", "zu", "es", "sie"},
}


def _escritura(ch: str) -> str:
    o = ord(ch)
    if 0x3040 <= o <= 0x30FF or 0x31F0 <= o <= 0x31FF or 0xFF66 <= o <= 0xFF9D:
        return "kana"
    if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF:
        return "han"
    if 0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F:
        return "hangul"
    if 0x0400 <= o <= 0x04FF:
        return "cirilico"
    if 0x0370 <= o <= 0x03FF:
        return "griego"
    if 0x0600 <= o <= 0x06FF:
        return "arabe"
    if 0x0590 <= o <= 0x05FF:
        return "hebreo"
    if 0x0900 <= o <= 0x097F:
        return "devanagari"
    if 0x0E00 <= o <= 0x0E7F:
        return "thai"
    if ch.isalpha():
        return "latino"
    return ""


def idioma(lineas: list[str]) -> str:
    """Código del idioma ("ja", "es"…) o "" si no se sabe."""
    texto = "\n".join(lineas)
    cuenta: dict[str, int] = {}
    for ch in texto:
        e = _escritura(ch)
        if e:
            cuenta[e] = cuenta.get(e, 0) + 1
    if not cuenta:
        return ""
    no_latino = {k: v for k, v in cuenta.items() if k != "latino"}
    # Basta una parte de la letra en otra escritura (las letras de K-pop/J-pop mezclan inglés)
    if no_latino and sum(no_latino.values()) >= 0.15 * sum(cuenta.values()):
        if cuenta.get("kana"):
            return "ja"
        principal = max(no_latino, key=no_latino.get)
        if principal == "cirilico":
            return "uk" if re.search(r"[іїєґІЇЄҐ]", texto) else "ru"
        return {"hangul": "ko", "han": "zh", "griego": "el", "arabe": "ar", "hebreo": "he",
                "devanagari": "hi", "thai": "th"}.get(principal, "")
    palabras = re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", texto.lower())
    if not palabras:
        return ""
    puntos = {cod: sum(p in comunes for p in palabras) for cod, comunes in _PALABRAS.items()}
    mejor = max(puntos, key=puntos.get)
    return mejor if puntos[mejor] >= 3 else ""


# ---------- Coreano (Romanización Revisada, simplificada) ----------
_INICIALES = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]
_VOCALES = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi",
            "yu", "eu", "ui", "i"]
# Final al terminar sílaba / final cuando la sigue una vocal (ㅇ): se "pasa" a la siguiente sílaba
_FINALES = ["", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l", "l", "p", "l", "m", "p", "p", "t", "t",
            "ng", "t", "t", "k", "t", "p", "t"]
_ENLACE = ["", "g", "kk", "gs", "n", "nj", "n", "d", "r", "lg", "lm", "lb", "ls", "lt", "lp", "r", "m", "b", "bs",
           "s", "ss", "ng", "j", "ch", "k", "t", "p", ""]


def _coreano(texto: str) -> str:
    salida = []
    chars = list(texto)
    for i, ch in enumerate(chars):
        o = ord(ch)
        if not 0xAC00 <= o <= 0xD7A3:
            salida.append(ch)
            continue
        n = o - 0xAC00
        ini, vocal, fin = n // 588, (n % 588) // 28, n % 28
        siguiente = ord(chars[i + 1]) - 0xAC00 if i + 1 < len(chars) and 0xAC00 <= ord(chars[i + 1]) <= 0xD7A3 else None
        antes_de_vocal = siguiente is not None and siguiente // 588 == 11  # la siguiente empieza con ㅇ (vocal)
        salida.append(_INICIALES[ini] + _VOCALES[vocal] + (_ENLACE[fin] if antes_de_vocal else _FINALES[fin]))
    return "".join(salida)


# ---------- Japonés: kana (Hepburn) ----------
_KANA = dict(zip(
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽぁぃぅぇぉゃゅょゎゔ",
    ["a", "i", "u", "e", "o", "ka", "ki", "ku", "ke", "ko", "sa", "shi", "su", "se", "so", "ta", "chi", "tsu", "te", "to",
     "na", "ni", "nu", "ne", "no", "ha", "hi", "fu", "he", "ho", "ma", "mi", "mu", "me", "mo", "ya", "yu", "yo",
     "ra", "ri", "ru", "re", "ro", "wa", "wo", "n", "ga", "gi", "gu", "ge", "go", "za", "ji", "zu", "ze", "zo",
     "da", "ji", "zu", "de", "do", "ba", "bi", "bu", "be", "bo", "pa", "pi", "pu", "pe", "po",
     "a", "i", "u", "e", "o", "ya", "yu", "yo", "wa", "vu"]))
_PEQUENAS = {"ゃ": "ya", "ゅ": "yu", "ょ": "yo"}


def _a_hiragana(ch: str) -> str:
    o = ord(ch)
    return chr(o - 0x60) if 0x30A1 <= o <= 0x30F6 else unicodedata.normalize("NFKC", ch) if 0xFF66 <= o <= 0xFF9D else ch


def _kana(texto: str) -> str | None:
    """Romaji de una línea sin diccionario; None si tiene kanji."""
    if any(_escritura(ch) == "han" for ch in texto):
        return None
    letras = [_a_hiragana(ch) for ch in texto]
    salida: list[str] = []
    doblar = False
    i = 0
    while i < len(letras):
        ch = letras[i]
        if ch == "っ":
            doblar = True
            i += 1
            continue
        if ch == "ー":  # vocal larga: se repite la anterior
            if salida and salida[-1][-1:] in "aeiou":
                salida.append(salida[-1][-1])
            i += 1
            continue
        silaba = _KANA.get(ch)
        if silaba is None:
            salida.append(ch)
            doblar = False
            i += 1
            continue
        siguiente = letras[i + 1] if i + 1 < len(letras) else ""
        if siguiente in _PEQUENAS and silaba.endswith("i") and len(silaba) > 1:
            base = silaba[:-1]  # き + ゃ = kya; し + ゃ = sha; ち + ゃ = cha; じ + ゃ = ja
            silaba = (base if base in ("sh", "ch", "j") else base + "y") + _PEQUENAS[siguiente][1]
            if base in ("sh", "ch", "j"):
                silaba = base + _PEQUENAS[siguiente][1]
            i += 1
        if doblar:
            silaba = ("t" if silaba.startswith("ch") else silaba[0]) + silaba
            doblar = False
        if ch == "ん" and siguiente and (_KANA.get(siguiente, "x")[0] in "aeiouy"):
            silaba = "n'"
        salida.append(silaba)
        i += 1
    return "".join(salida)


# ---------- Japonés: kanji (pykakasi) ----------
# pykakasi lee palabra por palabra y da la lectura más común del diccionario, no la de la frase: estas son las que más
# fallan en canciones ("君" salía "kun", "人" salía "nin", "愛してる" salía "itoshi teru")
_LECTURAS = {"君": "kimi", "人": "hito", "日": "hi", "月": "tsuki", "愛し": "aishi", "今日は": "kyou wa"}
_SIGNOS = str.maketrans({"、": ", ", "。": ". ", "「": ' "', "」": '" ', "『": ' "', "』": '" '})
# Terminaciones de verbos y adjetivos: van pegadas a su palabra ("止ま" + "らない" = "tomaranai")
_TERMINACIONES = ("て", "で", "た", "だ", "ない", "なか", "ま", "う", "ら", "れ", "る", "よう")
_lector = None


def _particulas(kana: str, romaji: str, tras_kanji: bool) -> str:
    """は y へ se escriben "ha" y "he" pero como partícula se leen "wa" y "e"."""
    if tras_kanji and kana[0] in "はへ":
        romaji = ("wa" if kana[0] == "は" else "e") + romaji[2:]
    elif kana.startswith(("では", "には", "とは")):
        romaji = romaji[:2] + "wa" + romaji[4:]
    separar = " " if any(_escritura(ch) == "han" for ch in kana) else ""
    if kana.endswith("は"):
        return romaji[:-2] + separar + "wa"
    if kana.endswith("へ"):
        return romaji[:-2] + separar + "e"
    return romaji


def _japones(texto: str) -> str | None:
    """Romaji de una línea, con espacios entre palabras."""
    global _lector
    try:
        if _lector is None:
            import pykakasi  # aquí y no arriba: son 10 MB de diccionario y solo se ocupan con letras en japonés
            _lector = pykakasi.kakasi()
        partes = _lector.convert(texto)
    except Exception:  # sin diccionario la letra debe seguir saliendo: se romaniza solo lo que no tenga kanji
        return _kana(texto)
    salida = ""
    anterior = ""
    for parte in partes:
        original = parte["orig"]
        if not any(_escritura(ch) in ("kana", "han") for ch in original):
            salida += unicodedata.normalize("NFKC", original.translate(_SIGNOS))
            anterior = ""
            continue
        lectura = _LECTURAS.get(original) or _particulas(original, parte["hepburn"], bool(anterior) and _escritura(anterior[-1]) == "han")
        pegada = any(_escritura(ch) == "han" for ch in anterior) and _escritura(anterior[-1]) == "kana" and original.startswith(_TERMINACIONES)
        if anterior and not pegada:
            salida += " "
        salida += lectura
        anterior = original
    return salida.strip()


# ---------- Cirílico y griego ----------
_CIRILICO = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюяіїєґ",
    ["a", "b", "v", "g", "d", "e", "yo", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f",
     "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya", "i", "yi", "ye", "g"]))
_CIRILICO_UK = {"г": "h", "и": "y", "е": "e"}
_GRIEGO = dict(zip(
    "αβγδεζηθικλμνξοπρσςτυφχψωάέήίόύώϊϋΐΰ",
    ["a", "v", "g", "d", "e", "z", "i", "th", "i", "k", "l", "m", "n", "x", "o", "p", "r", "s", "s", "t", "y", "f",
     "ch", "ps", "o", "a", "e", "i", "i", "o", "y", "o", "i", "y", "i", "y"]))


def _por_tabla(texto: str, tabla: dict[str, str]) -> str:
    salida = []
    for ch in texto:
        bajo = ch.lower()
        if bajo in tabla:
            r = tabla[bajo]
            salida.append(r.capitalize() if ch != bajo else r)
        else:
            salida.append(ch)
    return "".join(salida)


# ---------- Árabe, hebreo y tailandés (aproximados) ----------
# Estas escrituras casi nunca escriben las vocales cortas (y el tailandés no separa palabras), así que la lectura es
# aproximada: sirve para cantar sin saber leer la escritura, no es una transliteración académica.

_ARABE = {
    "ا": "a", "أ": "a", "إ": "i", "آ": "aa", "ٱ": "a", "ب": "b", "ت": "t", "ث": "th", "ج": "j", "ح": "h", "خ": "kh",
    "د": "d", "ذ": "dh", "ر": "r", "ز": "z", "س": "s", "ش": "sh", "ص": "s", "ض": "d", "ط": "t", "ظ": "z", "ع": "'",
    "غ": "gh", "ف": "f", "ق": "q", "ك": "k", "ل": "l", "م": "m", "ن": "n", "ه": "h", "ة": "a", "ى": "a", "ء": "'",
    "ؤ": "'", "ئ": "'", "پ": "p", "چ": "ch", "ژ": "zh", "گ": "g", "ک": "k", "ی": "y",
    "َ": "a", "ُ": "u", "ِ": "i", "ً": "an", "ٌ": "un", "ٍ": "in", "ْ": "", "ـ": "", "،": ",", "؟": "?", "؛": ";",
    **{chr(0x0660 + i): str(i) for i in range(10)},
}
_ARABE_VOCALES = set("َُِاًٌٍ")


def _arabe(linea: str) -> str:
    salida = []
    for palabra in re.split(r"(\s+)", linea):
        if not palabra or palabra.isspace():
            salida.append(palabra)
            continue
        # "ال" al principio es el artículo: al-
        pre, cuerpo = ("al-", palabra[2:]) if palabra.startswith("ال") and len(palabra) > 3 else ("", palabra)
        letras = []
        for i, ch in enumerate(cuerpo):
            previo = cuerpo[i - 1] if i else ""
            if ch == "ّ":  # shadda: la consonante anterior va doble (aunque su vocal se haya escrito antes: مَّ)
                k = len(letras) - 1
                while k >= 0 and letras[k] in ("a", "u", "i", "an", "un", "in", ""):
                    k -= 1
                if k >= 0 and letras[k]:
                    letras.insert(k + 1, letras[k][-1])
                continue
            if ch in "وي":
                # Al principio o después de vocal es consonante (w, y); después de consonante es vocal larga (u, i)
                consonante = i == 0 or previo in _ARABE_VOCALES
                letras.append(("w" if ch == "و" else "y") if consonante else ("u" if ch == "و" else "i"))
                continue
            letras.append(_ARABE.get(ch, ch))
        salida.append(pre + "".join(letras))
    return "".join(salida)


_HEBREO = {
    "א": "", "ב": "v", "ג": "g", "ד": "d", "ה": "h", "ז": "z", "ח": "ch", "ט": "t", "כ": "kh", "ך": "kh", "ל": "l",
    "מ": "m", "ם": "m", "נ": "n", "ן": "n", "ס": "s", "ע": "", "פ": "f", "ף": "f", "צ": "ts", "ץ": "ts", "ק": "k",
    "ר": "r", "ש": "sh", "ת": "t", "׳": "'", "״": '"', "־": "-",
    # Niqud (cuando la letra lo trae)
    "ַ": "a", "ָ": "a", "ֲ": "a", "ֶ": "e", "ֵ": "e", "ֱ": "e", "ְ": "e", "ִ": "i", "ֹ": "o", "ֳ": "o", "ֻ": "u",
}
_HEBREO_DURAS = {"ב": "b", "כ": "k", "ך": "k", "פ": "p", "ף": "p"}
_HEBREO_PUNTOS = "ְֱֲֳִֵֶַָֹֻּׁׂ"


def _hebreo(linea: str) -> str:
    salida = []
    for palabra in re.split(r"(\s+)", linea):
        if not palabra or palabra.isspace():
            salida.append(palabra)
            continue
        letras = [ch for ch in palabra]
        out, leidos = [], set()
        for i, ch in enumerate(letras):
            if i in leidos:
                continue
            if ch in _HEBREO_PUNTOS and ch not in "ְֱֲֳִֵֶַָֹֻ":
                continue  # dagesh y puntos de shin/sin: se leen con su letra
            marcas = ""
            j = i + 1
            while j < len(letras) and letras[j] in _HEBREO_PUNTOS:
                marcas += letras[j]
                j += 1
            inicio = not any(c not in _HEBREO_PUNTOS for c in letras[:i])
            final = j >= len(letras)
            if ch == "ו":
                if "ֹ" in marcas:
                    out.append("o")
                    leidos.update(range(i + 1, j))
                elif "ּ" in marcas and not inicio:
                    out.append("u")
                    leidos.update(range(i + 1, j))
                else:
                    out.append("v" if inicio else "o")
            elif ch == "י":
                # Después de una i o una e escritas, la yud solo alarga la vocal (אֲנִי = ani)
                out.append("y" if inicio else "" if out and out[-1] in ("i", "e") and letras[i - 1] in "ִֵֶ" else "i")
            elif ch == "א":
                # Al principio suena "a", salvo que la vocal la ponga lo que sigue (אוֹהֵב = ohev, אֲנִי = ani)
                siguiente = letras[j] if j < len(letras) else ""
                out.append("a" if inicio and not marcas.strip("ּׁׂ") and siguiente not in "וי" else "")
            elif ch == "ה" and final and not inicio:
                out.append("a")
            elif ch == "ש":
                out.append("s" if "ׂ" in marcas else "sh")
            elif ch in _HEBREO_DURAS:
                out.append(_HEBREO_DURAS[ch] if (inicio or "ּ" in marcas) else _HEBREO[ch])
            elif ch == "ְ" and final:
                out.append("")  # la shva al final no suena
            else:
                out.append(_HEBREO.get(ch, ch))
        salida.append("".join(out))
    return "".join(salida)


# Tailandés (RTGS simplificado): consonante inicial / final
_TH_INICIAL = {
    "ก": "k", "ข": "kh", "ฃ": "kh", "ค": "kh", "ฅ": "kh", "ฆ": "kh", "ง": "ng", "จ": "ch", "ฉ": "ch", "ช": "ch",
    "ซ": "s", "ฌ": "ch", "ญ": "y", "ฎ": "d", "ฏ": "t", "ฐ": "th", "ฑ": "th", "ฒ": "th", "ณ": "n", "ด": "d", "ต": "t",
    "ถ": "th", "ท": "th", "ธ": "th", "น": "n", "บ": "b", "ป": "p", "ผ": "ph", "ฝ": "f", "พ": "ph", "ฟ": "f", "ภ": "ph",
    "ม": "m", "ย": "y", "ร": "r", "ล": "l", "ว": "w", "ศ": "s", "ษ": "s", "ส": "s", "ห": "h", "ฬ": "l", "อ": "", "ฮ": "h",
}
_TH_FINAL = {**{c: "k" for c in "กขฃคฅฆ"}, "ง": "ng", **{c: "t" for c in "จชซฌฎฏฐฑฒดตถทธศษส"},
             **{c: "n" for c in "ญณนรลฬ"}, **{c: "p" for c in "บปผฝพฟภ"}, "ม": "m", "ย": "i", "ว": "o", "อ": "", "ห": "", "ฮ": ""}
_TH_VOCAL = {"ะ": "a", "ั": "a", "า": "a", "ำ": "am", "ิ": "i", "ี": "i", "ึ": "ue", "ื": "ue", "ุ": "u", "ู": "u",
             "็": "", "่": "", "้": "", "๊": "", "๋": "", "ฤ": "rue", "ฦ": "lue", "ๆ": "", "ฯ": ""}
_TH_ANTES = {"เ": "e", "แ": "ae", "โ": "o", "ใ": "ai", "ไ": "ai"}  # se escriben antes de la consonante y suenan después
_TH_PEGADAS = set("ะัาำิีึืุู็่้๊๋์")
_TH_GRUPO = set("กขคตปผพ")  # pueden ir con ร ล ว: kr, khl, pl…
_TH_MUDA_H = set("งญนมยรลว")  # ห delante de estas no suena (หนึ่ง = nueng)


def _thai(linea: str) -> str:
    s = [chr(ord(c) - 0x0E50 + 0x30) if "๐" <= c <= "๙" else c for c in linea]
    out, i = [], 0
    inicial = vocal = False
    pendiente = None
    def sig(k):
        return s[k] if k < len(s) else ""
    def sin_tono(k):  # el siguiente índice que no es marca de tono
        while sig(k) in ("่", "้", "๊", "๋"):
            k += 1
        return k
    while i < len(s):
        c = s[i]
        if c in _TH_ANTES:
            pendiente = c
            i += 1
            continue
        if c in _TH_INICIAL:
            if sig(i + 1) == "์":  # thanthakhat: esta consonante no se pronuncia
                i += 2
                continue
            pegada = sig(i + 1) in _TH_PEGADAS
            if c == "ห" and sig(i + 1) in _TH_MUDA_H and not vocal and pendiente is None:
                i += 1  # ห muda: solo cambia el tono de la siguiente
                continue
            if inicial and not vocal and c in "รลว" and out and out[-1] in ("k", "kh", "t", "p", "ph") and pegada:
                out.append(_TH_INICIAL[c])  # grupo: กล = kl
                i += 1
                continue
            grupo = c in _TH_GRUPO and sig(i + 1) in "รลว" and sig(i + 2) in _TH_PEGADAS  # ครับ = khrap: empieza otra sílaba
            if pendiente is None and inicial and vocal and not pegada and not grupo:
                fin = _TH_FINAL.get(c, "")
                if not (fin == "i" and out and out[-1].endswith("i")):
                    out.append(fin)
                inicial = vocal = False
                i += 1
                continue
            if pendiente is None and inicial and not vocal and not pegada:
                out.append("o" + _TH_FINAL.get(c, ""))  # คน = khon: la vocal que no se escribe
                vocal = True
                i += 1
                continue
            if inicial and not vocal:
                out.append("a")  # สบาย = sabai
            out.append(_TH_INICIAL[c])
            inicial, vocal = True, False
            i += 1
            if pendiente is not None:
                if c in _TH_GRUPO and sig(i) in "รลว" and sig(i + 1) not in _TH_PEGADAS:
                    out.append(_TH_INICIAL[sig(i)])
                    i += 1
                v = _TH_ANTES[pendiente]
                if pendiente == "เ" and sig(i) == "า":
                    v, i = "ao", i + 1
                elif pendiente == "เ" and sig(i) == "ี" and sig(sin_tono(i + 1)) == "ย":
                    v, i = "ia", sin_tono(i + 1) + 1
                elif pendiente == "เ" and sig(i) == "ื" and sig(sin_tono(i + 1)) == "อ":
                    v, i = "uea", sin_tono(i + 1) + 1
                elif pendiente == "เ" and sig(sin_tono(i)) == "อ":
                    v, i = "oe", sin_tono(i) + 1
                out.append(v)
                vocal, pendiente = True, None
            continue
        if c in _TH_VOCAL:
            if c == "ั" and sig(i + 1) == "ว":
                out.append("ua")
                i += 2
                vocal = True
                continue
            out.append(_TH_VOCAL[c])
            if c in "ะำ":
                inicial = vocal = False
            elif _TH_VOCAL[c]:
                vocal = True
            i += 1
            continue
        if c == "์":
            i += 1
            continue
        if inicial and not vocal and not c.strip():
            out.append("a")  # sílaba que se quedó sin vocal antes de un espacio
        inicial = vocal = False
        pendiente = None
        out.append(c)
        i += 1
    return "".join(out)


def romanizar(lineas: list[str], cod: str) -> list[str | None]:
    """Una romanización por línea (None en las que no se pudo, p. ej. con kanji)."""
    if cod == "ko":
        return [_coreano(l) for l in lineas]
    if cod == "ja":
        return [_japones(l) for l in lineas]
    if cod in ("ru", "uk"):
        tabla = {**_CIRILICO, **_CIRILICO_UK} if cod == "uk" else _CIRILICO
        return [_por_tabla(l, tabla) for l in lineas]
    if cod == "el":
        return [_por_tabla(l, _GRIEGO) for l in lineas]
    funcion = {"ar": _arabe, "he": _hebreo, "th": _thai}.get(cod)
    if funcion:
        return [funcion(l) for l in lineas]
    return [None] * len(lineas)
