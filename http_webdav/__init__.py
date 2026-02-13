from flask import Flask

from http_webdav.api import bp

app = Flask(__name__)
app.register_blueprint(bp)
