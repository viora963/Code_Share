import os
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for, session,
    flash, abort, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from config import Config
from db import fetchone, fetchall, execute
from utils import login_required, sha256_file, ensure_dir


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    ensure_dir(app.config["UPLOAD_FOLDER"])

    def allowed_file(name: str) -> bool:
        if "." not in name:
            return False
        ext = name.rsplit(".", 1)[1].lower()
        return ext in app.config["ALLOWED_EXTENSIONS"]

    def me():
        if "user_id" not in session:
            return None
        return fetchone(
            "SELECT id, username, email, created_at, bio FROM users WHERE id=%s",
            (session["user_id"],)
        )

    def is_member(project_id: int, user_id: int) -> bool:
        return fetchone(
            "SELECT 1 FROM project_members WHERE project_id=%s AND user_id=%s",
            (project_id, user_id)
        ) is not None

    def role_of(project_id: int, user_id: int):
        r = fetchone(
            "SELECT role FROM project_members WHERE project_id=%s AND user_id=%s",
            (project_id, user_id)
        )
        return r["role"] if r else None

    def log_activity(project_id: int, user_id, action, entity_type, entity_id=None):
        execute(
            """
            INSERT INTO project_activity(project_id, user_id, action, entity_type, entity_id)
            VALUES (%s,%s,%s,%s,%s)
            """,
            (project_id, user_id, action, entity_type, entity_id)
        )

    # ---------- Errors ----------
    @app.errorhandler(403)
    def e403(_):
        return render_template("403.html"), 403

    @app.errorhandler(500)
    def e500(_):
        return render_template("500.html"), 500

    # ---------- Auth ----------
    @app.get("/")
    def index():
        return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

    @app.get("/signup")
    def signup():
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return render_template("auth/signup.html")

    @app.post("/signup")
    def signup_post():
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if password != confirm:
            flash("Les mots de passe ne correspondent pas.", "danger")
            return redirect(url_for("signup"))

        try:
            uid = execute(
                "INSERT INTO users(username, email, password_hash) VALUES (%s,%s,%s)",
                (username, email, generate_password_hash(password))
            )
        except Exception:
            flash("Nom d'utilisateur ou email déjà utilisé.", "danger")
            return redirect(url_for("signup"))

        session["user_id"] = uid
        flash("Compte créé.", "success")
        return redirect(url_for("dashboard"))

    @app.get("/login")
    def login():
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return render_template("auth/login.html")

    @app.post("/login")
    def login_post():
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        u = fetchone(
            "SELECT id, username, password_hash FROM users WHERE username_norm=LOWER(TRIM(%s))",
            (username,)
        )
        if not u or not check_password_hash(u["password_hash"], password):
            flash("Identifiants incorrects.", "danger")
            return redirect(url_for("login"))

        session["user_id"] = u["id"]
        flash("Connexion réussie.", "success")
        return redirect(url_for("dashboard"))

    @app.get("/logout")
    def logout():
        session.clear()
        flash("Déconnexion.", "info")
        return redirect(url_for("login"))

    # ---------- Dashboard ----------
    @app.get("/dashboard")
    @login_required
    def dashboard():
        u = me()

        stats_projects = fetchone("SELECT COUNT(*) c FROM projects WHERE owner_id=%s", (u["id"],))["c"]
        stats_stars = fetchone(
            """
            SELECT COUNT(*) c
            FROM stars s
            JOIN projects p ON p.id=s.project_id
            WHERE p.owner_id=%s
            """,
            (u["id"],)
        )["c"]
        stats_followers = fetchone(
            "SELECT COUNT(*) c FROM followers WHERE following_id=%s",
            (u["id"],)
        )["c"]

        # My projects (owner)
        my_projects = fetchall(
            """
            SELECT
              p.id, p.title, p.status, p.created_at,
              (SELECT COUNT(*) FROM stars s WHERE s.project_id=p.id) AS stars,
              (SELECT COUNT(*) FROM project_members pm WHERE pm.project_id=p.id) AS members
            FROM projects p
            WHERE p.owner_id=%s
            ORDER BY p.created_at DESC
            """,
            (u["id"],)
        )

        # Popular public projects (by stars)
        popular = fetchall(
            """
            SELECT
              p.id, p.title,
              (SELECT COUNT(*) FROM stars s WHERE s.project_id=p.id) AS stars,
              (SELECT COUNT(*) FROM project_members pm WHERE pm.project_id=p.id) AS members
            FROM projects p
            WHERE p.is_private=FALSE AND p.status='active'
            ORDER BY stars DESC, p.created_at DESC
            LIMIT 6
            """
        )

        # Recent activities (projects you can see: public OR member)
        activities = fetchall(
            """
            SELECT
              pa.created_at, pa.action,
              COALESCE(uu.username,'System') AS actor,
              p.id AS project_id, p.title AS project_title
            FROM project_activity pa
            JOIN projects p ON p.id=pa.project_id
            LEFT JOIN users uu ON uu.id=pa.user_id
            WHERE p.is_private=FALSE
               OR EXISTS (
                    SELECT 1 FROM project_members pm
                    WHERE pm.project_id=p.id AND pm.user_id=%s
               )
            ORDER BY pa.created_at DESC
            LIMIT 10
            """,
            (u["id"],)
        )

        # Latest comments (visible scope)
        latest_comments = fetchall(
            """
            SELECT
              c.created_at, c.message,
              uu.username AS author,
              p.id AS project_id, p.title AS project_title
            FROM comments c
            JOIN projects p ON p.id=c.project_id
            JOIN users uu ON uu.id=c.user_id
            WHERE p.is_private=FALSE
               OR EXISTS (
                    SELECT 1 FROM project_members pm
                    WHERE pm.project_id=p.id AND pm.user_id=%s
               )
            ORDER BY c.created_at DESC
            LIMIT 6
            """,
            (u["id"],)
        )

        return render_template(
            "dashboard.html",
            user=u,
            stats_projects=stats_projects,
            stats_stars=stats_stars,
            stats_followers=stats_followers,
            my_projects=my_projects,
            popular_projects=popular,
            activities=activities,
            latest_comments=latest_comments
        )

    @app.post("/dashboard/projects/create")
    @login_required
    def create_project():
        u = me()
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip() or None
        is_private = True if request.form.get("is_private") == "1" else False

        if len(title) < 3:
            flash("Titre trop court.", "danger")
            return redirect(url_for("dashboard"))

        pid = execute(
            "INSERT INTO projects(owner_id,title,description,is_private) VALUES(%s,%s,%s,%s)",
            (u["id"], title, description, is_private)
        )
        execute(
            "INSERT INTO project_members(project_id,user_id,role) VALUES(%s,%s,'owner')",
            (pid, u["id"])
        )
        log_activity(pid, u["id"], "created_project", "project", pid)
        flash("Projet créé.", "success")
        return redirect(url_for("project", pid=pid))

    # ---------- Profile ----------
    @app.get("/profile")
    @login_required
    def profile():
        u = me()

        project_count = fetchone("SELECT COUNT(*) c FROM projects WHERE owner_id=%s", (u["id"],))["c"]
        comment_count = fetchone("SELECT COUNT(*) c FROM comments WHERE user_id=%s", (u["id"],))["c"]
        like_count = fetchone("SELECT COUNT(*) c FROM stars WHERE user_id=%s", (u["id"],))["c"]

        return render_template(
            "profile.html",
            user=u,
            project_count=project_count,
            comment_count=comment_count,
            like_count=like_count
        )

    # ---------- Project page ----------
    @app.get("/project/<int:pid>")
    @login_required
    def project(pid: int):
        u = me()

        p = fetchone(
            """
            SELECT p.*, ou.username AS owner_username
            FROM projects p
            JOIN users ou ON ou.id=p.owner_id
            WHERE p.id=%s
            """,
            (pid,)
        )
        if not p:
            abort(404)

        if p["is_private"] and not is_member(pid, u["id"]):
            abort(403)

        role = role_of(pid, u["id"])
        is_owner = role == "owner"

        members = fetchall(
            """
            SELECT pm.user_id, uu.username, pm.role
            FROM project_members pm
            JOIN users uu ON uu.id=pm.user_id
            WHERE pm.project_id=%s
            ORDER BY FIELD(pm.role,'owner','admin','member'), uu.username
            """,
            (pid,)
        )

        files = fetchall(
            """
            SELECT f.id, f.filename, f.uploaded_at, uu.username AS uploader
            FROM files f
            JOIN users uu ON uu.id=f.uploaded_by
            WHERE f.project_id=%s
            ORDER BY f.uploaded_at DESC
            """,
            (pid,)
        )

        comments = fetchall(
            """
            SELECT c.id, c.message, c.created_at, uu.username AS author
            FROM comments c
            JOIN users uu ON uu.id=c.user_id
            WHERE c.project_id=%s
            ORDER BY c.created_at DESC
            """,
            (pid,)
        )

        like_count = fetchone("SELECT COUNT(*) c FROM stars WHERE project_id=%s", (pid,))["c"]
        user_liked = fetchone("SELECT 1 FROM stars WHERE user_id=%s AND project_id=%s", (u["id"], pid)) is not None

        return render_template(
            "project.html",
            user=u,
            project=p,
            members=members,
            files=files,
            comments=comments,
            is_owner=is_owner,
            like_count=like_count,
            user_liked=user_liked
        )

    @app.post("/project/<int:pid>/comment")
    @login_required
    def add_comment(pid: int):
        u = me()
        p = fetchone("SELECT id, is_private FROM projects WHERE id=%s", (pid,))
        if not p:
            abort(404)
        if p["is_private"] and not is_member(pid, u["id"]):
            abort(403)

        msg = (request.form.get("comment") or "").strip()
        if not msg:
            flash("Commentaire vide.", "warning")
            return redirect(url_for("project", pid=pid))

        cid = execute(
            "INSERT INTO comments(project_id,user_id,message) VALUES(%s,%s,%s)",
            (pid, u["id"], msg)
        )
        log_activity(pid, u["id"], "commented", "comment", cid)
        flash("Commentaire ajouté.", "success")
        return redirect(url_for("project", pid=pid))

    @app.post("/project/<int:pid>/upload")
    @login_required
    def upload_file(pid: int):
        u = me()
        p = fetchone("SELECT id, is_private FROM projects WHERE id=%s", (pid,))
        if not p:
            abort(404)
        if p["is_private"] and not is_member(pid, u["id"]):
            abort(403)

        f = request.files.get("file")
        if not f or f.filename == "":
            flash("Aucun fichier.", "warning")
            return redirect(url_for("project", pid=pid))

        if not allowed_file(f.filename):
            flash("Format non autorisé.", "danger")
            return redirect(url_for("project", pid=pid))

        safe = secure_filename(f.filename)
        stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        stored = f"{pid}_{u['id']}_{stamp}_{safe}"
        path = os.path.join(app.config["UPLOAD_FOLDER"], stored)
        f.save(path)

        size = os.path.getsize(path)
        digest = sha256_file(path)

        fid = execute(
            """
            INSERT INTO files(project_id,uploaded_by,filename,filepath,filesize,sha256)
            VALUES(%s,%s,%s,%s,%s,%s)
            """,
            (pid, u["id"], safe, stored, size, digest)
        )
        log_activity(pid, u["id"], "uploaded_file", "file", fid)
        flash("Fichier uploadé.", "success")
        return redirect(url_for("project", pid=pid))

    @app.get("/files/<int:file_id>/download")
    @login_required
    def download_file(file_id: int):
        u = me()
        f = fetchone("SELECT id, project_id, filename, filepath FROM files WHERE id=%s", (file_id,))
        if not f:
            abort(404)

        p = fetchone("SELECT is_private FROM projects WHERE id=%s", (f["project_id"],))
        if p and p["is_private"] and not is_member(f["project_id"], u["id"]):
            abort(403)

        return send_from_directory(
            app.config["UPLOAD_FOLDER"],
            f["filepath"],
            as_attachment=True,
            download_name=f["filename"]
        )

    @app.post("/files/<int:file_id>/delete")
    @login_required
    def delete_file(file_id: int):
        u = me()
        row = fetchone(
            """
            SELECT f.id, f.filepath, f.project_id, p.owner_id
            FROM files f
            JOIN projects p ON p.id=f.project_id
            WHERE f.id=%s
            """,
            (file_id,)
        )
        if not row:
            abort(404)
        if row["owner_id"] != u["id"]:
            abort(403)

        execute("DELETE FROM files WHERE id=%s", (file_id,))
        try:
            os.remove(os.path.join(app.config["UPLOAD_FOLDER"], row["filepath"]))
        except OSError:
            pass

        flash("Fichier supprimé.", "success")
        return redirect(url_for("project", pid=row["project_id"]))

    # ---------- Members ----------
    @app.post("/project/<int:pid>/members/add")
    @login_required
    def add_member(pid: int):
        u = me()
        if role_of(pid, u["id"]) != "owner":
            abort(403)

        username = (request.form.get("username") or "").strip()
        role = request.form.get("role") or "member"
        if role not in ("admin", "member"):
            role = "member"

        target = fetchone("SELECT id FROM users WHERE username_norm=LOWER(TRIM(%s))", (username,))
        if not target:
            flash("Utilisateur introuvable.", "danger")
            return redirect(url_for("project", pid=pid))

        try:
            execute(
                "INSERT INTO project_members(project_id,user_id,role) VALUES(%s,%s,%s)",
                (pid, target["id"], role)
            )
        except Exception:
            flash("Déjà membre.", "warning")
            return redirect(url_for("project", pid=pid))

        log_activity(pid, u["id"], "joined_project", "member", target["id"])
        flash("Membre ajouté.", "success")
        return redirect(url_for("project", pid=pid))

    @app.post("/project/<int:pid>/members/<int:member_id>/remove")
    @login_required
    def remove_member(pid: int, member_id: int):
        u = me()
        if role_of(pid, u["id"]) != "owner":
            abort(403)

        t = fetchone(
            "SELECT role FROM project_members WHERE project_id=%s AND user_id=%s",
            (pid, member_id)
        )
        if not t or t["role"] == "owner":
            abort(403)

        execute("DELETE FROM project_members WHERE project_id=%s AND user_id=%s", (pid, member_id))
        log_activity(pid, u["id"], "left_project", "member", member_id)
        flash("Membre retiré.", "success")
        return redirect(url_for("project", pid=pid))

    # ---------- Stars ----------
    @app.post("/project/<int:pid>/star")
    @login_required
    def star(pid: int):
        u = me()
        p = fetchone("SELECT id, is_private FROM projects WHERE id=%s", (pid,))
        if not p:
            abort(404)
        if p["is_private"] and not is_member(pid, u["id"]):
            abort(403)

        exists = fetchone("SELECT 1 FROM stars WHERE user_id=%s AND project_id=%s", (u["id"], pid))
        if exists:
            execute("DELETE FROM stars WHERE user_id=%s AND project_id=%s", (u["id"], pid))
            flash("Star retirée.", "info")
        else:
            execute("INSERT INTO stars(user_id, project_id) VALUES(%s,%s)", (u["id"], pid))
            log_activity(pid, u["id"], "starred", "star", None)
            flash("Star ajoutée.", "success")

        return redirect(url_for("project", pid=pid))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
