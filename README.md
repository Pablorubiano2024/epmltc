para correr la aplicacion:

verificar ruta cd "/Users/pablorubiano/Library/CloudStorage/OneDrive-Personal/MAESTRIA/tesis_epm/epmltc"

En una terminal:

1. poetry run python etl/etl_consolidado.py

2. correr el modelo: poetry run python ml/train_model.py


En otra terminal

1. conda activate epm_ltc

2. correr el backend: poetry run uvicorn backend.main:app --reload

En otra terminal 

1. conda activate epm_ltc

2. poetry run streamlit run frontend/app.py