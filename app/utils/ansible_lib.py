# ansible_lib.py

import os
import json
import requests
import datetime
from dotenv import load_dotenv
import random

# Load environment variables
load_dotenv()

"""Ansible Tower Configuration"""
# Uncomment these if you want to use environment variables
# project_tower_base_url = os.getenv("DEV_TOWER_URL_PROJECT")
# template_tower_base_url = os.getenv("DEV_TOWER_URL_TEMPLATE")
# tower_token = os.getenv("DEV_TOWER_TOKEN")

# Static fallback configuration
project_tower_base_url = "https://aap-dev.com/api/v2/projects/"
template_tower_base_url = "https://aap-dev.com/api/v2/job_templates/"
tower_token = ""  # Ideally fetched from env or secret manager

print(f"Using Tower Token: {tower_token}")

tower_headers = {
    "Authorization": f"Bearer {tower_token}",
    "Content-Type": "application/json"
}

git_url = ""  # Set your Git repository URL here


class AnsibleUtil:
    @staticmethod
    def create_project(usecase_name: str, branch: str) -> int | None:
        """Create a new project in Ansible Tower."""
        try:
            project_payload = {
                "name": usecase_name,
                "description": usecase_name,
                "scm_type": "git",
                "scm_url": git_url,
                "scm_branch": branch,
                "credential": 245,
                "timeout": 0,
                "organization": 838,
                "scm_update_cache_timeout": 0,
            }

            response = requests.post(
                project_tower_base_url,
                headers=tower_headers,
                data=json.dumps(project_payload),
                verify=False
            )

            if response.status_code not in [200, 201]:
                print(f"❌ Failed to create project: {response.status_code} - {response.text}")
                return None

            response_dict = response.json()
            project_id = response_dict.get("id")

            print(f"✅ Ansible project created successfully — Project Name: {usecase_name}, ID: {project_id}")
            return project_id

        except Exception as e:
            print(f"⚠️ Error while creating Ansible project: {e}")
            return None

    @staticmethod
    def create_template(usecase_name: str, project_id: int) -> int | None:
        """Create a new job template in Ansible Tower."""
        try:
            template_payload = {
                "name": usecase_name,
                "description": "Craftbot",
                "job_type": "run",
                "inventory": 134,
                "project": project_id,
                "playbook": "main.yml",
                "scm_branch": "",
                "forks": 0,
                "limit": "",
                "verbosity": 0,
                "extra_vars": "---",
                "organization": 838,
            }

            response = requests.post(
                template_tower_base_url,
                headers=tower_headers,
                data=json.dumps(template_payload),
                verify=False
            )

            if response.status_code not in [200, 201]:
                print(f"❌ Failed to create template: {response.status_code} - {response.text}")
                return None

            response_dict = response.json()
            template_id = response_dict.get("id")

            print(f"✅ Ansible Job Template created successfully — Template Name: {usecase_name}, ID: {template_id}")
            return template_id

        except Exception as e:
            print(f"⚠️ Error while creating Ansible template: {e}")
            return None


if __name__ == "__main__":
    # Example usage
    project_id = AnsibleUtil.create_project("test_usecase", "main")
    if project_id:
        AnsibleUtil.create_template("test_usecase", project_id)
