# How to setup Agentic Project Agnostic Management Advisor

Python SDK's Requirements : Between 3.10.12 and 3.12.12

Environment Setup
conda create --name myenv python=3.10.12

conda init

conda activate python_312_env

python -m pip install pipenv

pipenv install --python 3.12.12

pipenv install ollama

pipenv install ipykernel

pipenv install crewai==0.28.8

pipenv install crewai-tools==0.1.6