import logging
import secrets
import string
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ai-hub-demo")

CODE_ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7

# Short links live only while the app runs (spec: links that survive a restart are out of scope).
links: dict[str, str] = {}


class LinkIn(BaseModel):
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def check_url(cls, url: str) -> str:
        # Checked and stored as sent, never trimmed or normalised.
        # The redirect percent-encodes unsafe characters in Location.
        if any(c.isspace() or not c.isprintable() for c in url):
            raise ValueError("url must not contain spaces or control characters")
        parts = urlsplit(url)
        if parts.scheme.lower() not in ("http", "https"):
            raise ValueError("url must use http or https")
        if not parts.hostname:
            raise ValueError("url must have a host")
        return url


class LinkOut(BaseModel):
    code: str
    short_url: str


def new_code() -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if code not in links:
            return code


@app.exception_handler(RequestValidationError)
async def log_invalid_request(request: Request, exc: RequestValidationError):
    # Log only where and why: the rejected input can hold personal data or tokens.
    errors = [(error["loc"], error["type"]) for error in exc.errors()]
    logger.warning("invalid request path=%s errors=%s", request.url.path, errors)
    return await request_validation_exception_handler(request, exc)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/links", status_code=201)
def create_link(link: LinkIn, request: Request) -> LinkOut:
    code = new_code()
    links[code] = link.url
    logger.info("short link created code=%s", code)
    return LinkOut(code=code, short_url=f"{str(request.base_url).rstrip('/')}/{code}")


@app.get("/{code}")
def follow_link(code: str) -> RedirectResponse:
    url = links.get(code)
    if url is None:
        # %r escapes newlines, so a crafted code cannot forge extra log lines.
        logger.warning("short link not found code=%r", code)
        raise HTTPException(status_code=404, detail="Short link not found")
    return RedirectResponse(url, status_code=302)
