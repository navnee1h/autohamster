from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import csv
import os
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

FILE_PATH = 'plans.csv'

class CSVData:
    def __init__(self, file_path):
        self.file_path = file_path
        self.lock = threading.Lock()
        self.data = self.read_data()
        self.last_modified = os.path.getmtime(self.file_path)

    def read_data(self):
        with self.lock:
            with open(self.file_path, 'r') as file:
                reader = csv.reader(file)
                return [row for row in reader]

    def save_data(self, data):
        with self.lock:
            with open(self.file_path, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerows(data)
            self.data = data
            self.last_modified = os.path.getmtime(self.file_path)

    def is_modified(self):
        return os.path.getmtime(self.file_path) != self.last_modified

csv_data = CSVData(FILE_PATH)

def calculate_profit(updationMoney, returnMoney):
    if returnMoney == 0:
        raise ValueError("returnMoney must be a non-zero value.")
    return updationMoney / returnMoney

def process_and_sort_plans(data, limit):
    plans = []
    for row in data:
        if row:
            plan_name, category, updationMoney, returnMoney, level = row
            # Convert category to string if it's not numeric
            if not category.isdigit():
                category = str(category)
            plans.append((plan_name, category, int(updationMoney), int(returnMoney), int(level)))

    plan_profits = []
    for plan in plans:
        plan_name, category, updationMoney, returnMoney, level = plan
        try:
            profit = calculate_profit(updationMoney, returnMoney)
            plan_profits.append((profit, plan))
        except ValueError as e:
            print(f"Error with plan {plan_name}: {e}")

    plan_profits.sort(key=lambda x: x[0])

    sorted_plans = []
    for profit, plan in plan_profits[:limit]:
        plan_name, category, updationMoney, returnMoney, level = plan
        formatted_profit = "{:.4f}".format(profit)
        sorted_plans.append({
            'plan_name': plan_name,
            'category_text': category,
            'updationMoney': updationMoney,
            'returnMoney': returnMoney,
            'level': level,
            'profit': formatted_profit
        })

    return sorted_plans

def monitor_csv_changes():
    while True:
        time.sleep(1)
        if csv_data.is_modified():
            csv_data.save_data(csv_data.read_data())
            processed_plans = process_and_sort_plans(csv_data.data, limit=15)
            socketio.emit('processed_data_updated', processed_plans, namespace='/')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_data', methods=['GET'])
def get_data():
    limit = 15
    plans = process_and_sort_plans(csv_data.data, limit)
    return jsonify({'raw_data': csv_data.data, 'processed_plans': plans})

@app.route('/save_data', methods=['POST'])
def save_data():
    data = request.json.get('data', [])
    csv_data.save_data(data)
    return jsonify({'message': 'File saved successfully', 'success': True})

@socketio.on('connect', namespace='/')
def test_connect():
    emit('my_response', {'data': 'Connected'})

@socketio.on('disconnect', namespace='/')
def test_disconnect():
    print('Client disconnected')

if __name__ == "__main__":
    t = threading.Thread(target=monitor_csv_changes)
    t.daemon = True
    t.start()
    socketio.run(app, debug=True)
