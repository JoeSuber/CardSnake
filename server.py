from flask import Flask



app = Flask(__name__)

@app.route("/")
@app.route("/hello")
def hello_world():
    # parse the dct out of url
    # look 
    return "Hello, World!"

if __name__ == "__main__":
   app.run()