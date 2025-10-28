"""
script_creator.py

Generates an Ansible playbook and supporting files from an AI-generated set of
10 resolution steps. Writes a single `steps.md`, individual `step_N.md` files,
creates a consolidated playbook YAML, initializes a local git project, and
optionally creates an Ansible Tower project/template (best-effort).
"""

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


# ---------------------- Use Case Endpoints ----------------------

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


# ---------------------- Script Creation ----------------------

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
    uid = payload.get("uid")
    name = payload.get("name")
    query = payload.get("query")

    if not (uid and name and query):
        raise HTTPException(status_code=400, detail="uid, name and query are required")

    try:
        # --- Request exactly 10 numbered steps ---
        prompt_steps = (
            "Provide exactly 10 numbered, concise resolution steps to achieve the following automation use case:\n"
            f"{query}\n\n"
            "Output as numbered lines like:\n1. Step one\n2. Step two\n...\n10. Step ten"
        )

        ai_response = await script_util.generate_script(query=prompt_steps)
        logger.info("AI response (steps)", response=ai_response)

        if not ai_response:
            raise Exception("Empty AI response for steps")

        # --- Extract numbered steps robustly ---
        step_matches = re.findall(r"^\s*\d+\.\s*(.+)$", ai_response, flags=re.MULTILINE)

        # If not 10, retry once asking explicitly for a strict reformat
        if len(step_matches) != 10:
            logger.info("AI returned %d steps, retrying to coerce to exactly 10", len(step_matches))
            ai_response_retry = await script_util.generate_script(
                query=(prompt_steps + "\n\nIf you did not provide exactly 10 numbered steps, please re-output exactly 10 now."),
            )
            logger.info("AI retry response (steps)", response=ai_response_retry)
            step_matches = re.findall(r"^\s*\d+\.\s*(.+)$", ai_response_retry or ai_response, flags=re.MULTILINE)

        # Deterministic padding/truncation to ensure exactly 10 steps
        steps: List[str] = []
        if len(step_matches) >= 10:
            steps = [s.strip() for s in step_matches[:10]]
        else:
            steps = [s.strip() for s in step_matches]
            while len(steps) < 10:
                steps.append(f"Implementation step {len(steps) + 1} for {name}")

        # --- Prepare local project and write steps ---
        git_util = GitUtil()
        local_path = git_util.update_copy(name)
        logger.info("Local path prepared", path=local_path)

        steps_md_path = git_util.write_steps_md(name, steps)

        # Compose playbook header
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
            sub_query = (
                f"Provide a valid Ansible YAML snippet for the following step:\n"
                f"Step {i}: {step}\n\n"
                "Ensure it begins with '- name:' and includes one or more valid tasks only. "
                "Do NOT include markdown fences or explanations."
            )

            sub_response = await script_util.generate_script(query=sub_query)
            logger.info(f"AI YAML response for Step {i}", response=sub_response)

            cleaned = git_util._sanitize_yaml_content(sub_response)

            # Proper YAML indentation for inclusion under tasks
            indented = "\n".join(
                [("    " + line if line.strip() else "") for line in cleaned.splitlines()]
            )
            task_snippets.append(indented)

            # Update README with actual AI content
            git_util.update_readme(name, f"Step {i}: {step}\n{sub_response}", i)

        # --- Combine everything ---
        playbook = playbook_header + "\n".join(task_snippets) + "\n"

        # Create and push git project
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
