"""La IA del usuario (Claude Code, Codex o Gemini), con su propia cuenta. Solo biblioteca estándar.

Corta nunca llama a una IA con una cuenta propia: arma el comando del CLI que la persona ya tiene instalado y le pasa el texto.
La IA corre en una carpeta temporal y en modo solo lectura: ve únicamente lo que le mandamos.
"""
import os
import shutil
import subprocess
import tempfile

import proyecto as datos

HOME = os.path.expanduser("~")


def _preparar_path():
    """La app no hereda el PATH de la terminal: agrega donde suelen quedar los CLI de IA (Mac, Linux y Windows)."""
    extra = [os.path.join(HOME, ".local", "bin"), os.path.join(HOME, ".claude", "local"), os.path.join(HOME, ".npm-global", "bin"),
             os.path.join(HOME, ".volta", "bin"), os.path.join(HOME, ".bun", "bin"), os.path.join(HOME, ".codex", "bin"),
             "/opt/homebrew/bin", "/usr/local/bin"]
    nvm = os.path.join(HOME, ".nvm", "versions", "node")
    if os.path.isdir(nvm):
        extra += [os.path.join(nvm, v, "bin") for v in sorted(os.listdir(nvm), reverse=True)]
    if os.name == "nt":
        extra += [os.path.join(os.environ.get("APPDATA", ""), "npm"), os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "claude")]
    os.environ["PATH"] = os.pathsep.join([os.environ.get("PATH", "")] + [d for d in extra if os.path.isdir(d)])


_preparar_path()

#: id → (comandos posibles, nombre visible). Gemini: Antigravity CLI (`agy`) o el Gemini CLI antiguo.
IAS = {"claude": (("claude",), "Claude"), "codex": (("codex",), "ChatGPT (Codex)"), "gemini": (("agy", "gemini"), "Gemini")}


def elegida():
    ia = datos.config().get("ia")
    return ia if ia in IAS else "claude"


def nombre():
    return IAS[elegida()][1]


def ejecutar_ia(prompt, timeout=600):
    """Le pasa el prompt a la IA del usuario y devuelve un CompletedProcess (stdout = respuesta)."""
    ia = elegida()
    comando = next((r for r in map(shutil.which, IAS[ia][0]) if r), IAS[ia][0][0])
    with tempfile.TemporaryDirectory(prefix="corta-ia-") as tmp:
        if ia == "codex":
            salida = os.path.join(tmp, "respuesta.txt")
            cmd = [comando, "exec", "--skip-git-repo-check", "-s", "read-only", "-C", tmp, "-o", salida, "-"]
            r = subprocess.run(cmd, input=prompt, text=True, encoding="utf-8", capture_output=True, timeout=timeout, cwd=tmp)
            texto = open(salida, encoding="utf-8").read() if os.path.exists(salida) else ""
            return subprocess.CompletedProcess(cmd, r.returncode, texto, r.stderr)
        es_agy = os.path.basename(comando).lower().split(".")[0] in ("agy", "antigravity")
        if ia == "gemini" and es_agy:
            # Prompts largos en un archivo: la línea de comandos tiene límite.
            if len(prompt) < 20000:
                pedido = prompt
            else:
                with open(os.path.join(tmp, "instrucciones.md"), "w", encoding="utf-8") as f:
                    f.write(prompt)
                pedido = ("Lee el archivo instrucciones.md de esta carpeta y haz exactamente lo que pide. "
                          "Entrega solo el resultado pedido, sin comentarios. No modifiques ni crees archivos.")
            cmd = [comando, "--output-format", "text", "--sandbox", "--add-dir", tmp, "-p", pedido]
            return subprocess.run(cmd, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", capture_output=True, timeout=timeout, cwd=tmp)
        if ia == "gemini":
            cmd = [comando, "-p", "Responde a las instrucciones de arriba. Entrega solo el resultado pedido.", "-o", "text"]
        else:
            cmd = [comando, "-p", "--output-format", "text"]
        return subprocess.run(cmd, input=prompt, text=True, encoding="utf-8", capture_output=True, timeout=timeout, cwd=tmp)


def preguntar(prompt, timeout=600):
    """Devuelve (texto, error). El error es un mensaje para la persona, con el nombre de su IA."""
    try:
        r = ejecutar_ia(prompt, timeout)
    except FileNotFoundError:
        return "", f"No encontré {nombre()} en este computador. Revisa en Ajustes → Tu IA."
    except subprocess.TimeoutExpired:
        return "", f"{nombre()} se demoró demasiado en responder. Inténtalo de nuevo."
    if r.returncode != 0 or not (r.stdout or "").strip():
        detalle = (r.stderr or "").strip().splitlines()[-1:] or [""]
        return "", f"{nombre()} no respondió. {detalle[0]}".strip()
    return r.stdout, ""
