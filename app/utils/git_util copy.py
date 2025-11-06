# git_util.py

import os
import shutil
import logging
from datetime import datetime
from dotenv import load_dotenv
import re
from textwrap import dedent

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class GitUtil:
    """
    Git utility for automation projects.
    Handles local project setup, YAML cleanup, Git initialization, and push operations.
    """

    BASE_PATH = os.getenv("BASE_PATH", "/tmp/New_Usecases")
    TEMPLATE_PATH = os.getenv("TEMPLATE_PATH", "/home/user/Project_template")
    GIT_URL = os.getenv("GIT_URL", "git@github.com:roysantu2002/script-bot.git")

    @staticmethod
    def _sanitize_name(name: str) -> str:
        return name.replace(" ", "_").replace("/", "_").strip()

    @staticmethod
    def _sanitize_yaml_content(content: str) -> str:
        """
        Clean AI-generated YAML by removing markdown fences, stripping
        surrounding quotes, and removing trailing model/usage metadata.
        """
        if not content:
            return "# Empty playbook"

        cleaned = content.strip()

        cleaned = re.sub(r"^```(?:yaml|yml)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1].strip()

        cleaned = re.sub(r"\s+usage=\{.*$", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"\s+model=['\"][^'\"]+['\"].*$", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"\s+finish_reason=['\"][^'\"]+['\"].*$", "", cleaned, flags=re.DOTALL)

        lines = [line.rstrip() for line in cleaned.splitlines()]
        cleaned = dedent("\n".join(lines)).strip()

        return cleaned

    def _ensure_path(self, automation_name: str) -> str:
        sanitized_name = self._sanitize_name(automation_name)
        target = os.path.join(self.BASE_PATH, sanitized_name)
        os.makedirs(target, exist_ok=True)
        return target

    def update_copy(self, automation_name: str) -> str:
        try:
            target = self._ensure_path(automation_name)
            print(f"📁 [update_copy] Local project directory ready at: {target}")
            logging.info(f"📁 Local directory ensured: {target}")
            return target
        except Exception as e:
            logging.error(f"❌ Error in update_copy: {e}")
            raise

    def update_readme(self, automation_name: str, step_content: str, step_count: int) -> None:
        try:
            target = self._ensure_path(automation_name)
            step_file = os.path.join(target, f"step_{step_count}.md")

            with open(step_file, "a", encoding="utf-8") as f:
                f.write(f"\n\n### Step {step_count}\n{step_content}\n")

            print(f"🪶 Step {step_count} written to: {step_file}")
            logging.info(f"🪶 Step {step_count} appended to: {step_file}")
        except Exception as e:
            logging.error(f"❌ Error updating README: {e}")
            raise

    def write_steps_md(self, automation_name: str, steps: list[str]) -> str:
        """
        Writes ALL steps into ONE steps.md file.
        """
        try:
            target = self.update_copy(automation_name)
            md_path = os.path.join(target, "steps.md")

            with open(md_path, "w", encoding="utf-8") as f:
                f.write(f"# Steps for {automation_name}\n\n")
                for i, step in enumerate(steps, start=1):
                    f.write(f"## Step {i}\n{step}\n\n")

            print(f"📝 All steps written into: {md_path}")
            logging.info(f"📝 All steps written into: {md_path}")
            return md_path
        except Exception as e:
            logging.error(f"❌ Error writing steps markdown: {e}")
            raise

    def git_project_create(self, automation_name: str, content: str = "", readme_content: str = "") -> str:
        try:
            target = self._ensure_path(automation_name)
            readme_path = os.path.join(target, "README.md")

            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(f"# {automation_name}\n\n{readme_content or 'Generated automation script.'}\n")

            yaml_filename = f"{self._sanitize_name(automation_name)}.yml"
            yaml_path = os.path.join(target, yaml_filename)

            clean_content = self._sanitize_yaml_content(content)
            with open(yaml_path, "w", encoding="utf-8") as yml:
                yml.write(clean_content + "\n")

            print(f"📝 README.md created at: {readme_path}")
            print(f"📄 YAML playbook created at: {yaml_path}")

            os.chdir(target)
            os.system("git init -q")
            os.system("git add .")
            os.system('git commit -m "Initial commit" -q')
            os.system("git branch -M main")

            if self.GIT_URL:
                os.system("git remote remove origin || true")
                os.system(f"git remote add origin {self.GIT_URL}")
                os.system("git push -u origin main || echo '⚠️ Push skipped (no permissions)'")

            print(f"🚀 Project '{automation_name}' initialized successfully at {target}")
            logging.info(f"🚀 Project '{automation_name}' initialized and pushed to remote")

            return target

        except Exception as e:
            logging.error(f"❌ Error during Git project creation: {e}")
            raise

    def git_project_push(self, automation_name: str, uid: str) -> tuple[str, str]:
        try:
            sanitized_name = self._sanitize_name(automation_name)
            project_path = os.path.join(self.BASE_PATH, sanitized_name)
            os.chdir(project_path)

            today_date = datetime.now().strftime("%d%m%Y")
            branch = f"UID_{uid}_{today_date}"

            os.system("git add .")
            os.system(f'git commit -m "auto-update: {today_date}" || echo "No changes to commit"')
            os.system(f"git branch -M {branch}")

            if self.GIT_URL:
                os.system("git remote remove origin || true")
                os.system(f"git remote add origin {self.GIT_URL}")
                os.system(f"git push -u origin {branch} || echo '⚠️ Push skipped (no permissions)'")

            print(f"✅ Successfully pushed branch '{branch}' for '{automation_name}'")
            logging.info(f"✅ Successfully pushed branch '{branch}' for '{automation_name}'")

            return self.GIT_URL, branch

        except Exception as e:
            logging.error(f"❌ Error pushing Git project: {e}")
            raise
