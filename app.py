import gradio as gr
import os
import shutil
import subprocess
import tempfile
import re
import unicodedata
from pathlib import Path
from bs4 import BeautifulSoup
from PIL import Image
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

BASE_DIR = Path("C:/dev").resolve()

# Utilidades ---------------

def normalize_title_to_folder(title: str) -> str:
    """Convierte el título de la app a un nombre válido de carpeta.
    Ejemplo: 'Hola Martín' -> 'hola-martin'
    """
    # Normalizar caracteres acentuados
    normalized = unicodedata.normalize('NFD', title)
    # Remover diacríticos (acentos)
    without_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    # Convertir a minúsculas
    lowercase = without_accents.lower()
    # Reemplazar espacios y caracteres especiales con guiones
    folder_name = re.sub(r'[^a-z0-9]+', '-', lowercase)
    # Remover guiones al inicio y final
    folder_name = folder_name.strip('-')
    return folder_name

def validate_app_title(title: str) -> tuple[bool, str]:
    """Valida que el título de la app no contenga caracteres prohibidos.
    Permite letras acentuadas pero no caracteres especiales problemáticos.
    """
    if not title or not title.strip():
        return False, "El título no puede estar vacío"
    
    # Permitir letras (incluidas acentuadas), números, espacios y algunos símbolos básicos
    allowed_pattern = r'^[\w\s\u00C0-\u024F\u1E00-\u1EFF._-]+$'
    if not re.match(allowed_pattern, title.strip()):
        return False, "El título contiene caracteres no válidos. Solo se permiten letras, números, espacios, puntos, guiones y guiones bajos"
    
    return True, ""

def run(cmd, cwd=None):
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, shell=True)
    out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, out.strip()

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def remove_dir(p: Path):
    try:
        shutil.rmtree(p, ignore_errors=True)
    except Exception:
        pass

def insert_head_meta_and_title(html_bytes: bytes, app_title: str) -> bytes:
    soup = BeautifulSoup(html_bytes, "lxml")

    # Garantizar <html><head><body>
    if soup.html is None:
        html_tag = soup.new_tag("html")
        soup.append(html_tag)
    if soup.head is None:
        head_tag = soup.new_tag("head")
        soup.html.insert(0, head_tag)
    if soup.body is None:
        body_tag = soup.new_tag("body")
        soup.html.append(body_tag)

    head = soup.head

    # <title>
    if head.title:
        head.title.string = app_title
    else:
        title_tag = soup.new_tag("title")
        title_tag.string = app_title
        head.append(title_tag)

    # Bloque de metas (en el orden solicitado)
    metas_html = """
<meta charset="utf-8">
<!--
Customize this policy to fit your own app's needs. For more guidance, please refer to the docs:
    https://cordova.apache.org/docs/en/latest/
Some notes:
    * https://ssl.gstatic.com is required only on Android and is needed for TalkBack to function properly
    * Disables use of inline scripts in order to mitigate risk of XSS vulnerabilities. To change this:
        * Enable inline JS: add 'unsafe-inline' to default-src
-->
<meta http-equiv="Content-Security-Policy" content="default-src 'self' data: https://ssl.gstatic.com 'unsafe-eval'; style-src 'self' 'unsafe-inline'; media-src *; img-src 'self' data: content:;">
<meta name="format-detection" content="telephone=no">
<meta name="msapplication-tap-highlight" content="no">
<meta name="viewport" content="initial-scale=1, width=device-width, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
""".strip()

    metas_soup = BeautifulSoup(metas_html, "lxml")
    # Insertar justo antes de </head>
    for el in metas_soup.find_all():
        head.append(el)

    # Insertar <script src="cordova.js"></script> antes del primer <script> del documento
    cordova_tag = soup.new_tag("script", src="cordova.js")

    first_script = soup.find("script")
    if first_script:
        first_script.insert_before(cordova_tag)
    else:
        # si no hay scripts, lo agregamos al final del head
        head.append(cordova_tag)

    # Envolver JS inline en deviceready
    inline_scripts = soup.find_all("script", src=False)
    for sc in inline_scripts:
        code = (sc.string or "").strip()
        if not code:
            continue
        wrapped = (
            "document.addEventListener('deviceready', onDeviceReady, false);\n\n"
            "function onDeviceReady() {\n"
            + code + "\n}\n"
        )
        sc.string = wrapped

    return soup.encode(formatter="html")

def patch_config_xml(config_path: Path):
    xml_text = config_path.read_text(encoding="utf-8", errors="ignore")
    block = """
    <platform name="android">
        <icon src="resources/android/icon/drawable-xxxhdpi-icon.png" density="xxxhdpi"/>
        <icon src="resources/android/icon/drawable-xxhdpi-icon.png" density="xxhdpi"/>
        <icon src="resources/android/icon/drawable-xhdpi-icon.png" density="xhdpi"/>
        <icon src="resources/android/icon/drawable-hdpi-icon.png" density="hdpi"/>
        <icon src="resources/android/icon/drawable-mdpi-icon.png" density="mdpi"/>
    </platform>
""".rstrip()

    if "</widget>" in xml_text and "platform name=\"android\"" not in xml_text:
        xml_text = xml_text.replace("</widget>", f"{block}\n</widget>")
        config_path.write_text(xml_text, encoding="utf-8")

def save_icon_512(icon_file, resources_dir: Path):
    ensure_dir(resources_dir)
    out = resources_dir / "icon.png"
    with Image.open(icon_file.name) as im:
        im = im.convert("RGBA")
        im = im.resize((512, 512))
        im.save(out, format="PNG")
    return out

# Flujo principal ---------------

def build_cordova(html_file, app_title, icon_image):
    logs = []
    try:
        # Validar título de la app
        is_valid, error_msg = validate_app_title(app_title)
        if not is_valid:
            return f"ERROR: {error_msg}"

        if html_file is None:
            return "ERROR: Debes subir un archivo .html."

        if icon_image is None:
            return "ERROR: Debes subir un icono (imagen) para generar resources/icon.png."

        # Generar nombre de carpeta desde el título
        project_folder = normalize_title_to_folder(app_title.strip())
        proj_dir = BASE_DIR / project_folder
        app_id = f"com.oneclicksoftwaresolutions.{project_folder}"
        
        # Cargar configuración del keystore desde .env
        keystore_path = os.getenv('KEYSTORE_PATH')
        keystore_alias = os.getenv('KEYSTORE_ALIAS')
        keystore_password = os.getenv('KEYSTORE_PASSWORD')
        
        if not keystore_path or not keystore_alias or not keystore_password:
            return "ERROR: Falta configuración del keystore en el archivo .env"

        # 1) cordova create
        cmd_create = f'cordova create "{project_folder}" "{app_id}" "{app_title}"'
        code, out = run(cmd_create, cwd=str(BASE_DIR))
        logs.append(f"$ {cmd_create}\n{out}")
        if code != 0:
            return "\n\n".join(logs)

        # 2) cordova platform add android@latest
        cmd_platform = 'cordova platform add android@latest'
        code, out = run(cmd_platform, cwd=str(proj_dir))
        logs.append(f"$ {cmd_platform}\n{out}")
        if code != 0:
            return "\n\n".join(logs)

        # 3) Reemplazar www/index.html
        www_dir = proj_dir / "www"
        ensure_dir(www_dir)
        index_path = www_dir / "index.html"

        # Cargar HTML subido y transformarlo
        html_bytes = Path(html_file.name).read_bytes()
        html_bytes = insert_head_meta_and_title(html_bytes, app_title)

        # Guardar nuevo index.html
        index_path.write_bytes(html_bytes)
        logs.append(f"✔ index.html reemplazado en {index_path}")

        # 4) Borrar www/css, www/js, www/img
        for sub in ["css", "js", "img"]:
            remove_dir(www_dir / sub)
        logs.append("✔ Carpetas www/css, www/js, www/img eliminadas")

        # 5) Crear resources/icon.png (512x512)
        resources_dir = proj_dir / "resources"
        icon_out = save_icon_512(icon_image, resources_dir)
        logs.append(f"✔ Icono generado: {icon_out}")

        # 6) cordova-res (íconos Android)
        cmd_res = "cordova-res android --skip-config" #"cordova-res --skip-config --skip-splash --platform android"
        code, out = run(cmd_res, cwd=str(proj_dir))
        logs.append(f"$ {cmd_res}\n{out}")
        #if code != 0:
        #    logs.append("⚠ cordova-res devolvió error (revisa que esté instalado en PATH).")

        # 7) Editar config.xml con <platform name="android">…</platform>
        config_xml = proj_dir / "config.xml"
        if config_xml.exists():
            patch_config_xml(config_xml)
            logs.append("✔ config.xml actualizado con íconos Android")
        else:
            logs.append("⚠ No se encontró config.xml para parchear.")

        # 8) Build release
        cmd_build = "cordova build android --release"
        code, out = run(cmd_build, cwd=str(proj_dir))
        logs.append(f"$ {cmd_build}\n{out}")
        if code != 0:
            return "\n\n".join(logs)

        # 9) Copiar AAB a C:/dev/app-release.aab
        aab_path = proj_dir / "platforms" / "android" / "app" / "build" / "outputs" / "bundle" / "release" / "app-release.aab"
        if not aab_path.exists():
            # ruta alternativa por si cambia el layout
            alt = list((proj_dir / "platforms").rglob("app-release.aab"))
            if alt:
                aab_path = alt[0]
        if not aab_path.exists():
            logs.append("❌ No encontré el app-release.aab después del build.")
            return "\n\n".join(logs)

        target_aab = BASE_DIR / "app-release.aab"
        shutil.copy2(aab_path, target_aab)
        logs.append(f"✔ Copiado AAB a {target_aab}")

        # 10) jarsigner
        keystore_path_obj = Path(keystore_path).resolve()
        if not keystore_path_obj.exists():
            return "\n\n".join(logs + [f"❌ Keystore no existe: {keystore_path_obj}"])

        alias = keystore_alias.strip()

        # jarsigner permite pasar -storepass (ojo: se mostrará en procesos del SO mientras corre)
        cmd_jarsigner = (
            f'jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 '
            f'-keystore "{keystore_path_obj}" -storepass "{keystore_password}" "{target_aab}" {alias}'
        )
        code, out = run(cmd_jarsigner, cwd=str(BASE_DIR))
        logs.append(f"$ {cmd_jarsigner}\n{out}")
        if code != 0:
            logs.append("❌ Error al firmar con jarsigner.")
            return "\n\n".join(logs)

        logs.append("🎉 ¡Listo! AAB firmado.")
        return "\n\n".join(logs)

    except Exception as e:
        logs.append(f"ERROR: {e}")
        return "\n\n".join(logs)


# Interfaz Gradio ---------------
with gr.Blocks(title="Icecream - Cordova Builder") as demo:
    gr.Markdown("## Icecream · Generador Cordova Android (release)")

    with gr.Row():
        html_file = gr.File(label="Sube tu HTML (se convertirá en www/index.html)", file_types=[".html"])
        icon_image = gr.File(label="Icono del app (cualquier imagen, se redimensiona a 512x512)", file_types=["image"])

    app_title = gr.Textbox(label="Título de la App", placeholder="Mi App Cordova", info="El nombre de la carpeta se generará automáticamente basado en este título")

    run_btn = gr.Button("Crear, preparar, compilar y firmar")
    output = gr.Textbox(label="Log", lines=25)

    run_btn.click(
        fn=build_cordova,
        inputs=[html_file, app_title, icon_image],
        outputs=[output]
    )

if __name__ == "__main__":
    demo.launch()
