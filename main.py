from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
import smtplib


'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap5(app)

EMAIL = "chisomomalembeka@gmail.com"
PASSWORD = "pujd yebf dkws ygxn"

# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# TODO: Configure gravatar
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), nullable=False, unique=True)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    # allows us to crate a one-to-many relationship with User being the parent to BlogPost
    user_posts = db.relationship("BlogPost", back_populates="author_user")
    user_comments = db.relationship("Comments", back_populates="author_comment")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    author_user = db.relationship("User", back_populates="user_posts")

    blog_comment = db.relationship("Comments", back_populates="user_comment")


class Comments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    comment = db.Column(db.String(1000), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    author_comment = db.relationship("User", back_populates="user_comments")

    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    user_comment = db.relationship("BlogPost", back_populates="blog_comment")


# TODO: Create a User table for all your registered users.
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


# TODO: Create admin_only decorator function
def admin_only(func):
    @wraps(func)
    def wrapper_func(*args, **kwargs):
        if current_user.id != 1:
            abort(403)
        return func(*args, **kwargs)
    return wrapper_func


with app.app_context():
    db.create_all()


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=["POST", "GET"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        for email in db.session.query(User, User.email).all():
            if email[1] == form.email.data:
                flash("You've already signed up with that email, Login instead")
                return redirect(url_for("login"))
        hashed_salted_password = generate_password_hash(form.password.data, 'pbkdf2', salt_length=8)
        new_user = User(
            email=form.email.data,
            password=hashed_salted_password,
            name=form.name.data
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=form, current_user=current_user)


# TODO: Retrieve a user from the database based on their email.
@app.route('/login', methods=["POST", "GET"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if not user:
            flash("That email doesnt exist, please try again")
            return redirect(url_for("login"))
        elif not check_password_hash(user.password, password):
            flash("That password is incorrect, please try again")
            return redirect(url_for("login"))
        else:
            login_user(user)
            return redirect(url_for("get_all_posts"))

    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, current_user=current_user)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    comments = db.session.execute(db.select(Comments)).scalars().all()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Please Log in to do that.")
            return redirect(url_for("login"))

        new_comment = Comments(
            comment=form.comment.data,
            author_id=current_user.id,
            post_id=post_id
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("post.html", form=form, post=requested_post, comments=comments, current_user=current_user)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_user=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


@app.route("/contact", methods=["POST", "GET"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone_no = request.form["phone"]
        message = request.form["message"]
        print(f"{name}\n{email}\n{phone_no}\n{message}")

        with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
            connection.starttls()
            connection.login(user=EMAIL, password=PASSWORD)
            connection.sendmail(to_addrs=EMAIL, from_addr=EMAIL, msg=f"Subject:New Blog Follower!\n\nName: {name} \nEmail: {email} \nPhone: {phone_no} \nMessage: {message}")

        return redirect(url_for("get_all_posts"))

    return render_template("contact.html", current_user=current_user)


if __name__ == "__main__":
    app.run(debug=True, port=5004)
