from flask import Flask
from api.routes.predict import predict_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(predict_bp)
    return app
