from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import secrets
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage


app = Flask(__name__)


app.secret_key = "notes_management_secret"



# ================= UPLOAD CONFIG =================

app.config["UPLOAD_FOLDER"] = "uploads"

app.config["PROFILE_FOLDER"] = "static/uploads/profile"



# Create Upload Folder

if not os.path.exists("uploads"):
    os.makedirs("uploads")



# Create Profile Image Folder

if not os.path.exists("static/uploads/profile"):
    os.makedirs("static/uploads/profile")



# Create Database Folder

if not os.path.exists("database"):
    os.makedirs("database")




# ================= DATABASE INITIALIZATION =================


def init_db():

    conn = sqlite3.connect("database/database.db")

    cursor = conn.cursor()



    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attachments(

        attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,

        note_id INTEGER,

        file_name TEXT,

        file_path TEXT,

        file_type TEXT,

        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY(note_id) REFERENCES notes(note_id)

    )
    """)


    conn.commit()

    conn.close()



init_db()






# ================= HOME =================


@app.route("/")
def home():

    return render_template("index.html")








# ================= REGISTER =================


@app.route("/register", methods=["GET","POST"])
def register():


    if request.method == "POST":


        username=request.form["username"]

        email=request.form["email"]

        password=request.form["password"]

        confirm_password=request.form["confirm_password"]



        if password != confirm_password:

            return "Passwords do not match!"



        password_hash=generate_password_hash(password)



        conn=sqlite3.connect("database/database.db")

        cursor=conn.cursor()



        cursor.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        )


        existing_user=cursor.fetchone()



        if existing_user:

            conn.close()

            return "Email already registered!"




        cursor.execute("""
        INSERT INTO users
        (username,email,password_hash)

        VALUES(?,?,?)

        """,
        (
            username,
            email,
            password_hash
        ))



        conn.commit()

        conn.close()



        return redirect(url_for("login"))



    return render_template("register.html")









# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database/database.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        )

        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user[3], password):

            session["user_id"] = user[0]
            session["username"] = user[1]

            return redirect(url_for("dashboard"))

        else:

            return render_template(
                "login.html",
                error="Invalid Email or Password"
            )

    return render_template("login.html")



# ================= FORGOT PASSWORD =================

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form.get("email", "").strip()

        if not email:
            flash("Please enter your email address.", "danger")
            return redirect(url_for("forgot_password"))

        conn = sqlite3.connect("database/database.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id
            FROM users
            WHERE email=?
        """, (email,))

        user = cursor.fetchone()

        if not user:
            conn.close()

            flash("No account found with this email.", "danger")
            return redirect(url_for("forgot_password"))

        # Generate secure reset token
        reset_token = secrets.token_urlsafe(32)

        # Token valid for 15 minutes
        expiry = datetime.now() + timedelta(minutes=15)

        cursor.execute("""
            UPDATE users
            SET reset_token=?,
                reset_token_expiry=?
            WHERE user_id=?
        """, (
            reset_token,
            expiry.isoformat(),
            user[0]
        ))

        conn.commit()
        conn.close()

        # Generate reset link
        reset_link = url_for(
            "reset_password",
            token=reset_token,
            _external=True
        )

        # ================= SEND EMAIL =================

        sender_email = os.environ.get("MAIL_USERNAME")
        sender_password = os.environ.get("MAIL_PASSWORD")

        if not sender_email or not sender_password:

            flash(
                "Email service is not configured. Please try again later.",
                "danger"
            )

            return redirect(url_for("forgot_password"))

        try:

            message = EmailMessage()

            message["Subject"] = "Notes Management System - Password Reset"
            message["From"] = sender_email
            message["To"] = email

            message.set_content(
                f"""Hello,

We received a request to reset your password for the Notes Management System.

Click the link below to reset your password:

{reset_link}

This link will expire in 15 minutes.

If you did not request a password reset, please ignore this email.

Regards,
Notes Management System
"""
            )

            with smtplib.SMTP("smtp.gmail.com", 587) as server:

                server.starttls()

                server.login(
                    sender_email,
                    sender_password
                )

                server.send_message(message)

            flash(
                "Password reset link has been sent to your email.",
                "success"
            )

        except Exception as e:

            print("EMAIL ERROR:", e)

            flash(
                "Unable to send reset email. Please try again later.",
                "danger"
            )

        return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")


# ================= RESET PASSWORD =================

@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):

    conn = sqlite3.connect("database/database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM users
        WHERE reset_token=?
    """, (token,))

    user = cursor.fetchone()

    if not user:
        conn.close()
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for("forgot_password"))

    # Check token expiry
    try:
        expiry = datetime.fromisoformat(user["reset_token_expiry"])

        if datetime.now() > expiry:
            conn.close()
            flash("Reset link has expired. Please request a new one.", "danger")
            return redirect(url_for("forgot_password"))

    except:
        conn.close()
        flash("Invalid reset link.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":

        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if not new_password or not confirm_password:
            conn.close()
            flash("All fields are required.", "danger")
            return redirect(url_for("reset_password", token=token))

        if new_password != confirm_password:
            conn.close()
            flash("Passwords do not match.", "danger")
            return redirect(url_for("reset_password", token=token))

        password_hash = generate_password_hash(new_password)

        cursor.execute("""
            UPDATE users
            SET password_hash=?,
                reset_token=NULL,
                reset_token_expiry=NULL
            WHERE user_id=?
        """, (
            password_hash,
            user["user_id"]
        ))

        conn.commit()
        conn.close()

        flash("Password reset successfully! Please login.", "success")

        return redirect(url_for("login"))

    conn.close()

    return render_template(
        "reset_password.html",
        token=token
    )








# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))


    search_query = request.args.get("search", "").strip()

    sort = request.args.get("sort", "newest")


    # ================= PAGINATION =================

    page = request.args.get("page", 1, type=int)

    per_page = 5

    offset = (page - 1) * per_page



    # ================= SORT SECURITY =================

    sort_options = {

        "newest": "created_at DESC",
        "oldest": "created_at ASC",
        "az": "title ASC",
        "za": "title DESC"

    }


    order_by = sort_options.get(sort, "created_at DESC")



    conn = sqlite3.connect("database/database.db")

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()



    # ================= SEARCH QUERY =================

    if search_query:


        query = f"""
            SELECT *
            FROM notes
            WHERE user_id=?
            AND (
                title LIKE ?
                OR content LIKE ?
                OR tags LIKE ?
            )
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """

        cursor.execute(

            query,

            (

                session["user_id"],

                f"%{search_query}%",

                f"%{search_query}%",

                f"%{search_query}%",

                per_page,

                offset

            )

        )



    # ================= NORMAL QUERY =================

    else:


        query = f"""
            SELECT *
            FROM notes
            WHERE user_id=?
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """


        cursor.execute(

            query,

            (

                session["user_id"],

                per_page,

                offset

            )

        )



    notes = cursor.fetchall()



    # ================= TOTAL NOTES COUNT =================

    cursor.execute("""
        SELECT COUNT(*)
        FROM notes
        WHERE user_id=?
    """,
    (
        session["user_id"],
    ))


    total_notes = cursor.fetchone()[0]


    total_pages = (total_notes + per_page - 1) // per_page





    # ================= FETCH CATEGORIES =================

    cursor.execute("""
        SELECT *
        FROM categories
        WHERE user_id=?
        ORDER BY category_name ASC
    """,
    (
        session["user_id"],
    ))


    categories = cursor.fetchall()



    conn.close()



    return render_template(

        "dashboard.html",

        username=session["username"],

        notes=notes,

        categories=categories,

        search=search_query,

        sort=sort,

        page=page,

        total_pages=total_pages

    )

# =========== CATEGORY MANAGEMENT ===============


# ================= ADD CATEGORY =================

@app.route("/add_category", methods=["GET", "POST"])
def add_category():

    if "user_id" not in session:
        return redirect(url_for("login"))


    if request.method == "POST":

        category_name = request.form["category_name"].strip()


        if category_name:

            conn = sqlite3.connect("database/database.db")
            cursor = conn.cursor()


            cursor.execute("""
                INSERT INTO categories(user_id, category_name)
                VALUES(?,?)
            """,
            (
                session["user_id"],
                category_name
            ))


            conn.commit()
            conn.close()


            flash("Category Added Successfully!", "success")


            return redirect(url_for("dashboard"))


    return render_template("add_category.html")





# ================= VIEW CATEGORY =================

@app.route("/category/<int:category_id>")
def category_page(category_id):


    if "user_id" not in session:
        return redirect(url_for("login"))



    conn = sqlite3.connect("database/database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()



    # Get Category Details

    cursor.execute("""
        SELECT *
        FROM categories
        WHERE category_id=? 
        AND user_id=?
    """,
    (
        category_id,
        session["user_id"]
    ))


    category = cursor.fetchone()



    # Get Notes Of Category

    cursor.execute("""
        SELECT *
        FROM notes
        WHERE category_id=?
        AND user_id=?
        ORDER BY created_at DESC
    """,
    (
        category_id,
        session["user_id"]
    ))


    notes = cursor.fetchall()



    conn.close()



    return render_template(
        "category_page.html",
        category=category,
        notes=notes
    )





# ================= EDIT CATEGORY =================


@app.route("/edit_category/<int:category_id>", methods=["GET","POST"])
def edit_category(category_id):


    if "user_id" not in session:
        return redirect(url_for("login"))



    conn = sqlite3.connect("database/database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()



    cursor.execute("""
        SELECT *
        FROM categories
        WHERE category_id=?
        AND user_id=?
    """,
    (
        category_id,
        session["user_id"]
    ))


    category = cursor.fetchone()



    if not category:

        conn.close()

        return "Category not found!"




    if request.method == "POST":


        category_name = request.form["category_name"].strip()



        cursor.execute("""
            UPDATE categories
            SET category_name=?
            WHERE category_id=?
            AND user_id=?
        """,
        (
            category_name,
            category_id,
            session["user_id"]
        ))



        conn.commit()
        conn.close()



        flash("Category Updated Successfully!", "success")

        return redirect(url_for("dashboard"))




    conn.close()



    return render_template(
        "edit_category.html",
        category=category
    )






# ================= DELETE CATEGORY =================


@app.route("/delete_category/<int:category_id>")
def delete_category(category_id):


    if "user_id" not in session:
        return redirect(url_for("login"))



    conn = sqlite3.connect("database/database.db")
    cursor = conn.cursor()



    # Remove Category From Notes

    cursor.execute("""
        UPDATE notes
        SET category_id=NULL
        WHERE category_id=?
        AND user_id=?
    """,
    (
        category_id,
        session["user_id"]
    ))



    # Delete Category

    cursor.execute("""
        DELETE FROM categories
        WHERE category_id=?
        AND user_id=?
    """,
    (
        category_id,
        session["user_id"]
    ))



    conn.commit()
    conn.close()



    flash("Category Deleted Successfully!", "success")


    return redirect(url_for("dashboard"))


# ================= CREATE NOTE =================

@app.route("/create_note", methods=["GET", "POST"])
def create_note():

    # Login check
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database/database.db")
    cursor = conn.cursor()

    # ================= POST =================

    if request.method == "POST":

        title = request.form.get("title")
        content = request.form.get("content")
        tags = request.form.get("tags")
        category_id = request.form.get("category_id")

        # Favorite checkbox
        favorite = request.form.get("favorite")

        if favorite:
            is_favorite = 1
        else:
            is_favorite = 0

        # File
        file = request.files.get("file")

        # ================= INSERT NOTE =================

        cursor.execute("""
            INSERT INTO notes
            (user_id, category_id, title, content, tags, is_favorite)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            category_id,
            title,
            content,
            tags,
            is_favorite
        ))

        note_id = cursor.lastrowid

        # ================= FILE UPLOAD =================

        if file and file.filename != "":

            filename = file.filename

            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            file.save(filepath)

            cursor.execute("""
                INSERT INTO attachments
                (note_id, file_name, file_path, file_type)
                VALUES (?, ?, ?, ?)
            """, (
                note_id,
                filename,
                filepath,
                file.content_type
            ))

        # Save database changes
        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    # ================= FETCH CATEGORIES =================

    cursor.execute("""
        SELECT category_id, category_name
        FROM categories
        WHERE user_id = ?
    """, (
        session["user_id"],
    ))

    categories = cursor.fetchall()

    conn.close()

    # ================= SHOW CREATE NOTE PAGE =================

    return render_template(
        "create_note.html",
        categories=categories
    )

# ================= FAVORITE TOGGLE =================

@app.route("/favorite/<int:note_id>", methods=["POST"])
def favorite_note(note_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database/database.db")
    cursor = conn.cursor()

    # Current Status
    cursor.execute("""
        SELECT is_favorite
        FROM notes
        WHERE note_id=? AND user_id=?
    """, (note_id, session["user_id"]))

    note = cursor.fetchone()

    if note:

        if note[0] == 0:

            # Make Favorite
            cursor.execute("""
                UPDATE notes
                SET is_favorite=1
                WHERE note_id=? AND user_id=?
            """, (note_id, session["user_id"]))

            cursor.execute("""
                INSERT INTO favorites(user_id,note_id)
                VALUES(?,?)
            """, (session["user_id"], note_id))

        else:

            # Remove Favorite
            cursor.execute("""
                UPDATE notes
                SET is_favorite=0
                WHERE note_id=? AND user_id=?
            """, (note_id, session["user_id"]))

            cursor.execute("""
                DELETE FROM favorites
                WHERE user_id=? AND note_id=?
            """, (session["user_id"], note_id))

    conn.commit()
    conn.close()

    return redirect(request.referrer or url_for("dashboard"))


# ================= view note =================


@app.route("/view_note/<int:note_id>")
def view_note(note_id):

    if "user_id" not in session:
        return redirect(url_for("login"))


    conn = sqlite3.connect("database/database.db")
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()


    cursor.execute("""
    SELECT *
    FROM notes
    WHERE note_id=? AND user_id=?
    """,
    (
        note_id,
        session["user_id"]
    ))


    note = cursor.fetchone()



    cursor.execute("""
    SELECT *
    FROM attachments
    WHERE note_id=?
    """,
    (note_id,))


    attachment = cursor.fetchone()



    conn.close()



    return render_template(
        "view_note.html",
        note=note,
        attachment=attachment
    )

# ================= EDIT NOTE =================

@app.route("/edit_note/<int:note_id>", methods=["GET", "POST"])
def edit_note(note_id):

    if "user_id" not in session:
        return redirect(url_for("login"))


    conn = sqlite3.connect("database/database.db")

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()



    # Fetch Note

    cursor.execute("""
        SELECT *
        FROM notes
        WHERE note_id=? AND user_id=?
    """,
    (
        note_id,
        session["user_id"]
    ))


    note = cursor.fetchone()



    if not note:

        conn.close()

        return "Note not found!"





    # Fetch Categories

    cursor.execute("""
        SELECT category_id, category_name
        FROM categories
        WHERE user_id=?
    """,
    (
        session["user_id"],
    ))


    categories = cursor.fetchall()





    if request.method == "POST":


        title = request.form["title"]

        category_id = request.form["category_id"]

        content = request.form["content"]

        tags = request.form["tags"]



        favorite = request.form.get("favorite")

        is_favorite = 1 if favorite else 0






        # Update Note

        cursor.execute("""
            UPDATE notes

            SET category_id=?,
                title=?,
                content=?,
                tags=?,
                is_favorite=?,
                updated_at=CURRENT_TIMESTAMP

            WHERE note_id=? AND user_id=?

        """,

        (
            category_id,
            title,
            content,
            tags,
            is_favorite,
            note_id,
            session["user_id"]
        ))





        # Favorite Table Update

        cursor.execute("""
            DELETE FROM favorites

            WHERE user_id=? AND note_id=?

        """,
        (
            session["user_id"],
            note_id
        ))





        if is_favorite == 1:


            cursor.execute("""
                INSERT INTO favorites
                (user_id,note_id)

                VALUES(?,?)

            """,

            (
                session["user_id"],
                note_id
            ))







        # ================= FILE UPDATE =================


        file = request.files.get("file")



        if file and file.filename != "":


            filename = file.filename


            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )



            file.save(filepath)





            cursor.execute("""
                DELETE FROM attachments

                WHERE note_id=?

            """,
            (
                note_id,
            ))





            cursor.execute("""
                INSERT INTO attachments

                (note_id,file_name,file_path,file_type)

                VALUES(?,?,?,?)

            """,

            (
                note_id,
                filename,
                filepath,
                file.content_type
            ))






        conn.commit()

        conn.close()



        return redirect(
            url_for(
                "view_note",
                note_id=note_id
            )
        )




    conn.close()



    return render_template(
        "edit_note.html",
        note=note,
        categories=categories
    )


# ================= DELETE NOTE =================

@app.route("/delete_note/<int:note_id>")
def delete_note(note_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database/database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Attachment माहिती मिळवा
    cursor.execute("""
        SELECT *
        FROM attachments
        WHERE note_id=?
    """, (note_id,))

    attachment = cursor.fetchone()

    # Actual file delete करा
    if attachment:

        filepath = attachment["file_path"]

        if os.path.exists(filepath):
            os.remove(filepath)

        cursor.execute("""
            DELETE FROM attachments
            WHERE note_id=?
        """, (note_id,))

    # Favorite table मधून delete
    cursor.execute("""
        DELETE FROM favorites
        WHERE note_id=? AND user_id=?
    """, (
        note_id,
        session["user_id"]
    ))

    # Note delete
    cursor.execute("""
        DELETE FROM notes
        WHERE note_id=? AND user_id=?
    """, (
        note_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))




# ================= ALL NOTES =================

@app.route("/notes")
def notes():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database/database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM notes
        WHERE user_id=?
        ORDER BY created_at DESC
    """, (session["user_id"],))

    notes = cursor.fetchall()

    conn.close()

    return render_template(
        "notes.html",
        notes=notes,
        username=session["username"]
    )




# ================= FAVORITE NOTES =================

@app.route("/favorites")
def favorites():

    if "user_id" not in session:
        return redirect(url_for("login"))

    search_query = request.args.get("search", "").strip()

    conn = sqlite3.connect("database/database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if search_query:

        cursor.execute("""
            SELECT notes.*
            FROM notes
            INNER JOIN favorites
            ON notes.note_id = favorites.note_id
            WHERE favorites.user_id=?
            AND (
                notes.title LIKE ?
                OR notes.content LIKE ?
                OR notes.tags LIKE ?
            )
            ORDER BY notes.created_at DESC
        """, (
            session["user_id"],
            f"%{search_query}%",
            f"%{search_query}%",
            f"%{search_query}%"
        ))

    else:

        cursor.execute("""
            SELECT notes.*
            FROM notes
            INNER JOIN favorites
            ON notes.note_id = favorites.note_id
            WHERE favorites.user_id=?
            ORDER BY notes.created_at DESC
        """, (session["user_id"],))

    notes = cursor.fetchall()

    conn.close()

    return render_template(
        "favorites.html",
        notes=notes,
        username=session["username"],
        search_query=search_query
    )



# ================= CHANGE PASSWORD =================

@app.route("/change_password", methods=["GET", "POST"])
def change_password():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # Check all fields
        if not current_password or not new_password or not confirm_password:
            flash("All fields are required!", "danger")
            return redirect(url_for("change_password"))

        # New password confirmation
        if new_password != confirm_password:
            flash("New passwords do not match!", "danger")
            return redirect(url_for("change_password"))

        # Get current user
        conn = sqlite3.connect("database/database.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT password_hash
            FROM users
            WHERE user_id=?
        """, (session["user_id"],))

        user = cursor.fetchone()

        if not user:
            conn.close()
            flash("User not found!", "danger")
            return redirect(url_for("profile"))

        # Check old password
        if not check_password_hash(user[0], current_password):
            conn.close()
            flash("Current password is incorrect!", "danger")
            return redirect(url_for("change_password"))

        # New password hash
        new_password_hash = generate_password_hash(new_password)

        cursor.execute("""
            UPDATE users
            SET password_hash=?
            WHERE user_id=?
        """, (
            new_password_hash,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        flash("Password changed successfully!", "success")

        return redirect(url_for("profile"))

    return render_template("change_password.html")


# ================= PROFILE =================

@app.route("/profile", methods=["GET", "POST"])
def profile():

    if "user_id" not in session:
        return redirect(url_for("login"))


    conn = sqlite3.connect("database/database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()



    # ================= PROFILE UPDATE =================

    if request.method == "POST":


        username = request.form["username"]
        email = request.form["email"]


        profile_image = None



        # ================= IMAGE UPLOAD =================

        if "profile_image" in request.files:


            file = request.files["profile_image"]


            if file.filename != "":


                from werkzeug.utils import secure_filename
                import time


                filename = (
                    str(int(time.time()))
                    + "_"
                    + secure_filename(file.filename)
                )


                file_path = os.path.join(
                    app.config["PROFILE_FOLDER"],
                    filename
                )


                file.save(file_path)


                profile_image = filename





        # ================= DATABASE UPDATE =================


        if profile_image:


            cursor.execute(
                """
                UPDATE users
                SET username=?,
                    email=?,
                    profile_image=?
                WHERE user_id=?
                """,
                (
                    username,
                    email,
                    profile_image,
                    session["user_id"]
                )
            )


        else:


            cursor.execute(
                """
                UPDATE users
                SET username=?,
                    email=?
                WHERE user_id=?
                """,
                (
                    username,
                    email,
                    session["user_id"]
                )
            )



        conn.commit()


        session["username"] = username





    # ================= FETCH PROFILE DATA =================


    cursor.execute(
        """
        SELECT *
        FROM users
        WHERE user_id=?
        """,
        (session["user_id"],)
    )


    user = cursor.fetchone()



    conn.close()



    return render_template(
        "profile.html",
        user=user
    )


# ================= SERVE UPLOADED FILES =================

@app.route("/uploads/<filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# ================= ERROR HANDLERS =================


@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "error.html",
        error_code=404,
        error_message="Page Not Found!"
    ), 404



@app.errorhandler(500)
def internal_server_error(error):

    return render_template(
        "error.html",
        error_code=500,
        error_message="Internal Server Error!"
    ), 500



# ================= LOGOUT =================


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))







# ================= RUN =================


if __name__=="__main__":

    app.run(debug=True)