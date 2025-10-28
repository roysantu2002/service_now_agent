"""Script Creator and Use Case endpoints."""
#script_creator.py

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from datetime import datetime
import structlog
import re
import time

from app.services.script_services import ScriptServices
from app.services.script_writer import ScriptUtil
from app.utils.git_util import GitUtil
from app.utils.ansible_lib import AnsibleUtil
# from app.utils.email_util import NotifyEmail

logger = structlog.get_logger(__name__)
router = APIRouter()

# Lazy dependencies
def get_script_services():
    return ScriptServices()

def get_script_util(provider: Optional[str] = Query(None)):
    return ScriptUtil(provider_name=provider)


# ------------------------------------------------------------
# Submit Use Case
# ------------------------------------------------------------
@router.post("/usecases/submit", summary="Submit a new automation use case")
async def submit_usecase(
    payload: Dict[str, Any] = Body(..., example={
        "name": "Restart Nginx",
        "description": "Generate an Ansible playbook to restart nginx service",
        "tech_comment": "Include pre-check for service status."
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
    except Exception as e:
        logger.error("Failed to submit use case", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error submitting use case: {str(e)}")


# ------------------------------------------------------------
# Fetch Use Case
# ------------------------------------------------------------
@router.get("/usecases/{uid}", summary="Fetch use case details")
async def fetch_usecase(
    uid: str,
    services: ScriptServices = Depends(get_script_services),
):
    try:
        data = await services.get_usecase(uid)
        if not data:
            raise HTTPException(status_code=404, detail=f"Use case {uid} not found")
        return {"success": True, "data": data}
    except Exception as e:
        logger.error("Error fetching use case", uid=uid, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error fetching use case: {str(e)}")


# ------------------------------------------------------------
# Script Creator
# ------------------------------------------------------------
@router.post("/script/create", summary="Generate automation script for use case")
async def create_script(
    payload: Dict[str, Any] = Body(..., example={
        "uid": "UC-1730123456",
        "name": "Restart Nginx",
        "query": "Create an Ansible playbook to restart nginx service on Ubuntu."
    }),
    provider: Optional[str] = Query(None),
    script_util=Depends(get_script_util),
    services: ScriptServices = Depends(get_script_services),
):
    uid = payload.get("uid")
    name = payload.get("name")
    query = payload.get("query")

    try:
        # --- AI Script Generation ---
        ai_response = await script_util.generate_script(query=query)
        if not ai_response:
            raise Exception("Empty AI response")

        formatted_data = re.sub(r'\b\d+\.\s', '', ai_response).strip()
        steps = [s for s in formatted_data.splitlines() if s.strip()]

        # --- Initialize Git Utility ---
        git_util = GitUtil()

        # --- Prepare project locally ---
        local_path = git_util.update_copy(name)
        print(f"✅ Local path prepared: {local_path}")

        # --- Generate step-wise YAML content ---
        playbook = ""
        for i, step in enumerate(steps, start=1):
            sub_query = f"Provide ansible code for: {step}"
            sub_response = await script_util.generate_script(query=sub_query)
            playbook += sub_response + "\n"

            # log step creation
            git_util.update_readme(name, f"Step {i}: {step}\n{sub_response}", i)
            print(f"🪶 Step {i} added to {name}")

        # --- Create and push Git project ---
        git_util.git_project_create(name, playbook)
        git_url, git_branch = git_util.git_project_push(name, uid)

        # --- Ansible Project Creation ---
        project_id = AnsibleUtil.create_project(name, git_branch)
        time.sleep(3)
        template_id = AnsibleUtil.create_template(name, project_id)

        # --- Persist metadata in DB ---
        await services.insert_script_record(
            usecase_id=uid,
            git_url=git_url,
            git_branch=git_branch,
            ansible_project_id=project_id,
            ansible_template_id=template_id,
            steps_count=len(steps),
        )

        print(f"✅ Script creation completed for {name}")
        return {
            "success": True,
            "message": "Script created and stored successfully",
            "data": {
                "git_url": git_url,
                "git_branch": git_branch,
                "project_id": project_id,
                "template_id": template_id,
                "total_steps": len(steps),
            },
        }

    except Exception as e:
        logger.error("Script creation failed", error=str(e))
        try:
            print(f"❌ Error creating script for {name} ({uid}): {str(e)}")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Script creation failed: {str(e)}")
