import os
import re
import sys
import logging
import threading
from pathlib import Path
from typing import Optional

import pytesseract
import fitz  # PyMuPDF
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from PIL import Image, ImageEnhance, ImageFilter

# ─────────────────────────────────────────────────────────
# Logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# PyInstaller support

def recurso_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)


# ─────────────────────────────────────────────────────────
# Tesseract discovery

def encontrar_tesseract() -> Optional[str]:
    rutas = [
        recurso_path("tesseract/tesseract.exe"),
        os.path.join(os.getcwd(), "tesseract", "tesseract.exe"),
        r"C:\Users\gclair\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
    ]
    for ruta in rutas:
        if os.path.exists(ruta):
            log.info("Tesseract encontrado: %s", ruta)
            return ruta
    return None


def configurar_tesseract() -> bool:
    """Intenta configurar Tesseract; devuelve True si tiene éxito."""
    ruta = encontrar_tesseract()
    if ruta:
        pytesseract.pytesseract.tesseract_cmd = ruta
        return True
    # En Linux/macOS Tesseract suele estar en el PATH — probamos con un ping
    try:
        pytesseract.get_tesseract_version()
        log.info("Tesseract disponible desde el PATH del sistema.")
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────
# Procesamiento de imagen

def mejorar_imagen(img: Image.Image) -> Image.Image:
    img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def recortar_encabezado(img: Image.Image) -> Image.Image:
    ancho, alto = img.size
    return img.crop((0, 0, ancho, int(alto * 0.4)))


# ─────────────────────────────────────────────────────────
# OCR y extracción

def normalizar_texto(texto: str) -> str:
    texto = texto.upper().replace("\n", " ")
    texto = re.sub(r"\s+", " ", texto)
    texto = texto.replace("N°", "Nº").replace("N8", "Nº")
    return texto


_PATRON_OFICIO = re.compile(r"O\s*F\s*I\s*C\s*I\s*O.*?(\d{2,6})", re.IGNORECASE)


def extraer_oficio(texto: str) -> Optional[str]:
    log.debug("Texto OCR (primeros 300 chars): %s", texto[:300])
    match = _PATRON_OFICIO.search(texto)
    return match.group(1) if match else None


def buscar_por_proximidad(texto: str) -> Optional[str]:
    palabras = texto.split()
    for i, palabra in enumerate(palabras):
        if "OFICIO" in palabra:
            ventana = palabras[i + 1 : min(i + 8, len(palabras))]
            for candidato in ventana:
                solo_digitos = re.sub(r"\D", "", candidato)
                if solo_digitos.isdigit() and 2 <= len(solo_digitos) <= 6:
                    return solo_digitos
    return None


# ─────────────────────────────────────────────────────────
# PDF → imagen

def pdf_a_imagen(ruta_pdf: str) -> Image.Image:
    doc = fitz.open(ruta_pdf)
    try:
        pagina = doc[0]
        mat = fitz.Matrix(2, 2)
        pix = pagina.get_pixmap(matrix=mat)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    finally:
        doc.close()


# ─────────────────────────────────────────────────────────
# Procesamiento de carpeta

def nombre_unico(carpeta: str, nombre_base: str) -> str:
    """Genera un nombre de archivo que no exista en carpeta."""
    ruta = os.path.join(carpeta, nombre_base)
    if not os.path.exists(ruta):
        return nombre_base
    stem = Path(nombre_base).stem
    ext = Path(nombre_base).suffix
    contador = 1
    while True:
        candidato = f"{stem}_{contador}{ext}"
        if not os.path.exists(os.path.join(carpeta, candidato)):
            return candidato
        contador += 1


def procesar_archivo(ruta_pdf: str, carpeta: str) -> str:
    """Procesa un PDF y lo renombra. Devuelve la línea de resultado."""
    archivo = os.path.basename(ruta_pdf)
    img = None
    try:
        img = pdf_a_imagen(ruta_pdf)
        img = recortar_encabezado(img)
        img = mejorar_imagen(img)

        texto = pytesseract.image_to_string(img, lang="spa", config="--oem 3 --psm 11")
        texto = normalizar_texto(texto)

        numero = extraer_oficio(texto) or buscar_por_proximidad(texto)

        if numero:
            nuevo_nombre = nombre_unico(carpeta, f"Oficio_{numero}.pdf")
            os.rename(ruta_pdf, os.path.join(carpeta, nuevo_nombre))
            return f"[OK]   {archivo} → {nuevo_nombre}"
        return f"[WARN] {archivo} — número de oficio no detectado"

    except fitz.FileDataError as exc:
        return f"[ERROR] {archivo} — PDF corrupto o inválido: {exc}"
    except pytesseract.TesseractError as exc:
        return f"[ERROR] {archivo} — fallo OCR: {exc}"
    except PermissionError:
        return f"[ERROR] {archivo} — sin permiso para renombrar el archivo"
    except OSError as exc:
        return f"[ERROR] {archivo} — error de sistema: {exc}"
    except Exception as exc:
        log.exception("Error inesperado procesando %s", archivo)
        return f"[ERROR] {archivo} — error inesperado: {exc}"
    finally:
        if img is not None:
            img.close()


def procesar_carpeta(
    carpeta: str,
    progreso_cb=None,
    cancelado_cb=None,
) -> list[str]:
    """
    Procesa todos los PDFs en carpeta.

    progreso_cb(porcentaje: float) — actualiza barra de progreso
    cancelado_cb() → bool          — devuelve True si el usuario canceló
    """
    archivos = sorted(f for f in os.listdir(carpeta) if f.lower().endswith(".pdf"))
    total = len(archivos)

    if total == 0:
        return ["[INFO] No se encontraron archivos PDF en la carpeta seleccionada."]

    resultados: list[str] = []
    encontrados = no_encontrados = errores = 0

    for i, archivo in enumerate(archivos, start=1):
        if cancelado_cb and cancelado_cb():
            resultados.append("\n[CANCELADO] Proceso interrumpido por el usuario.")
            break

        if progreso_cb:
            progreso_cb((i - 1) / total * 100)

        ruta_pdf = os.path.join(carpeta, archivo)
        linea = procesar_archivo(ruta_pdf, carpeta)
        resultados.append(linea)
        log.info(linea)

        if linea.startswith("[OK]"):
            encontrados += 1
        elif linea.startswith("[WARN]"):
            no_encontrados += 1
        else:
            errores += 1

    if progreso_cb:
        progreso_cb(100)

    resultados += [
        "",
        "─" * 40,
        f"Total procesados : {min(i, total)} / {total}",
        f"Renombrados      : {encontrados}",
        f"Sin coincidencia : {no_encontrados}",
        f"Errores          : {errores}",
    ]
    return resultados


# ─────────────────────────────────────────────────────────
# GUI

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Renombrador de Oficios PRO")
        self.geometry("800x580")
        self.resizable(True, True)
        self.minsize(600, 400)

        self._cancelado = threading.Event()
        self._procesando = False
        self._tesseract_ok = False

        self._construir_ui()
        self.after(100, self._verificar_tesseract)

    # ── construcción ──────────────────────────────────────

    def _construir_ui(self):
        top = tk.Frame(self, padx=10, pady=8)
        top.pack(fill="x")

        tk.Label(top, text="Renombrador de Oficios", font=("Arial", 13, "bold")).pack(side="left")

        self.btn_cancelar = tk.Button(
            top, text="Cancelar", command=self._cancelar,
            bg="#f44336", fg="white", font=("Arial", 10),
            padx=8, pady=4, state="disabled",
        )
        self.btn_cancelar.pack(side="right", padx=4)

        self.btn_exportar = tk.Button(
            top, text="Exportar log", command=self._exportar,
            bg="#2196F3", fg="white", font=("Arial", 10),
            padx=8, pady=4, state="disabled",
        )
        self.btn_exportar.pack(side="right", padx=4)

        self.btn_seleccionar = tk.Button(
            top, text="Seleccionar Carpeta",
            command=self._seleccionar_carpeta,
            bg="#4CAF50", fg="white", font=("Arial", 11),
            padx=10, pady=5,
        )
        self.btn_seleccionar.pack(side="right", padx=4)

        self.lbl_estado = tk.Label(self, text="Listo", anchor="w", font=("Arial", 9))
        self.lbl_estado.pack(fill="x", padx=10)

        self.progress = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=10, pady=(2, 6))

        frame_texto = tk.Frame(self)
        frame_texto.pack(expand=True, fill="both", padx=10, pady=(0, 10))

        scroll_y = tk.Scrollbar(frame_texto, orient="vertical")
        scroll_y.pack(side="right", fill="y")
        scroll_x = tk.Scrollbar(frame_texto, orient="horizontal")
        scroll_x.pack(side="bottom", fill="x")

        self.resultado_texto = tk.Text(
            frame_texto, wrap="none",
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            font=("Courier New", 9),
        )
        self.resultado_texto.pack(expand=True, fill="both")
        scroll_y.config(command=self.resultado_texto.yview)
        scroll_x.config(command=self.resultado_texto.xview)

        # Colores por tipo de línea
        self.resultado_texto.tag_config("ok",    foreground="#2e7d32")
        self.resultado_texto.tag_config("warn",  foreground="#e65100")
        self.resultado_texto.tag_config("error", foreground="#c62828")
        self.resultado_texto.tag_config("info",  foreground="#1565c0")

    # ── verificación de Tesseract ──────────────────────────

    def _verificar_tesseract(self):
        self._tesseract_ok = configurar_tesseract()
        if not self._tesseract_ok:
            self._log_ui(
                "[ERROR] Tesseract no encontrado. Instálalo o coloca tesseract.exe "
                "en la subcarpeta 'tesseract/'.\n",
                tag="error",
            )
            self.btn_seleccionar.config(state="disabled")
            messagebox.showerror(
                "Tesseract no encontrado",
                "No se encontró el ejecutable de Tesseract OCR.\n\n"
                "Instálalo desde: https://github.com/tesseract-ocr/tesseract\n"
                "o coloca tesseract.exe en la carpeta 'tesseract/' junto al programa.",
            )
        else:
            self._log_ui("[INFO] Tesseract OCR listo.\n", tag="info")

    # ── acciones de UI ────────────────────────────────────

    def _seleccionar_carpeta(self):
        if not self._tesseract_ok:
            messagebox.showerror("Error", "Tesseract no está disponible.")
            return

        carpeta = filedialog.askdirectory(title="Selecciona la carpeta con los PDFs")
        if not carpeta:
            return

        self._iniciar_procesamiento(carpeta)

    def _iniciar_procesamiento(self, carpeta: str):
        self._procesando = True
        self._cancelado.clear()
        self.btn_seleccionar.config(state="disabled")
        self.btn_cancelar.config(state="normal")
        self.btn_exportar.config(state="disabled")
        self.progress["value"] = 0
        self.resultado_texto.delete("1.0", tk.END)
        self._set_estado(f"Procesando: {carpeta}")

        hilo = threading.Thread(
            target=self._hilo_procesar,
            args=(carpeta,),
            daemon=True,
        )
        hilo.start()

    def _hilo_procesar(self, carpeta: str):
        try:
            resultados = procesar_carpeta(
                carpeta,
                progreso_cb=self._actualizar_progreso,
                cancelado_cb=lambda: self._cancelado.is_set(),
            )
            self.after(0, self._mostrar_resultados, resultados)
        except Exception as exc:
            log.exception("Error crítico en hilo de procesamiento.")
            self.after(0, self._mostrar_error_critico, str(exc))

    def _cancelar(self):
        self._cancelado.set()
        self._set_estado("Cancelando...")
        self.btn_cancelar.config(state="disabled")

    def _exportar(self):
        contenido = self.resultado_texto.get("1.0", tk.END).strip()
        if not contenido:
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Archivo de texto", "*.txt"), ("Todos", "*.*")],
            title="Guardar log",
        )
        if not ruta:
            return
        try:
            Path(ruta).write_text(contenido, encoding="utf-8")
            messagebox.showinfo("Exportado", f"Log guardado en:\n{ruta}")
        except OSError as exc:
            messagebox.showerror("Error al exportar", str(exc))

    # ── callbacks desde hilo ──────────────────────────────

    def _actualizar_progreso(self, valor: float):
        self.after(0, lambda: self.progress.configure(value=valor))

    def _mostrar_resultados(self, resultados: list[str]):
        self._procesando = False
        self.btn_seleccionar.config(state="normal")
        self.btn_cancelar.config(state="disabled")
        self.btn_exportar.config(state="normal")
        self.progress["value"] = 100

        for linea in resultados:
            tag = ""
            if linea.startswith("[OK]"):
                tag = "ok"
            elif linea.startswith("[WARN]"):
                tag = "warn"
            elif linea.startswith("[ERROR]"):
                tag = "error"
            elif linea.startswith("[INFO]") or linea.startswith("[CANCELADO]"):
                tag = "info"
            self._log_ui(linea + "\n", tag=tag)

        self._set_estado("Proceso terminado.")
        messagebox.showinfo("Listo", "Proceso terminado.")

    def _mostrar_error_critico(self, mensaje: str):
        self._procesando = False
        self.btn_seleccionar.config(state="normal")
        self.btn_cancelar.config(state="disabled")
        self._log_ui(f"[ERROR CRÍTICO] {mensaje}\n", tag="error")
        self._set_estado("Error crítico.")
        messagebox.showerror("Error crítico", mensaje)

    # ── utilidades ────────────────────────────────────────

    def _log_ui(self, texto: str, tag: str = ""):
        self.resultado_texto.insert(tk.END, texto, tag)
        self.resultado_texto.see(tk.END)

    def _set_estado(self, texto: str):
        self.lbl_estado.config(text=texto)


# ─────────────────────────────────────────────────────────
# Entry point

if __name__ == "__main__":
    app = App()
    app.mainloop()
