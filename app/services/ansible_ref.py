def generate_response(uid, name, comment):
    try:
        print(f"uid is == {uid}")
        id = str(uid)
        logging.info(f"Usecase ID: {uid}\nUsecase Name: {name}")

        playbook = ""
        print(comment)

        query1 = (
            f"Give all the task names (pre, main, and post) required to automate "
            f"{comment} use case in ansible. Exclude ansible installation, other "
            f"package installations, documentation steps."
        )

        logging.info("Prompt Passed to OpenAI: " + str(query1))

        try:
            print("Inside generate_response")
            al_content = OpenAIPromptutil.call_Prompt(name, query1)
        except Exception as e:
            logging.error(str(e))
            al_content = ""

        try:
            if al_content != "":
                formatted_data = (
                    al_content
                        .replace("Pre-tasks:", "")
                        .replace("Main tasks:", "")
                        .replace("Post-tasks:", "")
                )

                pattern = re.compile(r'\b\d+\.\s')
                text = pattern.sub("", formatted_data)

                formatted_data_1 = "".join([s for s in text.strip().splitlines(True) if s.strip()])
                formatted_data2 = list(formatted_data_1.splitlines())
                print(formatted_data2)
            else:
                logging.error("No response received for the prompt")
                print("No response received for the prompt")
        except Exception as e:
            logging.error("Failed to format OpenAI prompt response: " + str(e))
            formatted_data2 = []

        try:
            i = 0
            Gitutil.Updatecopy(name)

            for item in formatted_data2:
                i += 1
                step_detail = ""

                query2 = f"Provide ansible code for: {item}"
                logging.info("Prompt Passed to OpenAI: " + str(query2))

                ai_content2 = OpenAIPromptutil.call_Prompt(name, query2)

                if "***" in ai_content2:
                    ai_op = ai_content2.split("***")[1]
                else:
                    ai_op = ai_content2

                if "tasks:" in ai_op:
                    playbook = playbook + ai_op.split("tasks:")[1]
                    step_response = ai_op.split("tasks:")[1]
                    step_detail += f"Step: {item}\nStep Response: {step_response}"
                else:
                    playbook = playbook + ai_op
                    step_response = ai_op
                    step_detail += f"Step: {item}\nStep Response: {step_response}"

                print("STEP_DETAILS", step_detail)
                Gitutil.UpdateReadme(name, step_detail, i)

            logging.info("Successfully received the playbook from OpenAI")

        except Exception as e:
            logging.error("Failed to generate OpenAI prompt response for sub tasks: " + str(e))

        content1 = str(playbook)

        try:
            if playbook != "" and al_content != "":
                Gitutil.git_project_create(name, playbook, al_content)
                git_project_url = Gitutil.git_project_push(name, id)

                git_url = git_project_url[0]
                git_branch = git_project_url[1]

                print("GIT BRANCH ", git_branch)
                logging.info("Successfully pushed the playbook to Git URL: " + str(git_project_url))
            else:
                print("Git Project Error")
                logging.error("Failed to create Git Project")
                git_project_url = None

            if git_project_url:
                project_id = Ansibleutil.create_project(name, git_branch)
                logging.info("Ansible AAP Project ID: " + str(project_id))
            else:
                logging.error("Failed to push the code to git")
                project_id = ""

            time.sleep(30)

            if project_id != "":
                temp_id = Ansibleutil.create_template(name, project_id)
                logging.info("Ansible AAP Job template ID :" + str(temp_id))
            else:
                print("Error in Ansible job template creation")
                logging.error("Failed to create Ansible AAP Job template")

            if not project_id or not git_project_url or not playbook:
                NotifyEmail.sendfailmail(name, id)
                logging.info("Failure email has been sent")

        except Exception as e:
            logging.error(str(e))

    except Exception as e:
        print(e)
        logging.error(str(e))
