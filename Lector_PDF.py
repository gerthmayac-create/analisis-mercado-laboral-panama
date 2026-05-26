import os
import re
import json
import pytesseract
import fitz
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageEnhance, ImageFilter
from collections import Counter


# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================

APP_NAME = "RenombradorOficios"

# Carpeta segura para guardar config e históricos del usuario
APPDATA_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", APP_NAME)

if not os.path.exists(APPDATA_DIR):
    os.makedirs(APPDATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(APPDATA_DIR, "config_tesseract.txt")
HISTORIAL_FILE = os.path.join(APPDATA_DIR, "historial_oficios.json")


# =====================================================
# CONFIGURACIÓN TESSERACT
# =====================================================

def guardar_config(ruta):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(ruta)


def cargar_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None


def encontrar_tesseract():
    rutas = [
        os.path.join(
            os.path.expanduser("~"),
            "AppData",
            "Local",
            "Programs",
            "Tesseract-OCR",
            "tesseract.exe"
        ),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]

    for ruta in rutas:
        if ruta and os.path.exists(ruta):
            return ruta

    return None


def inicializar_tesseract(ruta):
    pytesseract.pytesseract.tesseract_cmd = ruta

    tessdata = os.path.join(os.path.dirname(ruta), "tessdata")

    if os.path.exists(tessdata):
        os.environ["TESSDATA_PREFIX"] = tessdata


def configurar_tesseract_manual():
    ruta = filedialog.askopenfilename(
        title="Selecciona tesseract.exe",
        filetypes=[("Ejecutable", "*.exe")]
    )

    if ruta:
        guardar_config(ruta)
        inicializar_tesseract(ruta)
        messagebox.showinfo("OK", "Tesseract configurado correctamente.")


def setup_tesseract():
    ruta = cargar_config()

    if ruta and os.path.exists(ruta):
        inicializar_tesseract(ruta)
        return

    ruta = encontrar_tesseract()

    if ruta:
        inicializar_tesseract(ruta)
        guardar_config(ruta)
        return

    messagebox.showwarning(
        "Tesseract no encontrado",
        "No se encontró Tesseract automáticamente.\n\n"
        "Usa el botón 'Configurar Tesseract' para seleccionarlo manualmente."
    )


# =====================================================
# HISTÓRICO / APRENDIZAJE
# =====================================================

def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    return []


def guardar_historial(historial):
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)


def limpiar_token(token):
    token = token.upper()
    token = re.sub(r"[^A-ZÁÉÍÓÚÑ0-9]", "", token)
    return token


def tokens_de_linea(linea):
    stopwords = {
        "DE", "DEL", "LA", "EL", "LOS", "LAS", "Y", "O", "EN", "A",
        "POR", "PARA", "CON", "SIN", "UN", "UNA", "NO", "N", "NUM",
        "NUMERO", "Nº", "OFICIO"
    }

    tokens = []

    for t in linea.split():
        t = limpiar_token(t)

        if not t:
            continue

        if t in stopwords:
            continue

        if t.isdigit():
            continue

        if len(t) < 3:
            continue

        tokens.append(t)

    return tokens


def aprender_de_resultado(archivo_original, nuevo_nombre, numero, linea_detectada, score):
    """
    Guarda solo detecciones razonablemente confiables.
    Esto evita que el sistema aprenda fechas o falsos positivos.
    """

    if not linea_detectada:
        return

    linea_upper = linea_detectada.upper()

    # Seguridad: solo aprender si la línea realmente parece relacionada a OFICIO
    if "OFICIO" not in linea_upper:
        return

    historial = cargar_historial()

    registro = {
        "archivo_original": archivo_original,
        "nuevo_nombre": nuevo_nombre,
        "numero": numero,
        "linea_detectada": linea_detectada,
        "score": score,
        "tokens": tokens_de_linea(linea_detectada)
    }

    historial.append(registro)

    # Evitar que crezca infinitamente
    historial = historial[-500:]

    guardar_historial(historial)


def obtener_tokens_aprendidos():
    historial = cargar_historial()
    contador = Counter()

    for item in historial:
        for token in item.get("tokens", []):
            contador[token] += 1

    return contador


def ver_aprendizaje():
    historial = cargar_historial()
    tokens = obtener_tokens_aprendidos()

    ventana_hist = tk.Toplevel(ventana)
    ventana_hist.title("Aprendizaje histórico")
    ventana_hist.geometry("700x500")

    txt = tk.Text(ventana_hist, wrap="word")
    txt.pack(expand=True, fill="both", padx=10, pady=10)

    txt.insert(tk.END, f"Total de ejemplos aprendidos: {len(historial)}\n\n")

    txt.insert(tk.END, "Tokens más aprendidos:\n")
    txt.insert(tk.END, "----------------------\n")

    for token, count in tokens.most_common(30):
        txt.insert(tk.END, f"{token}: {count}\n")

    txt.insert(tk.END, "\nÚltimos ejemplos:\n")
    txt.insert(tk.END, "----------------------\n")

    for item in historial[-20:]:
        txt.insert(
            tk.END,
            f"{item.get('archivo_original')} → {item.get('nuevo_nombre')}\n"
            f"Línea: {item.get('linea_detectada')}\n\n"
        )


def borrar_aprendizaje():
    if messagebox.askyesno(
        "Borrar aprendizaje",
        "¿Seguro que quieres borrar todo el historial aprendido?"
    ):
        if os.path.exists(HISTORIAL_FILE):
            os.remove(HISTORIAL_FILE)

        messagebox.showinfo("OK", "Aprendizaje borrado correctamente.")


# =====================================================
# PROCESAMIENTO DE IMAGEN
# =====================================================

def mejorar_imagen(img):
    img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def recortar_encabezado(img):
    ancho, alto = img.size

    # 60% porque algunos documentos traen el oficio más abajo
    return img.crop((0, 0, ancho, int(alto * 0.6)))


def pdf_a_imagen(ruta_pdf):
    doc = fitz.open(ruta_pdf)

    pagina = doc[0]

    # Zoom 2.5 mejora lectura de números pequeños
    pix = pagina.get_pixmap(matrix=fitz.Matrix(3, 3))

    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


# =====================================================
# OCR Y EXTRACCIÓN INTELIGENTE POR LÍNEA
# =====================================================

def normalizar_linea(linea):
    linea = linea.upper()
    linea = linea.replace("N°", "Nº")
    linea = linea.replace("N8", "Nº")
    linea = linea.replace("NO.", "NO")
    linea = linea.replace("N0", "NO")

    # Errores OCR comunes
    linea = linea.replace("0FICIO", "OFICIO")
    linea = linea.replace("OFIC10", "OFICIO")
    linea = linea.replace("OF1CIO", "OFICIO")

    linea = re.sub(r"\s+", " ", linea).strip()
    return linea


def limpiar_numero(numero):
    if not numero:
        return None

    numero = str(numero)

    # Correcciones comunes OCR
    numero = numero.replace("l", "1").replace("I", "1").replace("|", "1")
    numero = numero.replace("O", "0").replace("o", "0")

    # Permitir dígitos, guiones y slash
    numero = re.sub(r"[^\d/-]", "", numero)

    # Limpiar separadores dobles
    numero = re.sub(r"[-/]{2,}", "-", numero)

    return numero.strip("-/")


def normalizar_nombre_archivo(texto: str, max_len: int = 180) -> str:
    """
    Convierte el código detectado en un nombre válido para Windows.
    Requisito del usuario: reemplazar "/" por "-".
    """
    if not texto:
        return ""

    s = str(texto).strip()

    # 1) Reemplazos clave
    s = s.replace("/", "-")      # <-- lo que pediste
    s = s.replace("\\", "-")     # evita rutas accidentales

    # 2) Quitar caracteres inválidos en Windows: <>:"|?*  y controles
    s = re.sub(r'[<>:"|?*\x00-\x1F]', "", s)

    # 3) Compactar espacios y separadores repetidos
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"-{2,}", "-", s)

    # 4) Windows no permite terminar en punto o espacio
    s = s.strip(" .-_")

    # 5) Limitar longitud por seguridad
    if len(s) > max_len:
        s = s[:max_len].rstrip(" .-_")

    return s


def es_fecha_o_numero_malo(numero, linea):
    """
    Evita fechas y números basura, pero permite números de oficio largos.
    """

    if not numero:
        return True

    limpio = limpiar_numero(numero)

    if not limpio:
        return True

    solo_digitos = re.sub(r"\D", "", limpio)

    # Muy corto
    if len(solo_digitos) < 2:
        return True

    # Evitar años solos
    if re.fullmatch(r"20\d{2}", limpio):
        return True

    # Evitar fechas tipo 25/05/2026 o 13-05-2026
    if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]20\d{2}", limpio):
        return True

    # Evitar fechas compactas tipo 25052026, pero solo si parece fecha real
    if len(solo_digitos) == 8:
        dia = int(solo_digitos[:2])
        mes = int(solo_digitos[2:4])
        anio = solo_digitos[4:]

        if 1 <= dia <= 31 and 1 <= mes <= 12 and anio.startswith("20"):
            return True

    return False

def extraer_candidato_de_linea(linea):
    """
    Devuelve el mejor código de oficio dentro de una línea candidata.
    Prioriza el código inmediatamente después de OFICIO / NO / Nº.
    Permite códigos largos con letras (EXP/SEC), barras y guiones.
    """

    l = normalizar_linea(linea)
    candidatos = []

    def limpiar_codigo_oficio(s: str) -> str:
        s = normalizar_linea(s)
        # Quita espacios y normaliza tokens comunes
        s = re.sub(r"\s+", "", s)
        s = s.replace("EXPEDIENTE", "EXP")
        # Quita puntos después de SEC./EXP. -> SEC / EXP
        s = re.sub(r"(SEC|SECC|EXP)\.+", r"\1", s)
        # Deja solo caracteres válidos para el nombre
        s = re.sub(r"[^A-Z0-9/\-_.]", "", s)
        # Recorta separadores sobrantes
        s = s.strip("._-/")
        return s

    patrones_prioritarios = [
        # OFICIO Nº 865/EXP. 111833-19   | OFICIO NO912/ SEC. 118063-23 | OFICIO Nº1211/EXP115886-23
        r"OFICIO\s*(?:NO|Nº|NRO|NUMERO)?\s*[:.\-]?\s*([0-9][A-Z0-9\s./-]{1,60})",

        # OFICIO ... NO 865/EXP. 111833-19
        r"OFICIO.*?(?:NO|Nº|NRO|NUMERO)\s*[:.\-]?\s*([0-9][A-Z0-9\s./-]{1,60})",

        # OFICIO 1211/EXP115886-23
        r"OFICIO\s+([0-9][A-Z0-9\s./-]{1,60})",
    ]

    for patron in patrones_prioritarios:
        m = re.search(patron, l, re.IGNORECASE)
        if m:
            bruto = m.group(1)

            # ✅ IMPORTANTE: ya NO cortamos por SEC/EXP porque SÍ pertenecen al código
            # Solo cortamos por palabras que sí suelen ser "basura" del encabezado
            bruto = re.split(
                r"\b(?:PANAMA|PANAMÁ|FECHA|SEÑOR|GERENTE|BANCO)\b",
                bruto,
                flags=re.IGNORECASE
            )[0]

            codigo = limpiar_codigo_oficio(bruto)

            # Para validación de "fecha o número malo", evalúa solo la parte numérica
            solo_digitos = re.sub(r"\D", "", codigo)

            # Evita falsos positivos: si casi no hay dígitos, descarta
            if len(solo_digitos) < 3:
                continue

            # Reusa tu filtro existente sin romperlo:
            if codigo and not es_fecha_o_numero_malo(solo_digitos, l):
                candidatos.append((codigo, 20))

    # Candidatos generales: ahora también permiten letras (SEC/EXP) dentro
    # Busca secuencias "tipo oficio": empieza en dígito y luego mezcla separadores/letras/dígitos
    nums_generales = re.findall(r"\d[A-Z0-9/\-_.]{4,60}", l)

    for n in nums_generales:
        codigo = limpiar_codigo_oficio(n)
        solo_digitos = re.sub(r"\D", "", codigo)

        if len(solo_digitos) < 3:
            continue
        if es_fecha_o_numero_malo(solo_digitos, l):
            continue

        score = 3
        pos_num = l.find(n)
        pos_oficio = l.find("OFICIO")
        pos_sec = l.find("SEC")
        pos_exp = l.find("EXP")

        if pos_oficio != -1 and pos_num > pos_oficio:
            score += 5
        if pos_sec != -1 and pos_num < pos_sec:
            score += 4
        if pos_exp != -1 and pos_num < pos_exp:
            score += 4

        candidatos.append((codigo, score))

    if not candidatos:
        return None, 0

    # Preferir mayor score; si empatan, preferir el más "largo" y con más dígitos
    candidatos.sort(
        key=lambda x: (x[1], len(re.sub(r"\D", "", x[0])), len(x[0])),
        reverse=True
    )

    return candidatos[0]



def score_linea(linea, tokens_aprendidos):
    l = normalizar_linea(linea)

    score = 0

    # Base fuerte
    if "OFICIO" in l:
        score += 20

    if " NO " in f" {l} " or "Nº" in l:
        score += 5

    # Penalizaciones
    if "FECHA" in l:
        score -= 5

    if "PANAM" in l and re.search(r"\b20\d{2}\b", l):
        score -= 8

    if re.search(r"\b\d{1,2}\s+DE\s+[A-ZÁÉÍÓÚÑ]+\s+DE\s+20\d{2}\b", l):
        score -= 10

    # Número en línea
    candidato, score_num = extraer_candidato_de_linea(l)

    if candidato:
        score += score_num

    # Aprendizaje histórico
    tokens = tokens_de_linea(l)

    bonus_aprendido = 0

    for t in tokens:
        if t in tokens_aprendidos:
            bonus_aprendido += min(tokens_aprendidos[t], 5)

    # Limitar para que el aprendizaje no domine demasiado
    score += min(bonus_aprendido, 10)

    return score, candidato


def extraer_oficio_inteligente(texto):
    lineas_originales = texto.split("\n")
    tokens_aprendidos = obtener_tokens_aprendidos()

    mejor_linea = None
    mejor_numero = None
    mejor_score = -999

    candidatas_debug = []

    for linea in lineas_originales:
        linea_norm = normalizar_linea(linea)

        if not linea_norm:
            continue

        score, numero = score_linea(linea_norm, tokens_aprendidos)

        if numero:
            candidatas_debug.append((score, numero, linea_norm))

        if numero and score > mejor_score:
            mejor_score = score
            mejor_numero = numero
            mejor_linea = linea_norm

    print("\n--- CANDIDATAS ---")
    for s, n, l in sorted(candidatas_debug, reverse=True)[:5]:
        print(f"SCORE={s} | NUM={n} | LINEA={l}")
    print("------------------\n")

    return mejor_numero, mejor_linea, mejor_score


# =====================================================
# PROCESAMIENTO PRINCIPAL
# =====================================================

def procesar_carpeta(carpeta):
    archivos = [f for f in os.listdir(carpeta) if f.lower().endswith(".pdf")]
    total = len(archivos)

    resultados = []
    ok = 0
    warn = 0

    if total == 0:
        return ["No se encontraron PDFs en la carpeta seleccionada."]

    for i, archivo in enumerate(archivos, start=1):
        progress["value"] = (i / total) * 100
        ventana.update_idletasks()

        ruta_pdf = os.path.join(carpeta, archivo)

        try:
            img = pdf_a_imagen(ruta_pdf)
            img = recortar_encabezado(img)
            img = mejorar_imagen(img)

            texto = pytesseract.image_to_string(
                img,
                lang="spa+eng",
                config="--oem 3 --psm 6"
            )

            numero, linea_detectada, score = extraer_oficio_inteligente(texto)

            if numero:
                numero_archivo = normalizar_nombre_archivo(numero)

                # fallback por si quedara vacío tras limpiar
                if not numero_archivo:
                    numero_archivo = "SIN_NUMERO"

                nueva = os.path.join(carpeta, f"Oficio_{numero_archivo}.pdf")

                c = 1
                while os.path.exists(nueva):
                    nueva = os.path.join(carpeta, f"Oficio_{numero_archivo}_{c}.pdf")
                    c += 1

                os.replace(ruta_pdf, nueva)

                nuevo_nombre = os.path.basename(nueva)

                resultados.append(
                    f"[OK] {archivo} → {nuevo_nombre} | score={score}"
                )

                aprender_de_resultado(
                    archivo_original=archivo,
                    nuevo_nombre=nuevo_nombre,
                    numero=numero,
                    linea_detectada=linea_detectada,
                    score=score
                )

                ok += 1
            else:
                resultados.append(f"[WARN] {archivo} (no detectado)")
                warn += 1

        except Exception as e:
            resultados.append(f"[ERROR] {archivo} ({e})")

    resultados.append("")
    resultados.append("----------------------")
    resultados.append(f"Renombrados: {ok}")
    resultados.append(f"Sin coincidencia: {warn}")
    resultados.append(f"Historial guardado en: {HISTORIAL_FILE}")

    progress["value"] = 100
    return resultados


# =====================================================
# INTERFAZ
# =====================================================

def seleccionar_carpeta():
    carpeta = filedialog.askdirectory()

    if not carpeta:
        return

    resultado_texto.delete(1.0, tk.END)
    resultado_texto.insert(tk.END, "Procesando...\n")
    ventana.update()

    resultados = procesar_carpeta(carpeta)

    resultado_texto.delete(1.0, tk.END)

    for linea in resultados:
        resultado_texto.insert(tk.END, linea + "\n")

    messagebox.showinfo("Listo", "Proceso terminado")


# =====================================================
# GUI
# =====================================================

ventana = tk.Tk()
ventana.title("Renombrador de Oficios PRO")
ventana.geometry("850x620")

tk.Label(
    ventana,
    text="Selecciona carpeta de PDFs",
    font=("Arial", 12)
).pack(pady=10)

tk.Button(
    ventana,
    text="Seleccionar Carpeta",
    command=seleccionar_carpeta,
    bg="#4CAF50",
    fg="white",
    width=25
).pack(pady=5)

tk.Button(
    ventana,
    text="Configurar Tesseract",
    command=configurar_tesseract_manual,
    bg="#2196F3",
    fg="white",
    width=25
).pack(pady=5)

tk.Button(
    ventana,
    text="Ver Aprendizaje",
    command=ver_aprendizaje,
    bg="#795548",
    fg="white",
    width=25
).pack(pady=5)

tk.Button(
    ventana,
    text="Borrar Aprendizaje",
    command=borrar_aprendizaje,
    bg="#F44336",
    fg="white",
    width=25
).pack(pady=5)

progress = ttk.Progressbar(
    ventana,
    length=600,
    mode="determinate"
)
progress.pack(pady=10)

resultado_texto = tk.Text(ventana, wrap="word")
resultado_texto.pack(expand=True, fill="both", padx=10, pady=10)

setup_tesseract()

ventana.mainloop()
