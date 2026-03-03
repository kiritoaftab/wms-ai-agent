python3 -m venv .venv 
source .venv/bin/activate
pip install -r requirements.txt 

# for dev 
uvicorn app.main:app --reload --port 8000

#for stage/prod
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4