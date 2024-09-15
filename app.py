from flask import Flask, render_template, request, redirect, url_for
import re
from datetime import datetime
import os

app = Flask(__name__)

# 定义要抓取的关键事件的正则表达式
event1_pattern = re.compile(r'.*device sleep.*')
event2_pattern = re.compile(r'.*Grab wakeuplock.*serviceName: (?!tsp-agent-hb|position-service).*')
event3_pattern = re.compile(r'.*Start setting pin.*')
event4_pattern = re.compile(r'.*GPIO wakeup.*')
event5_pattern = re.compile(r'.*Ping success for 5 times.*')
event6_pattern = re.compile(r'.*Release wakeuplock, serviceName: (?!tsp-agent-hb|position-service).*')
event7_pattern = re.compile(r'.*unlock ECU:.*')
event8_pattern = re.compile(r'.*lock ECU:.*')
service_tsp_pattern = re.compile(r'.*service tsp-agent-hb.*')

# 定义要移除的模式
remove_pattern = re.compile(r'\[W\] \[PowerManager\]')
remove_unwanted_part_pattern = re.compile(r'\[\d+-\d+\]  \[.*?:.*?:\d+\]')

# 定义时间戳正则表达式模式
timestamp_pattern = re.compile(r'\[(\d{14}\.\d{3})\]')

def process_log_file(log_content, output_file_path):
    previous_line = ""
    previous_event = None
    result_lines = []
    with open(output_file_path, 'w') as output_file:
        for line in log_content.splitlines():
            if (event1_pattern.match(line) or event2_pattern.match(line) or 
                event3_pattern.match(line) or event4_pattern.match(line) or 
                event5_pattern.match(line) or event6_pattern.match(line) or 
                (event7_pattern.match(line) and not service_tsp_pattern.match(previous_line)) or
                (event8_pattern.match(line) and not service_tsp_pattern.match(previous_line))):
                
                match = timestamp_pattern.search(line)
                if match:
                    timestamp_str = match.group(1)
                    timestamp = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S.%f')
                    readable_time = timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    line_with_both_timestamps = line.replace(timestamp_str, f"{timestamp_str} ({readable_time})")
                
                    cleaned_line = remove_pattern.sub('', line_with_both_timestamps).strip()
                    cleaned_line = remove_unwanted_part_pattern.sub('', cleaned_line).strip()
                    
                    if "Grab wakeuplock" in cleaned_line:
                        service_name_match = re.search(r'serviceName: (\S+)', cleaned_line)
                        if service_name_match:
                            service_name = service_name_match.group(1)
                            cleaned_line = f"[{timestamp_str} ({readable_time})]  {service_name}  维持唤醒锁 ---------"
                    if "Release wakeuplock" in cleaned_line:
                        service_name_match = re.search(r'serviceName: (\S+)', cleaned_line)
                        if service_name_match:
                            service_name = service_name_match.group(1)
                            cleaned_line = f"[{timestamp_str} ({readable_time})]  {service_name}  释放唤醒锁"
                    
                    if "device sleep" in cleaned_line:
                        cleaned_line = f"[{timestamp_str} ({readable_time})]  SAF进入休眠"
                    
                    if "unlock ECU:" in cleaned_line:
                        if "unlock ECU: 1" in cleaned_line:
                            cleaned_line = f"[{timestamp_str} ({readable_time})]  udpnm 释放唤醒VDF"
                        elif "unlock ECU: 2" in cleaned_line:
                            cleaned_line = f"[{timestamp_str} ({readable_time})]  udpnm 释放唤醒CDF"
                        elif "unlock ECU: 3" in cleaned_line:
                            cleaned_line = f"[{timestamp_str} ({readable_time})]  udpnm 释放唤醒ADF"
                        previous_event = "unlock"
                        
                    if "lock ECU:" in cleaned_line:
                        if "lock ECU: 1" in cleaned_line:
                            cleaned_line = f"[{timestamp_str} ({readable_time})]  udpnm 维持唤醒VDF"
                        elif "lock ECU: 2" in cleaned_line:
                            cleaned_line = f"[{timestamp_str} ({readable_time})]  udpnm 维持唤醒CDF"
                        elif "lock ECU: 3" in cleaned_line:
                            cleaned_line = f"[{timestamp_str} ({readable_time})]  udpnm 维持唤醒ADF"
                        elif "lock ECU: 0" in cleaned_line:
                            cleaned_line = f"[{timestamp_str} ({readable_time})]  udpnm 维持唤醒SAF"
                        previous_event = "lock"
                    if "Start setting pin" in cleaned_line:
                        cleaned_line = f"[{timestamp_str} ({readable_time})]  GPIO唤醒VDF"
                    
                    if "Ping success for 5 times, exit process." in cleaned_line:
                        cleaned_line = f"[{timestamp_str} ({readable_time})]  GPIO唤醒VDF成功！"
                    
                    result_lines.append(cleaned_line)
                    output_file.write(cleaned_line + '\n')
            previous_line = line
    return output_file_path

def manage_log_files(directory, max_files=10):
    files = sorted(
        (os.path.join(directory, f) for f in os.listdir(directory)),
        key=os.path.getmtime
    )
    while len(files) > max_files:
        os.remove(files.pop(0))

@app.route('/')
def index():
    return render_template('upload.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'logfile' not in request.files:
            return "No file part"
        
        file = request.files['logfile']
        
        if file.filename == '':
            return "No selected file"
        
        if file:
            try:
                log_content = file.read().decode('utf-8')
            except UnicodeDecodeError:
                try:
                    log_content = file.read().decode('latin-1')
                except UnicodeDecodeError:
                    return "File encoding not supported"
            
            output_file_path = f'processed_logs/{file.filename}'  # 保留原始文件名
            if not os.path.exists('processed_logs'):
                os.makedirs('processed_logs')
            result_file = process_log_file(log_content, output_file_path)
            manage_log_files('processed_logs')  # 管理日志文件数量
            return redirect(url_for('upload_file', filename=file.filename))
    
    filename = request.args.get('filename')
    result = []
    if filename:
        file_path = f'processed_logs/{filename}'
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                result = file.readlines()  # 显示所有记录
        else:
            result = ["文件不存在"]
    
    history_files = os.listdir('processed_logs') if os.path.exists('processed_logs') else []
    return render_template('upload.html', result=result, history_files=history_files, current_file=filename)

@app.route('/results')
def results():
    # 你可以在这里添加处理结果的逻辑
    return "Results page"

if __name__ == '__main__':
    app.run(debug=True)