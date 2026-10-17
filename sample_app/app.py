
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Code Apex Sample App")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)

# Temporary storage for our demonstration.
# We will add a reset endpoint for repeatable testing.
users = {}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={}
    )


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="signup.html",
        context={}
    )


@app.post("/signup")
async def signup(
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    if email in users:
        return HTMLResponse("Email already registered", status_code=400)

    if password != confirm_password:
        return HTMLResponse("Passwords do not match", status_code=400)

    users[email] = {
        "password": password,
        "name": email.split("@")[0]
    }

    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )


@app.post("/login")
async def login(
    email: str = Form(...),
    password: str = Form(...)
):
    user = users.get(email)

    if not user or user["password"] != password:
        return HTMLResponse("Invalid email or password", status_code=401)

    # Temporary demo login. Session handling can be added later.
    return RedirectResponse(
        f"/dashboard?email={email}",
        status_code=303
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, email: str):
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
        request=request,
        name="reset_password.html",
        context={}
    )


@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="contact.html",
        context={}
    )


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, email: str):
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
    return {"message": "Sample app data cleared"}


@app.post("/reset-password")
async def reset_password(email: str = Form(...)):
    # Demo only: no real email is sent.
    if email not in users:
        return HTMLResponse("Email not found", status_code=404)
    return HTMLResponse("If the account exists, reset instructions will be sent.")


@app.post("/contact")
async def contact(
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...)
):
    # Demo only: message is not stored or emailed.
    return HTMLResponse("Thank you for contacting us!")
