import tkinter as tk
import zipfile, shutil
import sys, subprocess, shlex
import webbrowser, platform
import urllib.request
from pathlib import Path
from tkinter import ttk, messagebox


# =========================
# CONFIG PATHS
# =========================
def get_root_dir():
    """
    Returns the root directory of the application.
    Supports both PyInstaller bundles and normal script mode.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

# The folder where Lite-Brain will be installed, regardless of where the .exe file is located.
LAUNCHER_DIR = get_root_dir()
WORKDIR = Path.home() / ".lite_brain"
REPO_DIR = WORKDIR / "Lite-Brain"

# GitHub ZIP URL for the prod branch (no Git required)
ZIP_URL = "https://github.com/nixiz0/Lite-Brain/archive/refs/heads/prod.zip"

# These variables will be *updated* once the project is unpacked.
ROOT_DIR = LAUNCHER_DIR
SERVICES_DIR = ROOT_DIR / "services"
ENV_SOURCE = SERVICES_DIR / "env"          # Template .env
ENV_TARGET = SERVICES_DIR / ".env"         # Generated/updated .env
COMPOSE_FILE_YML = SERVICES_DIR / "docker-compose.yml"
COMPOSE_FILE_YAML = SERVICES_DIR / "docker-compose.yaml"
APP_URL = "http://localhost:9010"
PROJECT_NAME = "lite_brain"

def set_root_dir(new_root: Path):
    """
    Updates ROOT_DIR and all dependent paths
    to point to the Lite-Brain folder.
    """
    global ROOT_DIR, SERVICES_DIR, ENV_SOURCE, ENV_TARGET, COMPOSE_FILE_YML, COMPOSE_FILE_YAML

    ROOT_DIR = new_root
    SERVICES_DIR = ROOT_DIR / "services"
    ENV_SOURCE = SERVICES_DIR / "env"
    ENV_TARGET = SERVICES_DIR / ".env"
    COMPOSE_FILE_YML = SERVICES_DIR / "docker-compose.yml"
    COMPOSE_FILE_YAML = SERVICES_DIR / "docker-compose.yaml"


# =========================
# ZIP / REPO BOOTSTRAP (NO GIT)
# =========================
def ensure_repo_cloned() -> Path:
    """
    Ensure Lite-Brain is installed in ~/.lite_brain/Lite-Brain.

    - If ~/.lite_brain/Lite-Brain already exists and looks valid → just return it
    - Otherwise:
        - download the prod ZIP from GitHub
        - unzip in WORKDIR
        - move the folder to ~/.lite_brain/Lite-Brain
    """
    # If already installed and 'services' exists → no download, just use it
    if REPO_DIR.exists() and (REPO_DIR / "services").exists():
        return REPO_DIR

    WORKDIR.mkdir(parents=True, exist_ok=True)
    zip_path = WORKDIR / "lite-brain-prod.zip"

    # 1) Download ZIP
    try:
        urllib.request.urlretrieve(ZIP_URL, str(zip_path))
    except Exception as e:
        raise RuntimeError(
            "Failed to download Lite-Brain archive.\n"
            "Check your internet connection.\n\n"
            f"Detail: {e}"
        )

    # 2) Extract ZIP into WORKDIR, detect root folder, move to REPO_DIR
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(WORKDIR)
            # GitHub zip creates a top-level folder like Lite-Brain-prod or Lite-Brain-<hash>
            root_names = [
                Path(name).parts[0]
                for name in zf.namelist()
                if name and not name.endswith("/")
            ]

        if not root_names:
            raise RuntimeError("Downloaded archive appears to be empty.")

        src_root = WORKDIR / root_names[0]

        # If an old install exists, remove it (corrupted/old)
        if REPO_DIR.exists():
            shutil.rmtree(REPO_DIR)

        shutil.move(str(src_root), str(REPO_DIR))
    except Exception as e:
        raise RuntimeError(
            "Failed to extract Lite-Brain archive.\n"
            f"Detail: {e}"
        )
    finally:
        # Clean zip file if possible
        try:
            if zip_path.exists():
                zip_path.unlink()
        except Exception:
            pass

    return REPO_DIR


# =========================
# PARSING ENV
# =========================
def parse_env_file(path: Path):
    """
    Parses a .env-like file while preserving:
    - comments
    - blank lines
    - key=value pairs

    Also builds "sections" based on comment markers found in the file.
    The sections help group variables inside the UI.
    """
    text = path.read_text(encoding="utf-8")
    raw_lines = text.splitlines()

    parsed = []
    sections = {}
    order_of_sections = []

    current_section = "Général"
    sections.setdefault(current_section, [])
    order_of_sections.append(current_section)

    for line in raw_lines:
        stripped = line.strip()

        # Detect section changes based on comment markers in the template
        if stripped.startswith("#"):
            if "UI ENV CONFIG" in stripped:
                current_section = "UI"
            elif "ML ENV CONFIG" in stripped:
                current_section = "ML"
            elif "OLLAMA" in stripped:
                current_section = "OLLAMA"

            sections.setdefault(current_section, [])
            if current_section not in order_of_sections:
                order_of_sections.append(current_section)

            parsed.append({"type": "comment", "text": line})

        # Parse key=value pairs
        elif "=" in line and not stripped.startswith("#"):
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            parsed.append({
                "type": "var",
                "key": key,
                "value": value,
                "section": current_section
            })
            sections.setdefault(current_section, [])
            sections[current_section].append(key)

        else:
            # Preserve blank lines
            parsed.append({"type": "blank", "text": line})

    # Keep only sections containing variables
    clean_sections = {
        sec: keys for sec, keys in sections.items() if len(keys) > 0
    }
    clean_order = [s for s in order_of_sections if s in clean_sections]

    return parsed, clean_sections, clean_order


def rebuild_env_text(parsed_lines, values_by_key):
    """
    Reconstructs the .env file using the parsed structure
    and any updated variable values.
    Preserves comments + blank lines + ordering.
    """
    output_lines = []
    for item in parsed_lines:
        if item["type"] == "var":
            key = item["key"]
            new_value = values_by_key.get(key, item["value"])
            output_lines.append(f"{key}={new_value}")
        else:
            output_lines.append(item["text"])

    return "\n".join(output_lines) + "\n"


def load_template_and_current_values():
    """
    Loads settings from the template (source of truth),
    then overrides them using the existing .env if present.

    Returns:
    - parsed template structure
    - sections
    - section order
    - final values to display in UI
    """
    parsed_template, sections, sections_order = parse_env_file(ENV_SOURCE)

    # Defaults come from template
    values_by_key = {
        item["key"]: item["value"]
        for item in parsed_template if item["type"] == "var"
    }

    # Override with existing .env values
    if ENV_TARGET.exists():
        parsed_current, _, _ = parse_env_file(ENV_TARGET)
        current_values = {
            item["key"]: item["value"]
            for item in parsed_current if item["type"] == "var"
        }

        # Keep unknown keys instead of dropping them
        for k, v in current_values.items():
            values_by_key[k] = v

    return parsed_template, sections, sections_order, values_by_key


# =========================
# GPU DETECTION
# =========================
def detect_cuda_devices():
    """
    Detects available CUDA GPUs via nvidia-smi.
    Returns a list like ['cuda:0', 'cuda:1'] or empty if none.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            return []

        lines = [l for l in result.stdout.splitlines() if "GPU" in l]
        return [f"cuda:{i}" for i in range(len(lines))]
    except Exception:
        return []


# =========================
# DOCKER HELPERS
# =========================
def check_docker():
    """
    Verifies that Docker is installed and accessible in PATH.
    Raises RuntimeError if unavailable.
    """
    try:
        result = subprocess.run(
            "docker --version",
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)
    except Exception as e:
        # Message in English by default (also used in non-UI mode)
        raise RuntimeError(
            "Docker not installed or not available in PATH.\n"
            "Install Docker Desktop and restart the launcher.\n\n"
            f"Detail: {e}"
        )


def get_compose_cmd():
    """
    Detects the correct docker compose command (v2 or v1)
    and returns a fully resolved compose command including:
    - env-file
    - compose file
    - project name
    """
    compose_file = None
    if COMPOSE_FILE_YML.exists():
        compose_file = COMPOSE_FILE_YML
    elif COMPOSE_FILE_YAML.exists():
        compose_file = COMPOSE_FILE_YAML

    if compose_file is None:
        raise FileNotFoundError(
            "docker-compose.yml or docker-compose.yaml not found "
            f"in {ROOT_DIR}"
        )

    # Prefer "docker compose" over "docker-compose"
    test_cmds = ["docker compose version", "docker-compose --version"]
    used = None
    for cmd in test_cmds:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if r.returncode == 0:
            used = cmd.split()[0]
            break

    if used is None:
        raise RuntimeError(
            "'docker compose' or 'docker-compose' not found. "
            "Verify Docker installation."
        )

    base_cmd = "docker compose" if used == "docker" else "docker-compose"

    return (
        f'{base_cmd} --env-file "{ENV_TARGET}" '
        f'-f "{compose_file}" -p {PROJECT_NAME} up -d'
    )


def launch_stack_in_external_terminal():
    """
    Starts the docker compose stack inside an external terminal window.
    - Validates Docker
    - Builds compose command
    - Opens the terminal depending on OS
    Terminal auto-closes when compose finishes.
    """
    check_docker()
    cmd = get_compose_cmd()
    system = platform.system()
    root_str = str(ROOT_DIR)

    if system == "Windows":
        # Use `cd /d` to manage disk changes (C: -> D: etc.)
        win_cmd = f'start "" cmd /c "cd /d \\"{root_str}\\" && {cmd}"'
        subprocess.Popen(win_cmd, shell=True)

    elif system == "Darwin":  # macOS
        apple_script = f'''
        tell application "Terminal"
            activate
            do script "cd {shlex.quote(root_str)} && {cmd}; exit"
        end tell
        '''
        subprocess.Popen(["osascript", "-e", apple_script])

    else:  # Linux
        term_cmds = [
            ["x-terminal-emulator", "-e", f"bash -lc 'cd {shlex.quote(root_str)} && {cmd}; exit'"],
            ["gnome-terminal", "--", "bash", "-lc", f"cd {shlex.quote(root_str)} && {cmd}; exit"],
            ["konsole", "-e", f"bash -lc 'cd {shlex.quote(root_str)} && {cmd}; exit'"],
        ]

        for tcmd in term_cmds:
            try:
                subprocess.Popen(tcmd)
                return
            except FileNotFoundError:
                continue

        # Fallback: run in background if no terminal emulator is available
        subprocess.Popen(f"cd {shlex.quote(root_str)} && {cmd}", shell=True)


# =========================
# MODERN HOVER TOOLTIP
# =========================
class HoverTooltip:
    """
    Modern tooltip shown when hovering a widget.
    text_func: callable returning the text to display (so it updates with language).
    """
    def __init__(self, widget, text_func, bg="#020617", fg="#e5e7eb"):
        self.widget = widget
        self.text_func = text_func
        self.bg = bg
        self.fg = fg
        self.tipwindow = None
        self._after_id = None

        self.widget.bind("<Enter>", self._on_enter)
        self.widget.bind("<Leave>", self._on_leave)
        self.widget.bind("<Motion>", self._on_motion)

    def _on_enter(self, event=None):
        # Small delay before showing to feel smooth
        self._schedule()

    def _on_leave(self, event=None):
        self._unschedule()
        self._hide_tip()

    def _on_motion(self, event=None):
        # reposition if needed
        pass

    def _schedule(self):
        self._unschedule()
        self._after_id = self.widget.after(400, self._show_tip)

    def _unschedule(self):
        if self._after_id is not None:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show_tip(self):
        if self.tipwindow is not None:
            return

        text = self.text_func() or ""
        if not text.strip():
            return

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8

        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        # Modern rounded feel (simulated)
        frame = tk.Frame(
            tw,
            bg=self.bg,
            bd=0,
            highlightthickness=1,
            highlightbackground="#1f2937",
        )
        frame.pack(fill="both", expand=True)

        label = tk.Label(
            frame,
            text=text,
            justify="left",
            bg=self.bg,
            fg=self.fg,
            font=("Segoe UI", 9),
            wraplength=260,
            padx=10,
            pady=8,
        )
        label.pack()

    def _hide_tip(self):
        tw = self.tipwindow
        if tw is not None:
            tw.destroy()
        self.tipwindow = None


# =========================
# GUI APP (TKINTER DARK MODE)
# =========================
class EnvConfiguratorApp(tk.Tk):
    def __init__(self):
        super().__init__()

        # =========================
        # Language / translations
        # =========================
        self.current_lang = tk.StringVar(value="en")  # default = english
        self.translations = {
            "en": {
                "window_title": "Lite Brain Launcher",
                "header_title": "🧠 Lite Brain Launcher",
                "header_subtitle": "Configure & deploy your local AI stack in one click.",
                "env_params": "Environment Parameters",
                "status_ready": "Ready • Localhost",
                "tip": "Tip: You can restart the launcher anytime to adjust configuration.",
                "btn_quit": "Quit",
                "btn_launch": "🚀 Save & Launch Lite Brain",
                "msg_launch_title": "Launching",
                "msg_launch_body": "Lite Brain stack is starting in a terminal.\nUI available at: {url}",
                "msg_error_title": "Error",
                "missing_template_title": "Error",
                "missing_template_body": "Template configuration file not found:\n{path}",
                "no_params": "No parameters in this section.",
                "ollama_help": (
                    "RAM suggestions:\n"
                    "•  8GB  → 4096\n"
                    "• 16GB  → 8192\n"
                    "• 32GB  → 16384\n"
                    "• 64GB  → 32768\n"
                    "• 128GB → 65536\n"
                    "• > 128GB → 131072"
                ),
                "advanced_ui": "Advanced UI options",
                "advanced_ml": "Advanced ML options",
            },
            "fr": {
                "window_title": "Lanceur Lite Brain",
                "header_title": "🧠 Lanceur Lite Brain",
                "header_subtitle": "Configurez et déployez votre stack IA locale en un clic.",
                "env_params": "Paramètres d'environnement",
                "status_ready": "Prêt • Localhost",
                "tip": "Astuce : vous pouvez relancer le lanceur à tout moment pour ajuster la configuration.",
                "btn_quit": "Quitter",
                "btn_launch": "🚀 Sauvegarder & Lancer Lite Brain",
                "msg_launch_title": "Lancement",
                "msg_launch_body": "La stack Lite Brain démarre dans un terminal.\nUI disponible sur : {url}",
                "msg_error_title": "Erreur",
                "missing_template_title": "Erreur",
                "missing_template_body": "Fichier de configuration modèle introuvable :\n{path}",
                "no_params": "Aucun paramètre dans cette section.",
                "ollama_help": (
                    "Suggestions de RAM :\n"
                    "•  8 Go  → 4096\n"
                    "• 16 Go  → 8192\n"
                    "• 32 Go  → 16384\n"
                    "• 64 Go  → 32768\n"
                    "• 128 Go → 65536\n"
                    "• > 128 Go → 131072"
                ),
                "advanced_ui": "Options UI avancées",
                "advanced_ml": "Options ML avancées",
            },
        }

        # =========================
        # Param help tooltips (EN / FR)
        # =========================
        self.param_help = {
            # ===== UI ENV CONFIG =====
            "LANGUAGE": {
                "en": "Language used by the UI (supported: english and french).",
                "fr": "Langue utilisée par l’interface (supporte: l'anglais et le français).",
            },
            "ULTRA_MODE_ACTIVE": {
                "en": "Enables the ultra LLM tier (heavier but more capable model).",
                "fr": "Active le niveau LLM 'ultra' (modèle plus lourd mais plus puissant).",
            },
            "LLM_HISTORY_MAX_MESSAGES": {
                "en": "Maximum number of previous messages kept in conversation history.",
                "fr": "Nombre maximum de messages précédents conservés dans l’historique de conversation.",
            },
            "CHUNK_SIZE": {
                "en": "Target size of each document chunk used for RAG (in characters).",
                "fr": "Taille cible de chaque bloc de document utilisé pour le RAG (en caractères).",
            },
            "OVERLAP": {
                "en": "Overlap between consecutive blocks to avoid cutting off important context when uploading documents",
                "fr": "Chevauchement entre les blocs consécutifs pour éviter de couper du contexte important lors de l'upload des documents.",
            },
            "TOP_K_HYBRID": {
                "en": "(For RAG) Number of raw candidates fetched from the vector store before filtering (hybrid search).",
                "fr": "(Pour RAG) Nombre de candidats bruts récupérés depuis le vecteur store avant filtrage (recherche hybride).",
            },
            "TOP_K_MMR": {
                "en": "(For RAG) Number of candidates kept after MMR (diversity-aware) filtering.",
                "fr": "(Pour RAG) Nombre de candidats conservés après le filtrage MMR (favorise la diversité).",
            },
            "TOP_K_RERANK": {
                "en": "(For RAG) Number of final documents kept after reranking by the reranker model.",
                "fr": "(Pour RAG) Nombre final de documents conservés après reranking par le modèle de reranking.",
            },
            "MMR_LAMBDA": {
                "en": "(For RAG) MMR trade-off between relevance and diversity (0 = more diversity, 1 = more relevance).",
                "fr": "(Pour RAG) Compromis MMR entre pertinence et diversité (0 = plus de diversité, 1 = plus de pertinence).",
            },
            "MAX_FULL_DOC_CHUNKS": {
                "en": "Safety cap on the total number of chunks processed in full-document mode (Increase this if you have documents of more than 300-400 pages).",
                "fr": "Limite de sécurité sur le nombre total de chunks traités en mode document complet (à augmenter si vous avez des documents de plus de 300-400 pages).",
            },
            "FULL_DOC_CHUNKS_PER_BATCH": {
                "en": "Number of chunks processed per batch in full-document mode (tuned to LLM context size). Use 12 for an LLM context of 4000 but 24 for a context of 8000 etc.",
                "fr": "Nombre de chunks traités par lot en mode document complet (à ajuster selon le contexte du LLM). Mettre 12 pour un LLM contexte de 4000 mais 24 pour contexte de 8000 etc.",
            },
            "MIN_CHAR_PER_PAGE": {
                "en": "Minimum number of characters per page before considering OCR may be needed on a PDF.",
                "fr": "Nombre minimal de caractères par page avant de considérer qu’un OCR est nécessaire sur un PDF.",
            },
            "AVG_MIN_CHARS": {
                "en": "Minimal average characters per page used to detect low-text documents on a PDF.",
                "fr": "Nombre moyen minimal de caractères par page pour détecter les documents peu textuels sur un PDF.",
            },
            "BLANK_PAGE_THRESHOLD": {
                "en": "Threshold used to classify a page as blank based on text ratio on a PDF.",
                "fr": "Seuil utilisé pour classifier une page comme blanche selon le ratio de texte sur un PDF.",
            },
            "SECRET_KEY": {
                "en": "Application secret key used for security (sessions, signing, etc.).",
                "fr": "Clé secrète de l’application utilisée pour la sécurité (sessions, signatures, etc.).",
            },

            # ===== ML ENV CONFIG =====
            "DEVICE": {
                "en": "Inference device: 'cpu' or a CUDA device like 'cuda:0' when GPU is available.",
                "fr": "Périphérique d’inférence : 'cpu' ou un device CUDA comme 'cuda:0' si un GPU est disponible.",
            },

            # EMBEDDING & RERANKING CONFIG
            "EMB_MAX_WORKERS": {
                "en": "Maximum number of parallel workers for embedding generation.",
                "fr": "Nombre maximal de workers parallèles pour la génération des embeddings.",
            },

            # ===== OCR CONFIG =====
            "OCR_CONCURRENCY_LIMIT": {
                "en": "Maximum number of OCR jobs processed in parallel to protect the CPU.",
                "fr": "Nombre maximal de tâches OCR traitées en parallèle pour protéger le CPU.",
            },
            "OCR_MAX_PAGES": {
                "en": "Hard cap on the number of pages processed by the OCR for a single document.",
                "fr": "Limite stricte du nombre de pages traitées par l’OCR pour un document.",
            },
            "OCR_ASSUME_STRAIGHT": {
                "en": "If set to 1, assumes pages are mostly straight, improving speed but reducing rotation handling.",
                "fr": "Si réglé à 1, suppose que les pages sont globalement droites, plus rapide mais moins tolérant aux rotations.",
            },
            "TORCH_NUM_THREADS": {
                "en": "Number of Torch compute threads used per process (CPU parallelism).",
                "fr": "Nombre de threads de calcul Torch utilisés par processus (parallélisme CPU).",
            },
            "TORCH_NUM_INTEROP": {
                "en": "Number of interop threads used by Torch for coordinating parallel tasks.",
                "fr": "Nombre de threads d’interopérabilité utilisés par Torch pour coordonner les tâches parallèles.",
            },
            "OCR_PDF_DPI": {
                "en": "Rendering DPI for converting PDFs to images before OCR (higher = better quality, slower).",
                "fr": "DPI utilisé pour convertir les PDFs en images avant l’OCR (plus élevé = meilleure qualité, plus lent).",
            },
            "OCR_BATCH_PAGES": {
                "en": "Number of pages processed together in each OCR batch.",
                "fr": "Nombre de pages traitées ensemble dans chaque lot OCR.",
            },
            "SEM_TIMEOUT_S": {
                "en": "Timeout in seconds when waiting for an OCR processing slot before returning an error.",
                "fr": "Timeout en secondes lors de l’attente d’un créneau de traitement OCR avant de renvoyer une erreur.",
            },
            "MAX_UPLOAD_MB": {
                "en": "Maximum allowed upload size in megabytes (files larger than this are rejected).",
                "fr": "Taille maximale d’upload autorisée en mégaoctets (les fichiers plus gros sont refusés).",
            },
            "PPTX_MAX_SLIDES": {
                "en": "Maximum number of PowerPoint slides accepted for a single upload.",
                "fr": "Nombre maximal de diapositives PowerPoint acceptées pour un upload.",
            },

            # ===== OLLAMA SERVER ENV CONFIG =====
            "OLLAMA_CONTEXT_LENGTH": {
                "en": "Context window size for the Ollama LLM server (higher allows longer conversations/documents).",
                "fr": "Taille de la fenêtre de contexte pour le serveur LLM Ollama (plus élevé = conversations/documents plus longs).",
            },
        }

        self.default_param_help = {
            "en": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Parameter description goes here.",
            "fr": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Description du paramètre ici.",
        }

        # Main window setup
        self.title(self.tr("window_title"))
        self.geometry("600x700")
        self.minsize(600, 700)

        # Dark theme palette
        self.bg_color = "#020617"
        self.card_color = "#020617"
        self.accent = "#38bdf8"
        self.accent_soft = "#0ea5e9"
        self.text_color = "#e5e7eb"

        self.configure(bg=self.bg_color)

        # Initialize theme
        self.style = ttk.Style()
        self._configure_style()

        # GPU list
        self.cuda_devices = detect_cuda_devices()

        # Ensure template exists
        if not ENV_SOURCE.exists():
            messagebox.showerror(
                self.tr("missing_template_title"),
                self.tr("missing_template_body", path=ENV_SOURCE)
            )
            self.destroy()
            return

        # Create .env if missing
        if not ENV_TARGET.exists():
            ENV_TARGET.write_text(
                ENV_SOURCE.read_text(encoding="utf-8"),
                encoding="utf-8"
            )

        # Load structure + actual values
        (
            self.parsed_lines,
            self.sections,
            self.sections_order,
            self.values_by_key
        ) = load_template_and_current_values()

        # If LANGUAGE=fr in the .env file, we start directly in French
        initial_lang = str(self.values_by_key.get("LANGUAGE", "en")).lower()
        if initial_lang in ("en", "fr"):
            self.current_lang.set(initial_lang)
            self.title(self.tr("window_title"))

        # Mapping key → widget / variable
        self.entry_by_key = {}
        self.vars_by_key = {}

        self.btn_launch = None
        self.btn_quit = None
        self._pulse_state = 0

        # UI references for language update
        self.title_label = None
        self.subtitle_label = None
        self.env_params_label = None
        self.status_label = None
        self.tip_label = None
        self.ollama_help_label = None
        self.no_params_labels = []
        # Labels for advanced section toggles (so they can be translated)
        self.advanced_labels_ui = []
        self.advanced_labels_ml = []

        # UI building
        self._build_ui()
        self.center_window()

        # Launch button animation
        self.after(600, self._pulse_launch_button)

    # ====== i18n helpers ======
    def tr(self, key, **kwargs):
        lang = self.current_lang.get()
        txt = self.translations.get(lang, {}).get(key, key)
        if kwargs:
            try:
                txt = txt.format(**kwargs)
            except Exception:
                pass
        return txt

    def change_language(self, lang):
        if lang not in ("en", "fr"):
            return
        if self.current_lang.get() == lang:
            return
        self.current_lang.set(lang)
        self.title(self.tr("window_title"))
        self._apply_translations()
        self._update_language_buttons()

    def get_param_help_text(self, key: str) -> str:
        """
        Returns the tooltip description for a given parameter key,
        in the current language. Falls back to default lorem ipsum.
        """
        lang = self.current_lang.get()
        data = self.param_help.get(key)
        if data and lang in data:
            return data[lang]
        return self.default_param_help.get(lang, "")

    # =========================
    # Window helpers
    # =========================
    def center_window(self):
        """
        Centers the window relative to the screen.
        """
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _configure_style(self):
        """
        Configures global ttk style for dark theme UI.
        """
        self.style.theme_use("clam")

        # Frames, labels, buttons, notebook etc.
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("Card.TFrame", background=self.card_color, relief="flat")

        self.style.configure("TLabel", background=self.bg_color,
                             foreground=self.text_color, font=("Segoe UI", 10))
        self.style.configure("Title.TLabel", background=self.bg_color,
                             foreground=self.accent, font=("Segoe UI Semibold", 20))
        self.style.configure("Section.TLabel", background=self.bg_color,
                             foreground="#9ca3af", font=("Segoe UI Semibold", 11))

        self.style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6)
        self.style.map("TButton",
                       background=[("active", self.accent_soft)],
                       foreground=[("active", "#020617")])

        self.style.configure("Accent.TButton",
                             background=self.accent,
                             foreground="#020617",
                             borderwidth=0)
        self.style.map("Accent.TButton",
                       background=[("!disabled", self.accent),
                                  ("active", self.accent_soft),
                                  ("pressed", self.accent_soft)],
                       foreground=[("!disabled", "#020617")])

        # Notebook tabs
        self.style.configure("TNotebook", background=self.bg_color, borderwidth=0)
        self.style.configure("TNotebook.Tab",
                             font=("Segoe UI", 10, "bold"),
                             padding=[18, 8],
                             background="#020617",
                             foreground="#6b7280")
        self.style.map("TNotebook.Tab",
                       background=[("selected", "#020617")],
                       foreground=[("selected", self.accent)])

        # === Modern slim vertical scrollbar ===
        self.style.configure(
            "Lite.Vertical.TScrollbar",
            gripcount=0,
            background=self.card_color,   # rail
            troughcolor=self.card_color,  # rail
            bordercolor=self.card_color,
            lightcolor=self.card_color,
            darkcolor=self.card_color,
            arrowcolor="#64748b",
            relief="flat",
            borderwidth=0,
            arrowsize=8,
        )
        self.style.map(
            "Lite.Vertical.TScrollbar",
            background=[
                ("!active", "#0b1120"),   # normal rail
                ("active", "#020617"),
            ],
            troughcolor=[
                ("!active", "#020617"),
                ("active", "#020617"),
            ]
        )

    def _add_info_icon(self, parent, row: int, key: str):
        """
        Adds a small modern 'i' bubble with a larger hover/click area
        for the given parameter key.
        """
        # Container that occupies the entire column → large hover area
        container = tk.Frame(
            parent,
            bg=self.card_color,
            bd=0,
            highlightthickness=0,
        )
        container.grid(
            row=row,
            column=2,
            sticky="we",
            pady=4,
            padx=(6, 0),   # a little space with the field
        )
        container.columnconfigure(0, weight=1)

        # The "i" in the center of the container
        info_label = tk.Label(
            container,
            text="i",
            bg=self.card_color,
            fg=self.accent,
            font=("Segoe UI", 9, "bold"),
            bd=0,
            padx=10,   # expands the clickable area
            pady=4,    # enlarges in height
            cursor="question_arrow",
        )
        info_label.pack(fill="both", expand=True)

        # Tooltip covering the ENTIRE container (easier target area)
        HoverTooltip(
            container,
            text_func=lambda k=key: self.get_param_help_text(k),
            bg="#020617",
            fg=self.text_color,
        )

    def _create_param_row(self, parent, row: int, key: str, val: str) -> int:
        """
        Create a single labeled parameter row (label + entry/combobox + info icon).
        Returns the next available grid row index.

        This helper keeps UI construction consistent between
        normal and "advanced" sections.
        """
        # Label for the parameter key
        ttk.Label(parent, text=key, style="TLabel").grid(
            row=row, column=0, sticky="w", pady=4
        )

        # Info icon for this parameter
        self._add_info_icon(parent, row, key)

        widget = None

        if key == "LANGUAGE":
            # Language selector (en / fr) - for the stack itself
            options = ["en", "fr"]
            current_val = str(val).strip() or "en"
            if current_val not in options:
                options.append(current_val)

            var_lang = tk.StringVar(value=current_val)
            widget = ttk.Combobox(
                parent,
                textvariable=var_lang,
                state="readonly",
                values=options,
            )
            self.vars_by_key[key] = var_lang

        elif key == "ULTRA_MODE_ACTIVE":
            # Boolean combobox
            current_val = "True" if str(val).lower() == "true" else "False"
            var_bool = tk.StringVar(value=current_val)
            widget = ttk.Combobox(
                parent,
                textvariable=var_bool,
                state="readonly",
                values=["False", "True"],
            )
            self.vars_by_key[key] = var_bool

        elif key == "DEVICE":
            # CPU/GPU device selector
            device_options = ["cpu"] + self.cuda_devices
            current_val = str(val).strip() or "cpu"
            if current_val not in device_options:
                device_options.append(current_val)

            var_dev = tk.StringVar(value=current_val)
            widget = ttk.Combobox(
                parent,
                textvariable=var_dev,
                state="readonly",
                values=device_options,
            )
            self.vars_by_key[key] = var_dev

        else:
            # Generic text field for remaining parameters
            widget = tk.Entry(
                parent,
                bg="#020617",
                fg=self.text_color,
                insertbackground=self.accent,
                relief="flat",
                highlightthickness=1,
                highlightbackground="#1f2937",
                highlightcolor=self.accent,
                font=("Consolas", 10),
            )
            widget.insert(0, val)

        # Entry in column 1, info bubble already in col 2
        widget.grid(
            row=row,
            column=1,
            sticky="we",
            pady=4,
            padx=(10, 0),
            ipady=3,
        )
        self.entry_by_key[key] = widget

        parent.columnconfigure(1, weight=1)
        return row + 1

    def _build_standard_section(self, inner, vars_in_section):
        """
        Build a standard section without special collapsing behavior.
        Used for sections like OLLAMA where we keep all parameters visible.
        """
        row = 0

        if not vars_in_section:
            # Keep behavior consistent with original implementation
            lbl = ttk.Label(
                inner,
                text=self.tr("no_params"),
                style="TLabel"
            )
            lbl.pack(pady=10)
            self.no_params_labels.append(lbl)
            return

        for key in vars_in_section:
            val = self.values_by_key.get(key, "")

            # Special handling for known keys -------------
            if key == "OLLAMA_CONTEXT_LENGTH":
                # Row with label + info icon
                ttk.Label(inner, text=key, style="TLabel").grid(
                    row=row, column=0, sticky="w", pady=4
                )
                self._add_info_icon(inner, row, key)
                inner.columnconfigure(1, weight=1)
                row += 1

                options = ["4096", "8192", "16384",
                           "32768", "65536", "131072"]
                current_val = str(val).strip() or "4096"
                if current_val not in options:
                    options.append(current_val)

                var_ctx = tk.StringVar(value=current_val)
                combo = ttk.Combobox(inner, state="readonly",
                                     textvariable=var_ctx,
                                     values=options)
                combo.grid(row=row, column=0, columnspan=3,
                           sticky="we", pady=4)

                self.entry_by_key[key] = combo
                self.vars_by_key[key] = var_ctx
                row += 1

                help_text = self.tr("ollama_help")
                self.ollama_help_label = ttk.Label(
                    inner,
                    text=help_text,
                    style="TLabel",
                    justify="left"
                )
                self.ollama_help_label.configure(foreground="#9ca3af")
                self.ollama_help_label.grid(
                    row=row,
                    column=0,
                    columnspan=3,
                    sticky="w",
                    pady=(0, 8)
                )
                row += 1
                continue

            # Default behavior for generic parameters
            row = self._create_param_row(inner, row, key, val)

    def _build_section_with_advanced(self, inner, section_name, vars_in_section, primary_keys, advanced_type_key):
        """
        Build a section where only a subset of "primary" parameters is shown by default.

        The remaining parameters are grouped behind a collapsible "Advanced" panel
        toggled via a modern arrow header.
        """
        row = 0

        if not vars_in_section:
            lbl = ttk.Label(
                inner,
                text=self.tr("no_params"),
                style="TLabel"
            )
            lbl.pack(pady=10)
            self.no_params_labels.append(lbl)
            return

        # Respect the order provided by the env file while splitting
        core_keys = [k for k in vars_in_section if k in primary_keys]
        advanced_keys = [k for k in vars_in_section if k not in primary_keys]

        # Render primary/core parameters first
        for key in core_keys:
            val = self.values_by_key.get(key, "")
            row = self._create_param_row(inner, row, key, val)

        if not advanced_keys:
            # If there is nothing more, we simply stop here
            return

        # --- Advanced toggle header (arrow + label) ---
        toggle_frame = tk.Frame(
            inner,
            bg=self.card_color,
            highlightthickness=0,
            bd=0,
        )
        toggle_frame.grid(
            row=row,
            column=0,
            columnspan=3,
            sticky="we",
            pady=(12, 4),
        )

        arrow_label = tk.Label(
            toggle_frame,
            text="▶",
            bg=self.card_color,
            fg=self.accent,
            font=("Segoe UI", 10, "bold"),
        )
        arrow_label.pack(side="left", padx=(0, 4))

        # Text label is localized and saved so we can update it on language change
        if advanced_type_key == "advanced_ui":
            text_label = tk.Label(
                toggle_frame,
                text=self.tr("advanced_ui"),
                bg=self.card_color,
                fg="#9ca3af",
                font=("Segoe UI", 10, "bold"),
            )
            self.advanced_labels_ui.append(text_label)
        else:
            text_label = tk.Label(
                toggle_frame,
                text=self.tr("advanced_ml"),
                bg=self.card_color,
                fg="#9ca3af",
                font=("Segoe UI", 10, "bold"),
            )
            self.advanced_labels_ml.append(text_label)

        text_label.pack(side="left")

        # Container for advanced parameters
        advanced_frame = ttk.Frame(inner, style="Card.TFrame")
        advanced_frame.grid(
            row=row + 1,
            column=0,
            columnspan=3,
            sticky="we",
            pady=(4, 0),
        )

        # Build all advanced parameters inside the collapsible frame
        adv_row = 0
        for key in advanced_keys:
            val = self.values_by_key.get(key, "")
            adv_row = self._create_param_row(advanced_frame, adv_row, key, val)

        # Start collapsed by default
        advanced_frame.grid_remove()

        # Local mutable state to track visibility
        state = {"visible": False}

        def _toggle_advanced(event=None):
            """
            Toggle advanced frame visibility and update arrow icon.
            """
            if state["visible"]:
                advanced_frame.grid_remove()
                arrow_label.configure(text="▶")
                state["visible"] = False
            else:
                advanced_frame.grid()
                arrow_label.configure(text="▼")
                state["visible"] = True

        # Make the entire header clickable and cursor feedback consistent
        for widget in (toggle_frame, arrow_label, text_label):
            widget.bind("<Button-1>", _toggle_advanced)
            widget.configure(cursor="hand2")

    def _build_ui(self):
        """
        Builds entire Tkinter UI:
        - Header bar (+ language toggle)
        - Notebook with environment sections
        - Form fields for each env var
        - Bottom action buttons
        """
        # HEADER -------------------------------
        header = ttk.Frame(self, style="TFrame")
        header.pack(fill="x", padx=24, pady=(18, 10))

        left_header = ttk.Frame(header, style="TFrame")
        left_header.pack(side="left", anchor="w")

        self.title_label = ttk.Label(
            left_header,
            text=self.tr("header_title"),
            style="Title.TLabel"
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ttk.Label(
            left_header,
            text=self.tr("header_subtitle"),
            style="TLabel"
        )
        self.subtitle_label.pack(anchor="w", pady=(4, 0))

        right_header = ttk.Frame(header, style="TFrame")
        right_header.pack(side="right")

        # --- Language toggle (modern pill) ---
        lang_pill = tk.Frame(
            right_header,
            bg="#020617",
            highlightbackground="#1f2937",
            highlightthickness=1,
            bd=0,
        )
        lang_pill.pack(side="top", anchor="e", pady=(0, 6))

        self.btn_lang_en = tk.Button(
            lang_pill,
            text="EN",
            bd=0,
            padx=10,
            pady=2,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            command=lambda: self.change_language("en"),
            relief=tk.FLAT,
        )
        self.btn_lang_en.pack(side="left")

        self.btn_lang_fr = tk.Button(
            lang_pill,
            text="FR",
            bd=0,
            padx=10,
            pady=2,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            command=lambda: self.change_language("fr"),
            relief=tk.FLAT,
        )
        self.btn_lang_fr.pack(side="left")

        # Status chip
        status_chip = tk.Frame(right_header, bg="#0f172a",
                               highlightbackground=self.accent,
                               highlightthickness=1)
        status_chip.pack()

        dot = tk.Canvas(status_chip, width=10, height=10,
                        bg="#0f172a", highlightthickness=0)
        dot.create_oval(2, 2, 8, 8, fill="#22c55e", outline="")
        dot.pack(side="left", padx=(8, 4), pady=4)

        self.status_label = tk.Label(
            status_chip,
            text=self.tr("status_ready"),
            bg="#0f172a",
            fg=self.text_color,
            font=("Segoe UI", 9)
        )
        self.status_label.pack(side="left", padx=(0, 8))

        # Updates the graphical state of the language buttons
        self._update_language_buttons()

        # MAIN PANEL ---------------------------
        shadow = tk.Frame(self, bg="#000000")
        shadow.pack(fill="both", expand=True, padx=32, pady=(0, 28))
        shadow.pack_propagate(False)

        main_container = tk.Frame(
            shadow, bg=self.card_color, highlightthickness=1,
            highlightbackground="#1f2937"
        )
        main_container.place(relx=0, rely=0, relwidth=1, relheight=1, y=-3)

        # Left area (contains the scrollable section + bottom buttons)
        left_side = ttk.Frame(main_container, style="Card.TFrame")
        left_side.pack(fill="both", expand=True, padx=10, pady=18)

        # ---------- SCROLLABLE AREA ----------
        scroll_container = tk.Frame(left_side, bg=self.card_color)
        scroll_container.pack(fill="both", expand=True)

        # Canvas + Vertical Scrollbar
        canvas = tk.Canvas(
            scroll_container,
            bg=self.card_color,
            highlightthickness=0,
            borderwidth=0,
        )
        canvas.pack(side="left", fill="both", expand=True)

        vscroll = ttk.Scrollbar(
            scroll_container,
            orient="vertical",
            command=canvas.yview,
            style="Lite.Vertical.TScrollbar",
        )
        vscroll.pack(side="right", fill="y", padx=(4, 0))

        canvas.configure(yscrollcommand=vscroll.set)

        # Inner frame that will contain the label + notebook
        scroll_frame = ttk.Frame(canvas, style="Card.TFrame")
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        # Adjust the scrollregion when the content changes
        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        scroll_frame.bind("<Configure>", _on_frame_configure)

        # Mouse wheel
        def _on_mousewheel(event):
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ---------- SCROLLABLE CONTENT ----------
        self.env_params_label = ttk.Label(
            scroll_frame,
            text=self.tr("env_params"),
            style="Section.TLabel"
        )
        self.env_params_label.pack(anchor="w", pady=(0, 6))

        notebook = ttk.Notebook(scroll_frame)
        notebook.pack(fill="both", expand=True)

        # Create a tab per section
        for section_name in self.sections_order:
            vars_in_section = self.sections[section_name]
            tab = ttk.Frame(notebook, style="Card.TFrame")
            notebook.add(tab, text=section_name)

            inner = ttk.Frame(tab, style="Card.TFrame")
            inner.pack(fill="both", expand=True, padx=18, pady=14)

            # UI and ML sections get a modern "advanced" collapsible panel
            if section_name == "UI":
                primary_ui_keys = {"LANGUAGE", "ULTRA_MODE_ACTIVE", "LLM_HISTORY_MAX_MESSAGES"}
                self._build_section_with_advanced(
                    inner,
                    section_name,
                    vars_in_section,
                    primary_ui_keys,
                    advanced_type_key="advanced_ui",
                )
            elif section_name == "ML":
                primary_ml_keys = {"DEVICE"}
                self._build_section_with_advanced(
                    inner,
                    section_name,
                    vars_in_section,
                    primary_ml_keys,
                    advanced_type_key="advanced_ml",
                )
            else:
                # Other sections keep the original behavior
                self._build_standard_section(inner, vars_in_section)

        # BOTTOM BUTTONS -----------------------
        btn_frame = ttk.Frame(main_container, style="Card.TFrame")
        btn_frame.pack(fill="x", padx=18, pady=(8, 12), side="bottom")

        # Centered Tip
        self.tip_label = ttk.Label(
            btn_frame,
            text=self.tr("tip"),
            style="TLabel",
        )
        self.tip_label.pack(anchor="center")

        # Line of buttons centered below the tip
        buttons_row = ttk.Frame(btn_frame, style="Card.TFrame")
        buttons_row.pack(anchor="center", pady=(10, 0))

        # Bouton Quit
        self.btn_quit = ttk.Button(
            buttons_row,
            text=self.tr("btn_quit"),
            command=self.destroy,
        )
        self.btn_quit.pack(side="left", padx=6, ipady=2)

        # Bouton Save & Launch
        self.btn_launch = ttk.Button(
            buttons_row,
            text=self.tr("btn_launch"),
            style="Accent.TButton",
            command=self.on_save_and_launch,
        )
        self.btn_launch.pack(side="left", padx=6, ipady=2)

    def _update_language_buttons(self):
        """
        Updates the visual style of the EN / FR buttons.
        """
        lang = self.current_lang.get()

        if lang == "en":
            self.btn_lang_en.configure(
                bg=self.accent, fg="#020617", activebackground=self.accent_soft
            )
            self.btn_lang_fr.configure(
                bg="#020617", fg="#9ca3af", activebackground="#020617"
            )
        else:
            self.btn_lang_fr.configure(
                bg=self.accent, fg="#020617", activebackground=self.accent_soft
            )
            self.btn_lang_en.configure(
                bg="#020617", fg="#9ca3af", activebackground="#020617"
            )

    def _apply_translations(self):
        """
        Dynamically updates all UI text
        when the language is changed.
        """
        # Window title
        self.title(self.tr("window_title"))

        # Header
        if self.title_label is not None:
            self.title_label.configure(text=self.tr("header_title"))
        if self.subtitle_label is not None:
            self.subtitle_label.configure(text=self.tr("header_subtitle"))

        # Status chip
        if self.status_label is not None:
            self.status_label.configure(text=self.tr("status_ready"))

        # Section env
        if self.env_params_label is not None:
            self.env_params_label.configure(text=self.tr("env_params"))

        # Tip
        if self.tip_label is not None:
            self.tip_label.configure(text=self.tr("tip"))

        # Buttons
        if self.btn_quit is not None:
            self.btn_quit.configure(text=self.tr("btn_quit"))
        if self.btn_launch is not None:
            self.btn_launch.configure(text=self.tr("btn_launch"))

        # OLLAMA Help Text
        if self.ollama_help_label is not None:
            self.ollama_help_label.configure(text=self.tr("ollama_help"))

        # Labels "no params"
        for lbl in self.no_params_labels:
            lbl.configure(text=self.tr("no_params"))

        # Advanced toggle labels for UI and ML sections
        for lbl in self.advanced_labels_ui:
            lbl.configure(text=self.tr("advanced_ui"))
        for lbl in self.advanced_labels_ml:
            lbl.configure(text=self.tr("advanced_ml"))

        # Tooltips update automatically because they call
        # get_param_help_text() every time they are displayed.

    def _pulse_launch_button(self):
        """
        Simple pulsing effect on the launch button.
        Optimized to avoid UI errors.
        """
        try:
            if self._pulse_state == 0:
                self.style.configure("Accent.TButton", background=self.accent)
                self._pulse_state = 1
            else:
                self.style.configure("Accent.TButton", background=self.accent_soft)
                self._pulse_state = 0
        except Exception:
            return

        self.after(700, self._pulse_launch_button)

    def collect_values(self):
        """
        Reads current values from all form fields and returns key→value dict.
        """
        values = {}
        for key, widget in self.entry_by_key.items():
            try:
                values[key] = widget.get().strip()
            except Exception:
                values[key] = ""
        return values

    def on_save_and_launch(self):
        """
        Saves .env using the template structure, then:
        - launches docker compose in external terminal
        - opens browser
        - closes launcher
        Handles all errors gracefully.
        """
        try:
            new_values = self.collect_values()
            new_text = rebuild_env_text(self.parsed_lines, new_values)
            ENV_TARGET.write_text(new_text, encoding="utf-8")

            launch_stack_in_external_terminal()
            webbrowser.open(APP_URL)

            messagebox.showinfo(
                self.tr("msg_launch_title"),
                self.tr("msg_launch_body", url=APP_URL),
            )
            self.destroy()

        except Exception as e:
            messagebox.showerror(self.tr("msg_error_title"), str(e))


def main():
    try:
        repo_root = ensure_repo_cloned()
        set_root_dir(repo_root)
    except Exception as e:
        # A little root command to display the error properly
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", f"Failed to prepare Lite-Brain repository:\n{e}")
        root.destroy()
        return

    app = EnvConfiguratorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
