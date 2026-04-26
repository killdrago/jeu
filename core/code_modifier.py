"""
Moteur de modification de code par l'IA.
- Parse la réponse de l'IA pour extraire les blocs de code
- Valide syntaxiquement chaque fichier Python (ast.parse)
- Applique les modifications dans un dossier preview/ isolé
- Génère un diff lisible
"""

import os
import ast
import re
import shutil
import difflib
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class CodeBlock:
    """Représente un bloc de code extrait de la réponse IA."""
    filename: str           # Nom du fichier cible (ex: ui/chat_widget.py)
    content: str            # Contenu du code
    language: str = "python"
    action: str = "replace" # replace | patch | create
    description: str = ""   # Description de la modification


@dataclass
class ModificationPlan:
    """Plan de modification complet généré par l'IA."""
    blocks: List[CodeBlock] = field(default_factory=list)
    description: str = ""
    raw_response: str = ""
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)


class CodeModifier:
    """
    Extrait et applique les modifications de code proposées par l'IA.
    """

    # Patterns pour extraire les blocs de code de la réponse IA
    # Format attendu: ```python filename: ui/chat_widget.py
    BLOCK_PATTERN = re.compile(
        r"```(?P<lang>\w+)?\s*"
        r"(?:filename:\s*(?P<filename>[\w/\\.\-]+))?\s*\n"
        r"(?P<code>.*?)"
        r"```",
        re.DOTALL | re.IGNORECASE
    )

    # Pattern alternatif: ## FILE: path/to/file.py
    FILE_HEADER_PATTERN = re.compile(
        r"##\s*FILE:\s*(?P<filename>[\w/\\.\-]+)\s*\n"
        r"```(?:\w+)?\s*\n"
        r"(?P<code>.*?)"
        r"```",
        re.DOTALL
    )

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.preview_dir = os.path.join(base_dir, "_preview")

    # ─────────────────────────────────────────────
    # Extraction
    # ─────────────────────────────────────────────

    def extract_code_blocks(self, ai_response: str) -> List[CodeBlock]:
        """Extrait tous les blocs de code de la réponse IA."""
        blocks = []

        # Méthode 1: ## FILE: pattern
        for match in self.FILE_HEADER_PATTERN.finditer(ai_response):
            filename = match.group("filename").strip()
            code = match.group("code").strip()
            if code:
                blocks.append(CodeBlock(
                    filename=self._normalize_path(filename),
                    content=code,
                    language="python",
                    action=self._detect_action(ai_response, filename)
                ))

        # Méthode 2: ```python filename: ... pattern
        if not blocks:
            for match in self.BLOCK_PATTERN.finditer(ai_response):
                lang = match.group("lang") or "python"
                filename = match.group("filename")
                code = match.group("code").strip()

                if not code:
                    continue

                if not filename:
                    # Essaie de deviner depuis le contexte
                    filename = self._guess_filename(
                        ai_response[:match.start()], lang
                    )

                if filename:
                    blocks.append(CodeBlock(
                        filename=self._normalize_path(filename),
                        content=code,
                        language=lang.lower(),
                        action=self._detect_action(ai_response, filename)
                    ))

        return blocks

    def _normalize_path(self, path: str) -> str:
        """Normalise un chemin (slashes, pas de ..)."""
        path = path.replace("\\", "/")
        path = os.path.normpath(path).replace("\\", "/")
        # Sécurité: pas de remontée de dossier
        if ".." in path:
            path = os.path.basename(path)
        return path

    def _detect_action(self, text: str, filename: str) -> str:
        """Détecte si c'est un remplacement, patch ou création."""
        context = text.lower()
        if "crée" in context or "create" in context or "nouveau" in context:
            return "create"
        if "patch" in context or "modifie" in context or "ajoute" in context:
            return "patch"
        return "replace"

    def _guess_filename(self, context: str, lang: str) -> Optional[str]:
        """Essaie de deviner le nom de fichier depuis le contexte."""
        # Cherche des patterns comme "dans ui/chat_widget.py"
        pattern = re.compile(
            r"(?:fichier|file|dans|in|modif(?:ie)?)\s+"
            r"`?([a-zA-Z0-9_/\\.\-]+\.(?:py|txt|json|bat))`?",
            re.IGNORECASE
        )
        match = pattern.search(context[-500:])
        if match:
            return self._normalize_path(match.group(1))
        return None

    # ─────────────────────────────────────────────
    # Validation
    # ─────────────────────────────────────────────

    def validate_python(self, code: str) -> Tuple[bool, str]:
        """Valide la syntaxe Python avec ast.parse."""
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"SyntaxError ligne {e.lineno}: {e.msg}"
        except Exception as e:
            return False, str(e)

    def build_modification_plan(self, ai_response: str) -> ModificationPlan:
        """Construit et valide un plan de modification depuis la réponse IA."""
        plan = ModificationPlan(raw_response=ai_response)
        blocks = self.extract_code_blocks(ai_response)

        if not blocks:
            plan.validation_errors.append(
                "Aucun bloc de code trouvé dans la réponse IA.\n"
                "Format attendu:\n"
                "## FILE: ui/chat_widget.py\n"
                "```python\n"
                "# code ici\n"
                "```"
            )
            return plan

        for block in blocks:
            if block.language == "python":
                ok, err = self.validate_python(block.content)
                if not ok:
                    plan.validation_errors.append(
                        f"❌ {block.filename}: {err}"
                    )
                    continue
            plan.blocks.append(block)

        plan.is_valid = len(plan.blocks) > 0
        return plan

    # ─────────────────────────────────────────────
    # Preview
    # ─────────────────────────────────────────────

    def prepare_preview(self, plan: ModificationPlan) -> Tuple[bool, str]:
        """
        Copie l'app entière dans _preview/ et y applique les modifications.
        Retourne (succès, message).
        """
        try:
            # Nettoie l'ancien preview
            if os.path.exists(self.preview_dir):
                shutil.rmtree(self.preview_dir)

            # Copie l'app de base dans _preview/
            shutil.copytree(
                self.base_dir,
                self.preview_dir,
                ignore=shutil.ignore_patterns(
                    "_preview", "__pycache__", "*.pyc",
                    ".git", "model", "*.gguf"
                )
            )

            # Applique les modifications dans _preview/
            for block in plan.blocks:
                target = os.path.join(self.preview_dir, block.filename)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "w", encoding="utf-8") as f:
                    f.write(block.content)

            return True, f"Preview prêt: {len(plan.blocks)} fichier(s) modifié(s)"

        except Exception as e:
            return False, f"Erreur préparation preview: {e}"

    # ─────────────────────────────────────────────
    # Application finale
    # ─────────────────────────────────────────────

    def apply_plan(self, plan: ModificationPlan) -> Tuple[bool, str]:
        """
        Applique les modifications directement sur l'app de base.
        À appeler APRÈS validation humaine.
        """
        applied = []
        errors = []

        for block in plan.blocks:
            target = os.path.join(self.base_dir, block.filename)
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "w", encoding="utf-8") as f:
                    f.write(block.content)
                applied.append(block.filename)
            except Exception as e:
                errors.append(f"{block.filename}: {e}")

        if errors:
            return False, f"Erreurs: {'; '.join(errors)}"

        return True, f"✅ {len(applied)} fichier(s) modifié(s): {', '.join(applied)}"

    # ─────────────────────────────────────────────
    # Diff
    # ─────────────────────────────────────────────

    def generate_diff(self, plan: ModificationPlan) -> str:
        """Génère un diff lisible entre l'original et la modification."""
        diff_parts = []

        for block in plan.blocks:
            original_path = os.path.join(self.base_dir, block.filename)

            # Lit l'original
            if os.path.exists(original_path):
                try:
                    with open(original_path, "r", encoding="utf-8") as f:
                        original_lines = f.readlines()
                except Exception:
                    original_lines = ["<fichier illisible>\n"]
            else:
                original_lines = ["<nouveau fichier>\n"]

            # Nouvelles lignes
            new_lines = [
                l if l.endswith("\n") else l + "\n"
                for l in block.content.splitlines()
            ]

            diff = list(difflib.unified_diff(
                original_lines,
                new_lines,
                fromfile=f"original/{block.filename}",
                tofile=f"modifié/{block.filename}",
                lineterm=""
            ))

            if diff:
                diff_parts.append("\n".join(diff))

        return "\n\n".join(diff_parts) if diff_parts else "Aucune différence détectée."

    def get_file_content(self, relative_path: str) -> Optional[str]:
        """Lit le contenu d'un fichier de l'app."""
        full_path = os.path.join(self.base_dir, relative_path)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    def list_app_files(self) -> List[str]:
        """Liste tous les fichiers Python de l'app."""
        files = []
        for root, dirs, filenames in os.walk(self.base_dir):
            # Exclut les dossiers non pertinents
            dirs[:] = [
                d for d in dirs
                if d not in ("__pycache__", ".git", "_preview", "model")
            ]
            for fname in filenames:
                if fname.endswith((".py", ".json", ".txt", ".bat", ".md")):
                    rel = os.path.relpath(
                        os.path.join(root, fname), self.base_dir
                    ).replace("\\", "/")
                    files.append(rel)
        return sorted(files)
