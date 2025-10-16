uvicorn main:app --reload

tree -I "__pycache__|*.pyc|.git|.DS_Store|*.log|*.egg-info" > tree_clean.txt

tree -I "__pycache__|*.pyc|.git|.DS_Store|*.log|*.egg-info|venv|.venv|env|build|dist" > tree_clean.txt
