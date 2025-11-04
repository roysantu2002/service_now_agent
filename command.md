uvicorn main:app --reload

tree -I "__pycache__|*.pyc|.git|.DS_Store|*.log|*.egg-info" > tree_clean.txt

tree -I "__pycache__|*.pyc|.git|.DS_Store|*.log|*.egg-info|venv|.venv|env|build|dist" > tree_clean.txt

mkdir -p knowledge-base/middleware knowledge-base/network knowledge-base/database

touch knowledge-base/middleware/middleware_intro.csv \
      knowledge-base/middleware/middleware_advanced.csv \
      knowledge-base/network/network_basics.csv \
      knowledge-base/network/network_security.csv \
      knowledge-base/database/database_types.csv \
      knowledge-base/database/database_scaling.csv
      

# https://dev281199.service-now.com/api/now/table/incident/b84662f4c3413610e66adaec050131e1?sysparm_display_value=true