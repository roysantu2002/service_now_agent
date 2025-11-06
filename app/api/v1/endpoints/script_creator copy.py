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


# ---------------------- Dependencies ----------------------


def get_script_services() -> ScriptServices:
    return ScriptServices()


def get_script_util(provider: Optional[str] = Query(None)) -> ScriptUtil:
    return ScriptUtil(provider_name=provider)


# ---------------------- Helpers ----------------------


def _extract_numbered_steps(text: str) -> List[str]:
    """
    Extract numbered lines like:
      1. Do something
      2. Do something else
    Returns list of step texts (without numbers).
    """
    if not text:
        return []
    # Accept variations: "1. Step", "1) Step", "1 - Step"
    matches = re.findall(r"^\s*\d+\s*[\.\-\)]\s*(.+)$", text, flags=re.MULTILINE)
    if not matches:
        # fallback: lines that look like short sentences
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        # if there are many lines, take up to 10
        return lines[:10]
    return [m.strip() for m in matches]


def _normalize_snippet(snippet: str, git_util: GitUtil, step_index: int, usecase_name: str) -> str:
    """
    Use git_util._sanitize_yaml_content to clean the AI response and
    return a YAML snippet ready to be indented and appended under tasks:.
    Ensures the snippet contains at least '- name:'; otherwise returns an empty string.
    """
    cleaned = git_util._sanitize_yaml_content(snippet or "")
    if not cleaned:
        return ""

    # If AI returned wrapper "tasks:" remove it
    lines = cleaned.splitlines()
    if lines and lines[0].strip().lower().startswith("tasks:"):
        # drop first line
        cleaned = "\n".join(lines[1:]).strip()

    # Ensure the snippet starts with '- name:'; if not, try to salvage by creating a wrapper
    if "- name:" not in cleaned:
        # Use the first non-empty line as summary for fallback
        first_line = ""
        for ln in cleaned.splitlines():
            if ln.strip():
                first_line = ln.strip()
                break
        if first_line:
            cleaned = f"- name: {first_line}\n  debug:\n    msg: 'Auto-generated task; please review and replace with intended Ansible tasks.'"
        else:
            return ""

    # Remove any stray "content=" or "usage=" artifacts remaining
    cleaned = re.sub(r"\bcontent\s*=\s*['\"].*?['\"]", "", cleaned)
    cleaned = re.sub(r"\busage\s*=\s*None\b", "", cleaned)
    cleaned = re.sub(r"\busage\s*:\s*None\b", "", cleaned)

    return cleaned.strip()


# ---------------------- Use Case Endpoints ----------------------


@router.post("/usecases/submit", summary="Submit a new automation use case")
async def submit_usecase(
    payload: Dict[str, Any] = Body(
        ...,
        example={
            "name": "Restart Nginx",
            "description": "Generate an Ansible playbook to restart nginx service",
            "tech_comment": "Include pre-check for service status.",
        },
    ),
    services: ScriptServices = Depends(get_script_services),
):
    try:
        uid = await services.insert_usecase(
            name=payload["name"],
            description=payload.get("description", ""),
            tech_comment=payload.get("tech_comment", ""),
        )

        return JSONResponse(
            content={
                "success": True,
                "uid": uid,
                "message": "Use case submitted successfully",
            },
            status_code=201,
        )
    except Exception as exc:
        logger.error("Failed to submit use case", error=str(exc))
        raise HTTPException(
            status_code=500, detail=f"Error submitting use case: {str(exc)}"
        )


@router.get("/usecases/{uid}", summary="Fetch use case details")
async def fetch_usecase(
    uid: str, services: ScriptServices = Depends(get_script_services)
):
    try:
        data = await services.get_usecase(uid)
        if not data:
            raise HTTPException(status_code=404, detail=f"Use case {uid} not found")
        return {"success": True, "data": data}
    except Exception as exc:
        logger.error("Error fetching use case", uid=uid, error=str(exc))
        raise HTTPException(
            status_code=500, detail=f"Error fetching use case: {str(exc)}"
        )


# ---------------------- Script Creation ----------------------


@router.post("/script/create", summary="Generate automation script for use case")
async def create_script(
    payload: Dict[str, Any] = Body(
        ...,
        example={
            "uid": "UC-1730123456",
            "name": "Restart Nginx",
            "query": "Create an Ansible playbook to restart nginx service on Ubuntu.",
        },
    ),
    provider: Optional[str] = Query(None),
    script_util: ScriptUtil = Depends(get_script_util),
    services: ScriptServices = Depends(get_script_services),
):
    uid = payload.get("uid")
    name = payload.get("name")
    query = payload.get("query")

    if not (uid and name and query):
        raise HTTPException(status_code=400, detail="uid, name and query are required")

    try:
        # -------------------------
        # 1) Ask AI for exactly 10 numbered steps (strict instructions)
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
            "- Keep each step short (one line)."
        )

        ai_response = await script_util.generate_script(query=prompt_steps)
        logger.info("AI response (steps)", response=ai_response)

        if not ai_response:
            raise Exception("Empty AI response for steps")

        # normalize common headings AI might add
        ai_response_str = str(ai_response)
        for header in ("Pre-tasks:", "Main tasks:", "Post-tasks:"):
            ai_response_str = ai_response_str.replace(header, "")

        # Extract numbered steps robustly
        step_matches = _extract_numbered_steps(ai_response_str)

        # If not 10, retry once asking explicitly for a strict reformat
        if len(step_matches) != 10:
            logger.info(
                "AI returned %d steps, retrying to coerce to exactly 10", len(step_matches)
            )
            ai_response_retry = await script_util.generate_script(
                query=prompt_steps + "\n\nIf you did not provide exactly 10 numbered steps, please re-output exactly 10 now."
            )
            logger.info("AI retry response (steps)", response=ai_response_retry)
            step_matches = _extract_numbered_steps(str(ai_response_retry) or ai_response_str)

        # Deterministic padding/truncation to ensure exactly 10 steps
        steps: List[str] = []
        if len(step_matches) >= 10:
            steps = [s.strip() for s in step_matches[:10]]
        else:
            steps = [s.strip() for s in step_matches]
            while len(steps) < 10:
                steps.append(f"Implementation step {len(steps) + 1} for {name}")

        # -------------------------
        # 2) Prepare local project and write steps.md (single file)
        # -------------------------
        git_util = GitUtil()
        local_path = git_util.update_copy(name)
        logger.info("Local path prepared", path=local_path)

        # write consolidated steps.md (single file)
        steps_md_path = git_util.write_steps_md(name, steps)

        # -------------------------
        # 3) For each step ask AI for Ansible YAML tasks, sanitize and assemble playbook
        # -------------------------
        playbook_header = (
            "---\n"
            f"- name: {name}\n"
            "  hosts: all\n"
            "  become: yes\n"
            "  gather_facts: yes\n\n"
            "  tasks:\n"
        )

        task_snippets: List[str] = []

        for i, step in enumerate(steps, start=1):
            sub_query = (
                "You are an Ansible expert. Provide ONLY valid Ansible task YAML for the following single step.\n"
                "Rules:\n"
                "- Output only YAML (no markdown fences, no commentary, no surrounding code blocks).\n"
                "- Do NOT include top-level play or 'hosts:' or 'gather_facts:'.\n"
                "- Do NOT include installation or documentation tasks.\n"
                "- Start your YAML with '- name:' and include the task definition(s).\n\n"
                f"Step {i}: {step}\n"
            )

            sub_response = await script_util.generate_script(query=sub_query)
            logger.info("AI YAML response for Step %d", i, response=sub_response)

            # Use GitUtil sanitizer (robust) to clean LLM output
            cleaned_snippet = _normalize_snippet(sub_response, git_util, i, name)

            # If sanitizer returned empty, create a fallback debug task to keep playbook valid
            if not cleaned_snippet:
                cleaned_snippet = (
                    f"- name: Implementation step {i} for {name}\n"
                    "  debug:\n"
                    "    msg: 'No valid YAML returned by AI; manual implementation required.'"
                )

            # Ensure we don't keep an internal 'tasks:' wrapper
            if cleaned_snippet.strip().startswith("tasks:"):
                cleaned_snippet = "\n".join(cleaned_snippet.splitlines()[1:]).strip()

            # Indent each line by two spaces for inclusion under the top-level 'tasks:'
            indented = "\n".join([("  " + ln if ln.strip() else "") for ln in cleaned_snippet.splitlines()])
            task_snippets.append(indented)

            # Append details into README (single README file). Assuming GitUtil.update_readme appends to README.
            try:
                git_util.update_readme(name, f"Step {i}: {step}\n\nAI YAML:\n{cleaned_snippet}", i)
            except Exception:
                # If update_readme still writes step_N.md in your GitUtil, fallback to writing README directly
                readme_path = git_util._ensure_path(name) + "/README.md"
                try:
                    with open(readme_path, "a", encoding="utf-8") as rf:
                        rf.write(f"\n\n### Step {i}\nStep: {step}\n\nAI YAML:\n{cleaned_snippet}\n")
                except Exception as e:
                    logger.warning("Failed to append to README directly: %s", str(e))

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
        # small wait to allow Tower to register project
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
        raise HTTPException(
            status_code=500, detail=f"Script creation failed: {str(exc)}"
        )

@router.get("/usecases/{uid}", summary="Fetch use case details")
async def fetch_usecase(
    uid: str, services: ScriptServices = Depends(get_script_services)
):
    try:
        data = await services.get_usecase(uid)
        if not data:
            raise HTTPException(status_code=404, detail=f"Use case {uid} not found")
        return {"success": True, "data": data}
    except Exception as exc:
        logger.error("Error fetching use case", uid=uid, error=str(exc))
        raise HTTPException(
            status_code=500, detail=f"Error fetching use case: {str(exc)}"
        )


# ---------------------- Script Creation ----------------------


# @router.post("/script/create", summary="Generate automation script for use case")
# async def create_script(
#     payload: Dict[str, Any] = Body(
#         ...,
#         example={
#             "uid": "UC-1730123456",
#             "name": "Restart Nginx",
#             "query": "Create an Ansible playbook to restart nginx service on Ubuntu.",
#         },
#     ),
#     provider: Optional[str] = Query(None),
#     script_util: ScriptUtil = Depends(get_script_util),
#     services: ScriptServices = Depends(get_script_services),
# ):
#     uid = payload.get("uid")
#     name = payload.get("name")
#     query = payload.get("query")

#     if not (uid and name and query):
#         raise HTTPException(status_code=400, detail="uid, name and query are required")

#     try:
#         # --- Request exactly 10 numbered steps ---
#         prompt_steps = (
#             f"Give all the task names (pre, main, and post) required to automate "
#             f"{query} use case in Ansible. Exclude Ansible installation, other package "
#             f"installations, documentation steps. Provide exactly 10 numbered tasks as:\n"
#             "1. Task one\n2. Task two\n...\n10. Task ten"
#         )

#         ai_response = await script_util.generate_script(query=prompt_steps)
#         logger.info("AI response (steps)", response=ai_response)

#         if not ai_response:
#             raise Exception("Empty AI response for steps")

#         # --- Extract numbered steps robustly ---
#         step_matches = re.findall(r"^\s*\d+\.\s*(.+)$", ai_response, flags=re.MULTILINE)

#         # If not 10, retry once asking explicitly for a strict reformat
#         if len(step_matches) != 10:
#             logger.info(
#                 "AI returned %d steps, retrying to coerce to exactly 10",
#                 len(step_matches),
#             )
#             ai_response_retry = await script_util.generate_script(
#                 query=(
#                     prompt_steps
#                     + "\n\nIf you did not provide exactly 10 numbered steps, please re-output exactly 10 now."
#                 ),
#             )
#             logger.info("AI retry response (steps)", response=ai_response_retry)
#             step_matches = re.findall(
#                 r"^\s*\d+\.\s*(.+)$",
#                 ai_response_retry or ai_response,
#                 flags=re.MULTILINE,
#             )

#         # Deterministic padding/truncation to ensure exactly 10 steps
#         steps: List[str] = []
#         if len(step_matches) >= 10:
#             steps = [s.strip() for s in step_matches[:10]]
#         else:
#             steps = [s.strip() for s in step_matches]
#             while len(steps) < 10:
#                 steps.append(f"Implementation step {len(steps) + 1} for {name}")

#         # --- Prepare local project and write steps ---
#         git_util = GitUtil()
#         local_path = git_util.update_copy(name)
#         logger.info("Local path prepared", path=local_path)

#         steps_md_path = git_util.write_steps_md(name, steps)

#         # Compose playbook header
#         playbook_header = (
#             "---\n"
#             f"- name: {name}\n"
#             "  hosts: all\n"
#             "  become: yes  # Run tasks with privilege escalation (e.g., sudo)\n"
#             "  gather_facts: yes  # Gather system facts about the remote hosts\n\n"
#             "  tasks:\n"
#         )

#         task_snippets: List[str] = []

#         for i, step in enumerate(steps, start=1):
#             sub_query = (
#                 f"Provide a valid Ansible YAML snippet for the following step:\n"
#                 f"Step {i}: {step}\n\n"
#                 "Ensure it begins with '- name:' and includes one or more valid tasks only. "
#                 "Do NOT include markdown fences or explanations."
#             )

#             sub_response = await script_util.generate_script(query=sub_query)
#             logger.info(f"AI YAML response for Step {i}", response=sub_response)

#             cleaned = git_util._sanitize_yaml_content(sub_response)

#             # Proper YAML indentation for inclusion under tasks
#             indented = "\n".join(
#                 [
#                     ("    " + line if line.strip() else "")
#                     for line in cleaned.splitlines()
#                 ]
#             )
#             task_snippets.append(indented)

#             # Update README with actual AI content
#             git_util.update_readme(name, f"Step {i}: {step}\n{sub_response}", i)

#         # --- Combine everything ---
#         playbook = playbook_header + "\n".join(task_snippets) + "\n"

#         # Create and push git project
#         git_util.git_project_create(
#             name,
#             content=playbook,
#             readme_content="\n".join(
#                 [f"Step {i}: {s}" for i, s in enumerate(steps, start=1)]
#             ),
#         )

#         git_url, git_branch = git_util.git_project_push(name, uid)

#         # Tower (best-effort)
#         project_id = AnsibleUtil.create_project(name, git_branch)
#         time.sleep(3)
#         template_id = (
#             AnsibleUtil.create_template(name, project_id) if project_id else None
#         )

#         # Persist metadata
#         await services.insert_script_record(
#             usecase_id=uid,
#             git_url=git_url,
#             git_branch=git_branch,
#             ansible_project_id=project_id,
#             ansible_template_id=template_id,
#             steps_count=len(steps),
#         )

#         return {
#             "success": True,
#             "message": "Script created and stored successfully",
#             "data": {
#                 "git_url": git_url,
#                 "git_branch": git_branch,
#                 "project_id": project_id,
#                 "template_id": template_id,
#                 "total_steps": len(steps),
#                 "steps_md": steps_md_path,
#             },
#         }

#     except Exception as exc:
#         logger.error("Script creation failed", error=str(exc))
#         raise HTTPException(
#             status_code=500, detail=f"Script creation failed: {str(exc)}"
#         )
