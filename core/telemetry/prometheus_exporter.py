from core.telemetry.metrics import MetricsCollector
from flask import Flask, Response
import time

app = Flask(__name__)

@app.route('/metrics')
def metrics():
    output = []
    for key, values in MetricsCollector._metrics.items():
        metric_name = key.split("{'", 1)[0]
        for ts, value in values:
            output.append(f"{metric_name} {value} {int(ts)}")
    return Response('\n'.join(output), mimetype='text/plain')

if __name__ == '__main__':
    app.run(port=8000)

