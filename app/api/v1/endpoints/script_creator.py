# app/routers/script_creator.py

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.services.script_services import ScriptServices
from app.services.script_writer import ScriptUtil
from app.utils.ansible_lib import AnsibleUtil
from app.utils.git_util import GitUtil

logger = structlog.get_logger(__name__)
router = APIRouter()


def get_script_services() -> ScriptServices:
    return ScriptServices()


def get_script_util(provider: Optional[str] = Query(None)) -> ScriptUtil:
    return ScriptUtil(provider_name=provider)


@router.post("/usecases/submit", summary="Submit a new automation use case")
async def submit_usecase(
    payload: Dict[str, Any] = Body(..., example={
        "name": "Restart Nginx",
        "description": "Generate an Ansible playbook to restart nginx service",
        "tech_comment": "Include pre-check for service status.",
    }),
    services: ScriptServices = Depends(get_script_services),
):
    try:
        uid = await services.insert_usecase(
            name=payload["name"],
            description=payload.get("description", ""),
            tech_comment=payload.get("tech_comment", ""),
        )

        return JSONResponse(
            content={"success": True, "uid": uid, "message": "Use case submitted successfully"},
            status_code=201,
        )
    except Exception as exc:
        logger.error("Failed to submit use case", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Error submitting use case: {str(exc)}")


@router.get("/usecases/{uid}", summary="Fetch use case details")
async def fetch_usecase(uid: str, services: ScriptServices = Depends(get_script_services)):
    try:
        data = await services.get_usecase(uid)
        if not data:
            raise HTTPException(status_code=404, detail=f"Use case {uid} not found")
        return {"success": True, "data": data}
    except Exception as exc:
        logger.error("Error fetching use case", uid=uid, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Error fetching use case: {str(exc)}")

@router.post("/script/create", summary="Generate automation script for use case")
async def create_script(
    payload: Dict[str, Any] = Body(..., example={
        "uid": "UC-1730123456",
        "name": "Restart Nginx",
        "query": "Create an Ansible playbook to restart nginx service on Ubuntu.",
    }),
    provider: Optional[str] = Query(None),
    script_util: ScriptUtil = Depends(get_script_util),
    services: ScriptServices = Depends(get_script_services),
):
    import textwrap  # local import to avoid changing file-level imports

    uid = payload.get("uid")
    name = payload.get("name")
    query = payload.get("query")

    if not (uid and name and query):
        raise HTTPException(status_code=400, detail="uid, name and query are required")

    try:
        # -------------------------
        # 1) Request exactly 10 numbered steps (strict format)
        # -------------------------
        prompt_steps = (
            f"You are an expert Ansible automation engineer.\n\n"
            f"Provide EXACTLY 10 concise numbered steps required to automate the "
            f"following use case in Ansible (include pre, main and post tasks where relevant):\n\n"
            f"{query}\n\n"
            "Rules:\n"
            "- Output ONLY numbered lines (no headings, no explanation). Example:\n"
            "  1. Check service status\n"
            "  2. Restart service\n"
            "  ...\n"
            "  10. Verify logs\n"
            "- DO NOT include Ansible installation steps, package installation steps, or documentation steps.\n"
            "- Keep each step short (one line).\n"
            "- If you cannot produce 10, output as many as you can and the caller will request a strict re-output."
        )

        ai_response = await script_util.generate_script(query=prompt_steps)
        logger.info("AI response (steps)", response=ai_response)

        if not ai_response:
            raise Exception("Empty AI response for steps")

        ai_response_str = str(ai_response)
        # Remove common headings if model included them
        ai_response_str = ai_response_str.replace("Pre-tasks:", "").replace("Main tasks:", "").replace("Post-tasks:", "")

        # Extract numbered steps robustly (accepts "1. x", "1) x", "1 - x")
        step_matches = re.findall(r"^\s*\d+\s*[\.\-\)]\s*(.+)$", ai_response_str, flags=re.MULTILINE)

        # Retry once if not exactly 10
        if len(step_matches) != 10:
            logger.info("AI returned %d steps, retrying to coerce to exactly 10", len(step_matches))
            ai_response_retry = await script_util.generate_script(
                query=prompt_steps + "\n\nIf you did not provide exactly 10 numbered steps, please re-output exactly 10 now."
            )
            logger.info("AI retry response (steps)", response=ai_response_retry)
            ai_response_retry_str = str(ai_response_retry) if ai_response_retry else ai_response_str
            ai_response_retry_str = ai_response_retry_str.replace("Pre-tasks:", "").replace("Main tasks:", "").replace("Post-tasks:", "")
            step_matches = re.findall(r"^\s*\d+\s*[\.\-\)]\s*(.+)$", ai_response_retry_str, flags=re.MULTILINE)

        # Deterministic padding/truncation to ensure exactly 10 steps
        steps: List[str] = []
        if len(step_matches) >= 10:
            steps = [s.strip() for s in step_matches[:10]]
        else:
            steps = [s.strip() for s in step_matches]
            while len(steps) < 10:
                steps.append(f"Implementation step {len(steps) + 1} for {name}")

        # -------------------------
        # 2) Prepare local project and write consolidated steps.md
        # -------------------------
        git_util = GitUtil()
        local_path = git_util.update_copy(name)
        logger.info("Local path prepared", path=local_path)

        steps_md_path = git_util.write_steps_md(name, steps)

        # -------------------------
        # 3) For each step ask LLM for YAML tasks, sanitize and assemble playbook
        # -------------------------
        playbook_header = (
            "---\n"
            f"- name: {name}\n"
            "  hosts: all\n"
            "  become: yes  # Run tasks with privilege escalation (e.g., sudo)\n"
            "  gather_facts: yes  # Gather system facts about the remote hosts\n\n"
            "  tasks:\n"
        )

        task_snippets: List[str] = []

        for i, step in enumerate(steps, start=1):
            # Strict prompt for a single, well-formed YAML task block
            sub_query = (
                "You are an Ansible expert. Provide ONLY valid Ansible task YAML for the following single step.\n\n"
                "HARD RULES:\n"
                "- Output only YAML (no markdown fences, no commentary, no surrounding code blocks).\n"
                "- Produce ONE and only ONE '- name:' task block that implements this step.\n"
                "- Do NOT include top-level play headers (---, hosts:, gather_facts: etc.).\n"
                "- Do NOT provide multiple alternative commands, do NOT repeat the same task.\n"
                "- Avoid including installation or documentation tasks.\n\n"
                f"Step {i}: {step}\n"
            )

            sub_response = await script_util.generate_script(query=sub_query)
            logger.info("AI YAML response for Step %d", i, response=sub_response)

            # Convert to string and do basic cleanup
            ai_text = str(sub_response or "").strip()

            # Quick rejection if response clearly contains an error/quota
            if re.search(r"Quota exceeded|ERROR:|quota_metric", ai_text, flags=re.IGNORECASE):
                logger.warning("LLM returned an error/quota message for step %d", i)
                cleaned = ""
            else:
                # 1) Use GitUtil sanitizer for typical wrappers (this should remove fences, usage=..., content=... etc.)
                cleaned = git_util._sanitize_yaml_content(ai_text)

                # 2) Convert escaped newline sequences into actual newlines (some connectors return "\n")
                if "\\n" in cleaned:
                    cleaned = cleaned.replace("\\n", "\n")

                # 3) Strip outer quotes if still present
                if (cleaned.startswith("'") and cleaned.endswith("'")) or (cleaned.startswith('"') and cleaned.endswith('"')):
                    cleaned = cleaned[1:-1].strip()

                # 4) Remove any trailing "usage=None" or similar tokens that slipped through
                cleaned = re.sub(r"\busage\s*=\s*None\b", "", cleaned)
                cleaned = re.sub(r"\busage\s*:\s*None\b", "", cleaned)
                cleaned = re.sub(r"\bcontent\s*=\s*['\"].*?['\"]", "", cleaned)

                # 5) If model returned multiple '- name:' blocks, keep only the first (we want one clear task per step)
                blocks = re.findall(r"(?s)(^- name:.*?)(?=(?:\n- name:)|\Z)", cleaned, flags=re.MULTILINE)
                if blocks:
                    # choose first non-empty block that contains '- name:'
                    first_block = None
                    for b in blocks:
                        if "- name:" in b:
                            first_block = b.strip()
                            break
                    cleaned = first_block if first_block else blocks[0].strip()
                else:
                    # If no '- name:' found, keep cleaned as-is and handle fallback later
                    cleaned = cleaned.strip()

                # 6) Remove any leading 'tasks:' wrapper if present
                if cleaned.lower().startswith("tasks:"):
                    cleaned = "\n".join(cleaned.splitlines()[1:]).strip()

            # If sanitized cleaned is empty or invalid, produce fallback debug task
            if not cleaned or "- name:" not in cleaned:
                cleaned = (
                    f"- name: Implementation step {i} for {name}\n"
                    "  debug:\n"
                    "    msg: 'No valid YAML returned by AI for this step; manual implementation required.'"
                )

            # Ensure final cleaned text has no stray error lines
            cleaned_lines = [ln for ln in cleaned.splitlines() if not re.search(r"Quota exceeded|ERROR:|quota_metric", ln, flags=re.IGNORECASE)]
            cleaned = "\n".join(cleaned_lines).strip()

            # Indent each line by FOUR spaces so it sits correctly under "  tasks:" (two spaces for play + two extra)
            indented = "\n".join([("    " + ln if ln.strip() else "") for ln in cleaned.splitlines()])
            task_snippets.append(indented)

            # Append step details into README (single file). If GitUtil.update_readme still creates step_N.md,
            # the fallback will append to README directly.
            try:
                git_util.update_readme(name, f"Step {i}: {step}\n\nAI YAML:\n{cleaned}", i)
            except Exception:
                try:
                    readme_path = os.path.join(git_util._ensure_path(name), "README.md")
                    with open(readme_path, "a", encoding="utf-8") as rf:
                        rf.write(f"\n\n### Step {i}\nStep: {step}\n\nAI YAML:\n{cleaned}\n")
                except Exception as e:
                    logger.warning("Failed to append to README directly for step %d: %s", i, str(e))

        # -------------------------
        # 4) Combine playbook and write/push
        # -------------------------
        playbook = playbook_header + "\n".join(task_snippets) + "\n"

        git_util.git_project_create(
            name,
            content=playbook,
            readme_content="\n".join([f"Step {i}: {s}" for i, s in enumerate(steps, start=1)]),
        )

        git_url, git_branch = git_util.git_project_push(name, uid)

        # Tower (best-effort)
        project_id = AnsibleUtil.create_project(name, git_branch)
        time.sleep(3)
        template_id = AnsibleUtil.create_template(name, project_id) if project_id else None

        # Persist metadata
        await services.insert_script_record(
            usecase_id=uid,
            git_url=git_url,
            git_branch=git_branch,
            ansible_project_id=project_id,
            ansible_template_id=template_id,
            steps_count=len(steps),
        )

        return {
            "success": True,
            "message": "Script created and stored successfully",
            "data": {
                "git_url": git_url,
                "git_branch": git_branch,
                "project_id": project_id,
                "template_id": template_id,
                "total_steps": len(steps),
                "steps_md": steps_md_path,
            },
        }

    except Exception as exc:
        logger.error("Script creation failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Script creation failed: {str(exc)}")
