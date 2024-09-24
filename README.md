1. 进入虚拟环境
source myenv/bin/activate  

2. 本地运行
python3 app.py

3. 发布运行
gunicorn -w 4 -b 0.0.0.0:8000 app:app 
