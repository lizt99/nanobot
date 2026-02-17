"""
Skill Installer Service.
Responsible for fetching, verifying, and installing skills from remote registries.
"""

import os
import shutil
import tarfile
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from loguru import logger

class SkillInstaller:
    # Hardcoded registries (Priority order)
    REGISTRIES = [
        "https://npm.mspbots.ai",
        "https://skillmp.com"
    ]

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.skills_dir = workspace / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def ensure_skills(self, skill_names: list[str]) -> None:
        """Check for missing skills and attempt to install them."""
        for name in skill_names:
            if not self._is_installed(name):
                logger.info(f"Skill '{name}' missing. Attempting auto-install...")
                if self._install_skill(name):
                    logger.info(f"Skill '{name}' installed successfully.")
                else:
                    logger.warning(f"Failed to install skill '{name}' from any registry.")

    def _is_installed(self, name: str) -> bool:
        """Check if skill exists in workspace."""
        # Simple check: does the directory exist and contain SKILL.md?
        skill_path = self.skills_dir / name
        if skill_path.exists() and (skill_path / "SKILL.md").exists():
            return True
        
        # Check package (Built-in skills)
        try:
            import nanobot.skills
            pkg_path = Path(nanobot.skills.__file__).parent
            builtin_path = pkg_path / name
            if builtin_path.exists() and (builtin_path / "SKILL.md").exists():
                return True
        except (ImportError, AttributeError):
            pass
            
        return False

    def _install_skill(self, name: str) -> bool:
        """Iterate registries to find and install the skill."""
        for registry in self.REGISTRIES:
            # Normalize URL
            base_url = registry.rstrip("/")
            # Assumption: Skills are hosted as tar.gz bundles
            # e.g. https://npm.mspbots.ai/web-search.tar.gz
            url = f"{base_url}/{name}.tar.gz"
            
            try:
                logger.debug(f"Checking {url}...")
                if self._download_and_extract(url, name):
                    self._install_dependencies(name)
                    return True
            except Exception as e:
                logger.debug(f"Failed to fetch from {registry}: {e}")
                continue
        
        return False

    def _download_and_extract(self, url: str, name: str) -> bool:
        """Download .tar.gz and extract to skills directory."""
        import tempfile
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
                # Set a User-Agent to avoid some 403s
                req = urllib.request.Request(
                    url, 
                    headers={'User-Agent': 'nanobot/1.0'}
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status != 200:
                        return False
                    shutil.copyfileobj(response, tmp)
                    tmp_path = Path(tmp.name)

            # Extract
            target_dir = self.skills_dir / name
            target_dir.mkdir(exist_ok=True)
            
            with tarfile.open(tmp_path, "r:gz") as tar:
                # Security: simplistic check to prevent path traversal
                for member in tar.getmembers():
                    if ".." in member.name or member.name.startswith("/"):
                        logger.warning(f"Skipping suspicious file in {name}: {member.name}")
                        continue
                    tar.extract(member, path=target_dir)
            
            # Cleanup
            os.unlink(tmp_path)
            
            # Validation: Did we get a SKILL.md?
            # Sometimes tarballs have a root folder, sometimes not. 
            # If SKILL.md is inside a subdirectory, we might need to flatten it.
            # For now, assume standard flat structure or root folder matches name.
            return True

        except urllib.error.HTTPError:
            return False
        except Exception as e:
            logger.error(f"Error downloading {name}: {e}")
            return False

    def _install_dependencies(self, name: str) -> None:
        """Install Python (pip) and Node (npm) dependencies if present."""
        skill_path = self.skills_dir / name
        
        # 1. Python: requirements.txt
        req_file = skill_path / "requirements.txt"
        if req_file.exists():
            logger.info(f"Installing Python dependencies for {name}...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                    check=True,
                    capture_output=True
                )
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install python deps for {name}: {e.stderr.decode()}")

        # 2. Node: package.json
        pkg_file = skill_path / "package.json"
        if pkg_file.exists():
            logger.info(f"Installing Node dependencies for {name}...")
            # Check if npm is available
            if shutil.which("npm"):
                try:
                    subprocess.run(
                        ["npm", "install"],
                        cwd=str(skill_path),
                        check=True,
                        capture_output=True
                    )
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to install node deps for {name}: {e.stderr.decode()}")
            else:
                logger.warning("npm not found, skipping package.json installation")
import sys
