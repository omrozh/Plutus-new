from captcha.image import ImageCaptcha
import flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, login_user, UserMixin, current_user
from sqlalchemy import desc
from uuid import uuid4
from flask_mail import Message, Mail
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
import os
from flask_sse import sse
from flask_socketio import SocketIO, emit

# TO DO: Implement missing templates search by .html
# We will need Redis on live server otherwise sse won't work.

# TO DO: Implement live chat with socket

app = flask.Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///site.db"
app.config["SECRET_KEY"] = "letsgoooobitchpenguinz0"

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_USERNAME"] = "omer.ozhan@modularsoftware.net"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USE_SSL"] = True
app.config["MAIL_PASSWORD"] = "nbvkkpvjozqcsfwz"

app.config["REDIS_URL"] = "redis://localhost"
app.register_blueprint(sse, url_prefix='/stream')

db = SQLAlchemy(app)

mail = Mail(app)

login_manager = LoginManager(app)
image = ImageCaptcha()

scheduler = BackgroundScheduler(app=app)
migrate = Migrate(app, db)
socket = SocketIO(app)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True)
    username = db.Column(db.String)
    password = db.Column(db.String)
    date_of_birth = db.Column(db.Date)
    status = db.Column(db.String)
    lives_remaining = db.Column(db.Integer)
    did_verify_email = db.Column(db.Boolean, default=False)
    public_code = db.Column(db.String, unique=True)
    referrer_fk = db.Column(db.String)

    def send_verification_email(self):
        msg = Message("Plutus Onay Kodu",
                      sender="omer.ozhan@modularsoftware.net",
                      recipients=[self.email])

        with open("emails/verification.html", "r") as f:
            msg.html = f.read().replace("%verification%", self.public_code)

        mail.send(msg)

    def send_lives_gained_mail(self):
        user_instance_of_referrer = User.query.filter_by(public_code=self.referrer_fk)

        msg = Message("Plutus'e Hoşgeldin!",
                      sender="omer.ozhan@modularsoftware.net",
                      recipients=[self.email])

        with open("emails/welcome.html", "r") as f:
            msg.html = f.read().replace("%lives%", self.lives_remaining)

        mail.send(msg)

        msg = Message("Plutus'e Arkadaşlarını Davet Ettiğin için Teşekkürler!",
                      sender="omer.ozhan@modularsoftware.net",
                      recipients=[user_instance_of_referrer.email])

        with open("emails/thanks.html", "r") as f:
            msg.html = f.read().replace("%lives%", user_instance_of_referrer.lives_remaining)

        mail.send(msg)

    # TO DO write the templates for emails. Use %lives% and %verification% for placeholders.


class CurrentCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    current_code = db.Column(db.String)
    is_updated = db.Column(db.Boolean, default=False)


class CodeAd(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code_fk = db.Column(db.Integer)
    ad_index = db.Column(db.Integer)


class SuccessfulCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_fk = db.Column(db.Integer)
    current_code_fk = db.Column(db.Integer)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route("/", methods=["POST", "GET"])
def index():
    return flask.render_template("index.html")


@app.route("/signup", methods=["POST", "GET"])
def signup():
    if flask.request.method == "POST":
        values = flask.request.values

        new_user = User(username=values["username"], email=values["email"], password=values["password"],
                        status="Continue", lives_remaining=1, referrer_fk=flask.request.args.get("referrer", None),
                        public_code=str(uuid4()))
        db.session.add(new_user)
        db.session.commit()

        new_user.send_verification_email()

        return flask.render_template("please_verify_your_email.html")

    return flask.render_template("signup.html")


@app.route("/verify-email")
def verify_email():
    user_by_code = User.query.filter_by(public_code=flask.request.args.get("email_verification_code")).first()
    if user_by_code.did_verify_email:
        return flask.redirect("/")

    user_by_code.did_verify_email = True
    if user_by_code.referrer_fk:
        User.query.filter_by(public_code=user_by_code.referrer_fk).first().lives_remaining += 1
    user_by_code.lives_remaining += 1

    db.session.commit()
    user_by_code.send_lives_gained_mail()
    return flask.render_template("email_verification.html")


@app.route("/login", methods=["POST", "GET"])
def login():
    if flask.request.method == "POST":
        get_user = User.query.filter_by(email=flask.request.values["email"]).first()
        if get_user:
            if get_user.did_verify_email:
                if get_user.password == flask.request.values["password"]:
                    login_user(get_user, remember=True)
                    return flask.redirect("/")
            else:
                get_user.send_verification_email()
                return flask.render_template("please_verify_your_email.html")
    return flask.render_template("login.html")


@app.route("/generate_code", methods=["POST", "GET"])
@login_required
def generate_code():
    if flask.request.method == "POST":
        values = flask.request.values
        latest_code = CurrentCode.query.order_by(desc(CurrentCode.id)).limit(1).first()
        if values.get("current_code") == latest_code.current_code:
            return flask.jsonify({
                "status": "Retry"
            })
        else:
            return flask.jsonify({
                "status": "New Code",
                "is_winner": current_user.status == "Succeed",
                "is_failed": current_user.lives_remaining <= 0,
                "is_ok": current_user.status == "Continue",
                "lives_remaining": current_user.lives_remaining,
                "number_of_remaining_participants": User.query.count() - User.query.filter_by(lives_remaining=0).count()
            })


@app.route("/post_code", methods=["POST"])
@login_required
def post_code():
    if flask.request.method == "POST":
        latest_code = CurrentCode.query.order_by(desc(CurrentCode.id)).limit(1).first()
        if latest_code.current_code == flask.request.values["c-code"]:
            new_successful_code = SuccessfulCode(user_fk=current_user.id, current_code_fk=latest_code.id)
            db.session.add(new_successful_code)
            db.session.commit()
            return flask.jsonify({
                "status": "Success",
                "lives_remaining": current_user.lives_remaining
            })

        else:
            current_user.lives_remaining -= 1
            db.session.commit()
            return flask.jsonify({
                "status": "Fail",
                "lives_remaining": current_user.lives_remaining
            })


@app.route("/gameplay")
def gameplay():
    if current_user.lives_remaining <= 0:
        return flask.redirect("/failed")
    return flask.render_template("gameplay.html", lives=current_user.lives_remaining, username=current_user.username)


@app.route("/<filename>")
def return_image(filename):
    return flask.send_file(filename)


@app.route("/ads")
def ads():
    latest_code = CurrentCode.query.order_by(desc(CurrentCode.id)).limit(1).first()
    code_ad = CodeAd.query.filter_by(code_fk=latest_code.id).first()
    return flask.send_file("ads/" + os.listdir("ads")[code_ad.ad_index])


@socket.on("text")
def text(message):
    print(message)
    emit("chat", message, broadcast=True)
