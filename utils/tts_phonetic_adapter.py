# -*- coding: utf-8 -*-
"""
utils/tts_phonetic_adapter.py — Adaptador fonético y estructural para Edge TTS
==============================================================================
Compensa la falta de SSML en Edge TTS (es-AR-TomasNeural / es-AR-ElenaNeural)
transformando el texto del rewriter en un guion optimizado para locución
natural, expresiva y no mecánica.

Reglas implementadas (directiva editorial definitiva):
1. ESTRUCTURA Y RESPIRACIÓN: oraciones de 12-18 palabras, comas antes de
   conectores breves (micro-pausas), puntos suspensivos para desacelerar el
   cierre, paréntesis y guiones largos convertidos en frases independientes.
2. EXPANSIÓN ORTOTIPOGRÁFICA: números cardinales y ordinales en palabras,
   unidades/porcentajes/symbols transcriptos, "pesos"/"dólares" antepuesto a
   la cifra, fechas completas ("cuatro de noviembre").
3. ADAPTACIÓN FONÉTICA: siglas desglosadas letra por letra (E-N-R-E),
   extranjerismos transcritos al español rioplatense ("uatsap", "onláin").
4. Devuelve ÚNICAMENTE el texto procesado.
"""

import re

_UNIDADES = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete",
             "ocho", "nueve", "diez", "once", "doce", "trece", "catorce",
             "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve",
             "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro",
             "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
_DECENAS = ["", "", "veinte", "treinta", "cuarenta", "cincuenta", "sesenta",
            "setenta", "ochenta", "noventa"]
_CIENTOS = ["", "ciento", "doscientos", "trescientos", "cuatrocientos",
            "quinientos", "seiscientos", "setecientos", "ochocientos", "novecientos"]

_ORDINALES = {
    1: ("primero", "primera"), 2: ("segundo", "segunda"), 3: ("tercero", "tercera"),
    4: ("cuarto", "cuarta"), 5: ("quinto", "quinta"), 6: ("sexto", "sexta"),
    7: ("séptimo", "séptima"), 8: ("octavo", "octava"), 9: ("noveno", "novena"),
    10: ("décimo", "décima"), 11: ("undécimo", "undécima"), 12: ("duodécimo", "duodécima"),
    15: ("decimoquinto", "decimoquinta"), 20: ("vigésimo", "vigésima"),
}

_MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _menor_mil(n: int) -> str:
    if n <= 0:
        return ""
    if n == 100:
        return "cien"
    c, r = divmod(n, 100)
    partes = []
    if c:
        partes.append("ciento" if c == 1 else _CIENTOS[c])
    if r:
        if r < 30:
            partes.append(_UNIDADES[r])
        else:
            d, u = divmod(r, 10)
            partes.append(_DECENAS[d] + (f" y {_UNIDADES[u]}" if u else ""))
    return " ".join(partes)


def num_a_palabras(n: int) -> str:
    """Convierte un entero 0..999.999.999 a su forma en palabras."""
    if n < 0:
        return "menos " + num_a_palabras(-n)
    if n < 1000:
        return _menor_mil(n) or "cero"
    if n < 1_000_000:
        miles, r = divmod(n, 1000)
        s = "mil" if miles == 1 else f"{_menor_mil(miles)} mil"
        if r:
            s += " " + _menor_mil(r)
        return s
    if n < 1_000_000_000:
        mm, r = divmod(n, 1_000_000)
        s = "un millón" if mm == 1 else f"{_menor_mil(mm)} millones"
        if r:
            s += " " + num_a_palabras(r)
        return s
    return str(n)


def _parse_numero(token: str) -> int:
    """Parsea '300.000' (punto=millar, formato AR) a entero."""
    return int(token.replace(".", "").replace(",", ""))


# ──────────────────────────────────────────────────────────────────────
# Extranjerismos → transcripción fonética rioplatense
# ──────────────────────────────────────────────────────────────────────
_EXTRANJERISMOS = [
    (r'\bWhatsApp\b', 'uatsap'),
    (r'\bwhatsapp\b', 'uatsap'),
    (r'\bFacebook\b', 'feisbuc'),
    (r'\bInstagram\b', 'instagran'),
    (r'\btwiter|Twitter\b', 'tuíter'),
    (r'\bstreaming\b', 'stríming'),
    (r'\bonline\b', 'onláin'),
    (r'\bwi[-\s]?fi\b', 'guai-fai'),
    (r'\bweb app\b', 'béc-ap'),
    (r'\bwebsite\b', 'websáit'),
    (r'\bweb\b', 'béc'),
    (r'\bloguin|login\b', 'lóguin'),
    (r'\bcoupon\b', 'cupón'),
    (r'\bshopping\b', 'shóping'),
    (r'\bsandwich\b', 'sánduich'),
    (r'\bfood truck\b', 'fud truck'),
    (r'\bDJ\b', 'di-yéi'),
    (r'\bshow\b', 'shou'),
    (r'\bsms\b', 'es-em-es'),
    (r'\blink\b', 'linqu'),
    (r'\bclick\b', 'clic'),
    (r'\bteam\b', 'tim'),
    (r'\bgps\b', 'hi-pi-es'),
]

# Palabras en mayúsculas que NO son siglas (no desglosar)
_STOP_UPPER = {"EN", "DE", "LA", "EL", "UN", "UNA", "LOS", "LAS", "Y", "A", "CON",
               "POR", "PARA", "DEL", "AL", "ES", "SON", "FUE", "HAY", "SE", "SI",
               "NO", "QUE", "SU", "SUS", "COMO", "TODO", "TODA", "TODOS", "TODAS",
               "MUY", "MAS", "YA", "FTE", "OBRAS"}

# Conectores breves que reciben coma de micro-pausa adelante
_CONECTORES = r"(?:pero|aunque|sino|además|también|luego|después|entonces|finalmente|igualmente)"


# ──────────────────────────────────────────────────────────────────────
# Transformaciones
# ──────────────────────────────────────────────────────────────────────
def _abreviaturas_a_palabras(texto: str) -> str:
    # Títulos y abreviaturas frecuentes que el TTS deletrearía mal
    texto = re.sub(r'\bIng\.\s*', 'ingeniero ', texto)
    texto = re.sub(r'\bDra\.\s*', 'doctora ', texto)
    texto = re.sub(r'\bDr\.\s*', 'doctor ', texto)
    texto = re.sub(r'\bSra\.\s*', 'señora ', texto)
    texto = re.sub(r'\bSr\.\s*', 'señor ', texto)
    texto = re.sub(r'\b(?:N°|Nº|Nro\.)\s*(\d+)', lambda m: f"número {num_a_palabras(int(m.group(1)))}", texto)
    texto = re.sub(r'\bDNI\b', 'de ene i', texto)
    return texto


def _expandir_moneda(texto: str) -> str:
    # u$s / US$ / usd → dólares anteponida
    texto = re.sub(r'u\.?\s?\$\s*([\d.]+)', lambda m: f"dólares {num_a_palabras(_parse_numero(m.group(1)))}", texto)
    texto = re.sub(r'\bUS?D\.?\s*([\d.]+)', lambda m: f"dólares {num_a_palabras(_parse_numero(m.group(1)))}", texto)
    # $ → pesos anteponida
    texto = re.sub(r'\$\s*([\d][\d.,]*)', lambda m: f"pesos {num_a_palabras(_parse_numero(m.group(1)))}", texto)
    return texto


def _expandir_porcentajes(texto: str) -> str:
    return re.sub(r'(\d+)\s*%', lambda m: f"{num_a_palabras(int(m.group(1)))} por ciento", texto)


def _expandir_unidades(texto: str) -> str:
    texto = re.sub(r'\b(\d+(?:[.,]\d+)?)\s*km/h\b', lambda m: f"{num_a_palabras(_parse_numero(m.group(1)))} kilómetros por hora", texto, flags=re.I)
    texto = re.sub(r'\b(\d+(?:[.,]\d+)?)\s*km\b', lambda m: f"{num_a_palabras(_parse_numero(m.group(1)))} kilómetros", texto, flags=re.I)
    texto = re.sub(r'\b(\d+(?:[.,]\d+)?)\s*(?:mts?\.?|metros)\b', lambda m: f"{num_a_palabras(_parse_numero(m.group(1)))} metros", texto, flags=re.I)
    texto = re.sub(r'\b(\d+(?:[.,]\d+)?)\s*kg\b', lambda m: f"{num_a_palabras(_parse_numero(m.group(1)))} kilos", texto, flags=re.I)
    texto = re.sub(r'\b(\d+(?:[.,]\d+)?)\s*m\b(?![a-zA-Z])', lambda m: f"{num_a_palabras(_parse_numero(m.group(1)))} metros", texto)
    texto = re.sub(r'\b(\d+(?:[.,]\d+)?)\s*(?:hs?|horas)\b', lambda m: f"{num_a_palabras(_parse_numero(m.group(1)))} horas", texto, flags=re.I)
    return texto


def _expandir_fechas(texto: str) -> str:
    def _fecha(m):
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if not (1 <= mo <= 12) or not (1 <= d <= 31):
            return m.group(0)
        s = f"{num_a_palabras(d)} de {_MESES[mo]}"
        if y:
            yy = int(y)
            if yy < 100:
                yy += 2000
            s += f" de {num_a_palabras(yy)}"
        return s
    return re.sub(r'\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b', _fecha, texto)


def _expandir_ordinales(texto: str) -> str:
    def _ord(m):
        n = int(m.group(1))
        genero = 1 if m.group(2) in ("ª", "a") else 0
        if n in _ORDINALES:
            return _ORDINALES[n][genero]
        return num_a_palabras(n)
    texto = re.sub(r'\b(\d{1,2})(?:º|°)\b', lambda m: _ORDINALES[int(m.group(1))][0] if int(m.group(1)) in _ORDINALES else num_a_palabras(int(m.group(1))), texto)
    texto = re.sub(r'\b(\d{1,2})ª\b', lambda m: _ORDINALES[int(m.group(1))][1] if int(m.group(1)) in _ORDINALES else num_a_palabras(int(m.group(1))), texto)
    return texto


def _expandir_numeros(texto: str) -> str:
    # Fechas y horas primero (contextos especiales)
    texto = _expandir_fechas(texto)
    # Números con separador de miles AR: 300.000
    texto = re.sub(r'\b\d{1,3}(?:\.\d{3})+\b', lambda m: num_a_palabras(_parse_numero(m.group(0))), texto)
    # Números sueltos (no formar parte de siglas/urls ya removidas)
    texto = re.sub(r'(?<![\w-])\d+(?![\w.])', lambda m: num_a_palabras(int(m.group(0))), texto)
    return texto


def _desglosar_siglas(texto: str) -> str:
    # Siglas con puntos ("E.N.R.E." / "C.P.R.") → letra-letra sin puntos
    texto = re.sub(r'\b(?:[A-Z]\.){2,}[A-Z]?\.?',
                   lambda m: "-".join(c for c in m.group(0) if c.isalpha()), texto)
    # Runs de 3+ palabras en mayúsculas = encabezados de gacetilla → minúsculas
    texto = re.sub(r'\b(?:[A-ZÁÉÍÓÚÑ]{2,}\s+){2,}(?=[A-ZÁÉÍÓÚÑ][a-záéíóúñ]|\b[A-ZÁÉÍÓÚÑ]{2,}\b\s*$|\b[A-ZÁÉÍÓÚÑ]{2,}(?:\s+\S+)*$)',
                   lambda m: " ".join(w.lower() for w in m.group(0).split()) + " ", texto)
    if not re.search(r'[a-záéíóúñ]', texto):
        return texto
    # Siglas de 2 a 5 letras mayúsculas → letra-letra
    def _sigla(m):
        tok = m.group(0)
        if tok in _STOP_UPPER or len(set(tok)) < 2:
            return tok
        return "-".join(tok)
    return re.sub(r'\b[A-Z]{2,5}\b', _sigla, texto)


def _extranjerismos(texto: str) -> str:
    for patron, reemplazo in _EXTRANJERISMOS:
        texto = re.sub(patron, reemplazo, texto)
    return texto


def _estructura_y_respiracion(texto: str, final_pause: bool = True) -> str:
    # 1. Paréntesis y guiones largos → comas
    texto = texto.replace("(", ", ").replace(")", ", ")
    texto = re.sub(r'\s*[—–]\s*', ', ', texto)
    texto = re.sub(r'(\s,\s)+', ', ', texto)
    texto = re.sub(r'(?<=\.)\s*,\s*', ' ', texto)
    texto = re.sub(r',\s*(?=[\.,])', '', texto)

    # 2. Oraciones: dividir recursivamente las de más de 18 palabras.
    #    Orden de corte: coma cercana al centro → conjunción oracional → coma de
    #    respiro inyectada (nunca dentro de cifras en palabras ni antes de
    #    funciontes como artículos/preposiciones).
    _PALABRAS_NO_CORTE = set(_UNIDADES) | set(_DECENAS) | set(_CIENTOS) | {
        "mil", "millón", "millones", "pesos", "dólares", "por", "ciento", "y",
        "la", "el", "los", "las", "un", "una", "unos", "unas", "de", "del",
        "en", "con", "al", "a", "o", "e", "que", "su", "sus", "lo", "se", "es",
        "para", "les", "le", "con", "al"}
    _CONECT_ORACIONALES = ("que", "pero", "aunque", "además", "también", "mientras", "donde", "cuando")

    def _split_recursive(s: str, budget: int = 4):
        s = s.strip()
        if not s or len(s.split()) <= 18 or budget <= 0:
            return [s] if s else []
        partes = s.split(", ")
        if len(partes) >= 2:
            total = len(s.split())
            mejor, mejor_dist, acum = 0, 10**9, 0
            for i in range(len(partes) - 1):
                acum += len(partes[i].split())
                if abs(acum - total / 2) < mejor_dist:
                    mejor_dist, mejor = abs(acum - total / 2), i
            first = partes[:mejor + 1][0]
            rest = ", ".join(partes[mejor + 1:])
            return _split_recursive(first, budget - 1) + _split_recursive(rest, budget - 1)
        palabras = s.split()
        candidatos = [i for i, w in enumerate(palabras)
                      if w in _CONECT_ORACIONALES and 0 < i < len(palabras) - 1]
        if candidatos:
            i = min(candidatos, key=lambda i: abs(i - len(palabras) / 2))
            return _split_recursive(" ".join(palabras[:i]), budget - 1) + \
                   _split_recursive(" ".join(palabras[i + 1:]), budget - 1)
        safe = []
        for i in range(3, len(palabras) - 3):
            w_prev, w_curr = palabras[i - 1], palabras[i]
            # No cortar dentro de frases numéricas contiguas (pesos trescientos mil, etc.)
            if w_prev in _PALABRAS_NO_CORTE and w_curr in _PALABRAS_NO_CORTE:
                continue
            # No cortar entre dos nombres propios (ambos titlecase con más de 2 letras).
            if w_prev.istitle() and w_curr.istitle() and len(w_prev) > 2 and len(w_curr) > 2:
                continue
            # No cortar antes de artículos definidos/poseivos que inician un sintagma.
            if w_curr in {"El", "La", "Los", "Las", "Un", "Una", "Su", "Sus"}:
                continue
            safe.append(i)
        if not safe:
            return [s]
        i = min(safe, key=lambda i: abs(i - len(palabras) / 2))
        return _split_recursive(" ".join(palabras[:i]), budget - 1) + \
               _split_recursive(" ".join(palabras[i:]), budget - 1)

    trozos = []
    for s in re.split(r'(?<=[\.\!\?])\s+', texto):
        trozos.extend(t for t in _split_recursive(s) if t)
    partes_out = []
    for t in trozos:
        t = t.strip().rstrip(",;")
        if t:
            partes_out.append(t[0].upper() + t[1:].strip() + ".")
    texto = " ".join(partes_out)

    # 3. Coma de micro-pausa antes de conectores breves y tras conectores al inicio
    texto = re.sub(rf'(?<![,\.;])\s+{_CONECTORES}\b', lambda m: ", " + m.group(0).strip(), texto)
    texto = re.sub(r'\bsin embargo\b', 'sin embargo,', texto)
    texto = re.sub(r'(?<=\.)\s+(Además|También|Luego|Después|Entonces|Finalmente|Igualmente|Sin embargo)(?=[ ,])',
                   lambda m: " " + m.group(1) + ",", texto)

    # 4. Puntuación final: punto → puntos suspensivos (desaceleración del cierre)
    if final_pause:
        texto = re.sub(r'\.\s*$', '...', texto.rstrip())
    elif not texto.endswith(('.', '!', '?')):
        texto += "."
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


# ──────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────
def adapt_text_for_tts(text: str, final_pause: bool = True) -> str:
    """
    Aplica todas las reglas del adaptador fonético para Edge TTS y devuelve
    ÚNICAMENTE el texto procesado (sin saludos, notas ni markdown).
    """
    if not text:
        return ""
    texto = " ".join(text.split())
    texto = _abreviaturas_a_palabras(texto)
    texto = _expandir_moneda(texto)
    texto = _expandir_porcentajes(texto)
    texto = _expandir_unidades(texto)
    texto = _expandir_ordinales(texto)
    texto = _expandir_numeros(texto)
    texto = _extranjerismos(texto)
    texto = _desglosar_siglas(texto)
    texto = _estructura_y_respiracion(texto, final_pause=final_pause)
    return texto
