
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

users = {}
contact_messages = []


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request, name="home.html", context={}
    )


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="signup.html", context={}
    )


@app.post("/signup")
async def signup(
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    email = email.strip().lower()

    if email in users:
        return HTMLResponse("Email already registered", status_code=400)

    if password != confirm_password:
        return HTMLResponse("Passwords do not match", status_code=400)

    # Intentional QA bug: weak passwords are accepted.
    users[email] = {
        "password": password,
        "name": email.split("@")[0]
    }

    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="login.html", context={}
    )


@app.post("/login")
async def login(
    email: str = Form(...),
    password: str = Form(...)
):
    email = email.strip().lower()
    user = users.get(email)

    if not user or user["password"] != password:
        return HTMLResponse(
            "Invalid email or password", status_code=401
        )

    return RedirectResponse(
        f"/dashboard?email={email}", status_code=303
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, email: str):
    email = email.strip().lower()
    user = users.get(email)

    if not user:
        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": user, "email": email}
    )


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="reset_password.html", context={}
    )


@app.post("/reset-password")
async def reset_password(email: str = Form(...)):
    email = email.strip().lower()

    if email not in users:
        return HTMLResponse("Email not found", status_code=404)

    # Intentional QA bug: password is not actually reset.
    return HTMLResponse(
        "If the account exists, reset instructions will be sent."
    )


@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="contact.html", context={}
    )


@app.post("/contact", response_class=HTMLResponse)
async def contact(
    name: str = Form(""),
    email: str = Form(""),
    message: str = Form("")
):
    name = name.strip()
    email = email.strip().lower()
    message = message.strip()

    if not email or email not in users:
        return HTMLResponse(
            "Please use an email address registered with us.",
            status_code=400
        )

    # Intentional QA bug: empty names and messages are accepted.
    contact_messages.append({
        "name": name,
        "email": email,
        "message": message
    })

    return HTMLResponse("Thank you for contacting us!")


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, email: str):
    email = email.strip().lower()
    user = users.get(email)

    if not user:
        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={"user": user, "email": email}
    )


@app.post("/reset")
async def reset_app():
    users.clear()
    contact_messages.clear()
    return {"message": "Sample app data cleared"}
