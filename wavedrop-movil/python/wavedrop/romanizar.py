"""Idioma de una letra y su romanización, sin internet.

- idioma(): por el tipo de escritura (hiragana/katakana → japonés, hangul → coreano, cirílico → ruso…);
  en alfabeto latino, por palabras comunes de cada idioma.
- romanizar(): coreano (Romanización Revisada), japonés (Hepburn; los kanji se leen con el diccionario de pykakasi),
  cirílico (ruso/ucraniano) y griego. El chino necesita un diccionario que no viene aquí: se deja sin romanizar.
"""
import re
import unicodedata

NOMBRES = {
    "ja": "Japonés", "ko": "Coreano", "zh": "Chino", "ru": "Ruso", "uk": "Ucraniano", "el": "Griego", "ar": "Árabe",
    "he": "Hebreo", "hi": "Hindi", "th": "Tailandés", "es": "Español", "en": "Inglés", "pt": "Portugués",
    "fr": "Francés", "it": "Italiano", "de": "Alemán",
}
ROMANIZABLES = {"ja", "ko", "ru", "uk", "el"}

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
    return [None] * len(lineas)
