import hmac
import math
import os
import secrets
from functools import wraps
from pathlib import Path

import click
import pymysql
from flask import (
    Flask, abort, flash, g, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("MYALERT_SECRET_KEY"),
        MYSQL_HOST=os.getenv("MYSQL_HOST", "127.0.0.1"),
        MYSQL_PORT=int(os.getenv("MYSQL_PORT", "3306")),
        MYSQL_USER=os.getenv("MYSQL_USER", "myalert"),
        MYSQL_PASSWORD=os.getenv("MYSQL_PASSWORD", ""),
        MYSQL_DATABASE=os.getenv("MYSQL_DATABASE", "myalert"),
        SESSION_COOKIE_SECURE=os.getenv("MYALERT_HTTPS") == "1",
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    app.config.update(config or {})

    def db():
        if "db" not in g:
            g.db = pymysql.connect(
                host=app.config["MYSQL_HOST"], port=app.config["MYSQL_PORT"],
                user=app.config["MYSQL_USER"], password=app.config["MYSQL_PASSWORD"],
                database=app.config["MYSQL_DATABASE"], charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor, connect_timeout=5,
            )
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()

    def query(sql, args=(), *, one=False):
        with db().cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.fetchone() if one else cursor.fetchall()

    def write(sql, args=()):
        connection = db()
        with connection.cursor() as cursor:
            cursor.execute(sql, args)
        connection.commit()

    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def load_user():
        if not app.secret_key:
            abort(503, "Configura MYALERT_SECRET_KEY antes de iniciar MyAlert!.")
        if request.method == "POST":
            expected = session.get("csrf", "")
            supplied = request.form.get("csrf", "")
            if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
                abort(400, "Formulario inválido. Recarga la página e inténtalo de nuevo.")
        user_id = session.get("user_id")
        g.user = None
        if user_id is not None:
            g.user = query(
                "SELECT id, username, role FROM users WHERE id=%s AND active=1",
                (user_id,), one=True,
            )
            if g.user is None:
                session.clear()

    def protected(view=None, *, admin=False):
        def decorate(handler):
            @wraps(handler)
            def check(*args, **kwargs):
                if g.user is None:
                    return redirect(url_for("login"))
                if admin and g.user["role"] != "administrativo":
                    abort(403)
                return handler(*args, **kwargs)
            return check
        return decorate if view is None else decorate(view)

    @app.get("/")
    def index():
        reports = query(
            "SELECT r.*, u.username FROM reports r JOIN users u ON u.id=r.user_id "
            "ORDER BY r.created_at DESC, r.id DESC LIMIT 100"
        )
        pins = [
            {"title": row["title"], "place": row["place"],
             "lat": row["latitude"], "lon": row["longitude"]}
            for row in reports if row["latitude"] is not None
        ]
        return render_template("index.html", reports=reports, pins=pins)

    @app.route("/registro", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not valid_account(name, email, password):
                flash("Revisa el usuario, el correo y la contraseña.", "error")
            elif password != request.form.get("confirmation"):
                flash("Las contraseñas deben coincidir.", "error")
            else:
                try:
                    write(
                        "INSERT INTO users (username,email,password_hash) VALUES (%s,%s,%s)",
                        (name, email, generate_password_hash(password)),
                    )
                except pymysql.err.IntegrityError as error:
                    if error.args[0] != 1062:
                        raise
                    flash("El usuario o correo ya está registrado.", "error")
                else:
                    flash("Cuenta creada. Ya puedes iniciar sesión.", "success")
                    return redirect(url_for("login"))
        return render_template("account.html", registration=True)

    @app.route("/ingresar", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            user = query(
                "SELECT id, password_hash FROM users WHERE username=%s AND active=1",
                (request.form.get("username", "").strip(),), one=True,
            )
            if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
                session.clear()
                session["user_id"] = user["id"]
                return redirect(url_for("index"))
            flash("Usuario o contraseña incorrectos.", "error")
        return render_template("account.html", registration=False)

    @app.post("/salir")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    @app.route("/reportes/nuevo", methods=["GET", "POST"])
    @protected
    def new_report():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            place = request.form.get("place", "").strip()
            details = request.form.get("details", "").strip()
            try:
                lat, lon = coordinates(request.form.get("lat", ""), request.form.get("lon", ""))
                if not (1 <= len(title) <= 100 and 1 <= len(place) <= 150
                        and 1 <= len(details) <= 2000):
                    raise ValueError("Completa el título, el lugar y la descripción.")
            except ValueError as error:
                flash(str(error), "error")
            else:
                write(
                    "INSERT INTO reports (user_id,title,place,details,latitude,longitude) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (g.user["id"], title, place, details, lat, lon),
                )
                flash("Reporte publicado.", "success")
                return redirect(url_for("index"))
        return render_template("report.html")

    @app.get("/perfil")
    @protected
    def profile():
        reports = query(
            "SELECT * FROM reports WHERE user_id=%s ORDER BY created_at DESC, id DESC",
            (g.user["id"],),
        )
        return render_template("profile.html", reports=reports)

    @app.get("/administracion")
    @protected(admin=True)
    def admin():
        users = query("SELECT id,username,email,role,active FROM users ORDER BY username")
        total = query("SELECT COUNT(*) AS total FROM reports", one=True)["total"]
        return render_template("admin.html", users=users, total=total)

    @app.post("/administracion/usuarios/<int:user_id>")
    @protected(admin=True)
    def set_user_status(user_id):
        active = request.form.get("active")
        if active not in {"0", "1"}:
            abort(400)
        write("UPDATE users SET active=%s WHERE id=%s AND role='cliente'", (int(active), user_id))
        return redirect(url_for("admin"))

    @app.cli.command("init-db")
    def init_db():
        statements = (Path(app.root_path) / "schema.sql").read_text(encoding="utf-8")
        for statement in statements.split(";"):
            if statement.strip():
                write(statement)
        click.echo("Esquema de MyAlert! preparado.")

    @app.cli.command("create-admin")
    @click.option("--username", prompt="Usuario")
    @click.option("--email", prompt="Correo")
    @click.password_option(confirmation_prompt=True)
    def create_admin(username, email, password):
        username, email = username.strip(), email.strip().lower()
        if not valid_account(username, email, password):
            raise click.ClickException("Revisa el usuario, el correo y la contraseña.")
        try:
            write(
                "INSERT INTO users (username,email,password_hash,role) "
                "VALUES (%s,%s,%s,'administrativo')",
                (username, email, generate_password_hash(password)),
            )
        except pymysql.err.IntegrityError as error:
            if error.args[0] != 1062:
                raise
            raise click.ClickException("El usuario o correo ya existe.") from error
        click.echo("Cuenta administrativa creada.")

    return app


def valid_account(username, email, password):
    return (3 <= len(username) <= 40 and len(email) <= 254
            and email.count("@") == 1 and all(email.split("@"))
            and not any(character.isspace() for character in email)
            and 8 <= len(password) <= 128)


def coordinates(lat, lon):
    if not lat and not lon:
        return None, None
    try:
        latitude, longitude = float(lat), float(lon)
        if math.isfinite(latitude) and math.isfinite(longitude):
            if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                return latitude, longitude
    except ValueError:
        pass
    raise ValueError("Selecciona una ubicación válida en el mapa.")
