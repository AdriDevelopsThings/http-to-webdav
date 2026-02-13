from mimetypes import guess_type

from flask import Blueprint, Response, abort, stream_with_context

from http_webdav.file_backend import file_backend

bp = Blueprint("api", __name__)


@bp.route("/", defaults={"path": ""})
@bp.route("/<path>")
def get(path: str):
    file = file_backend.get_file("/" + path)
    if file is None:
        abort(404)
        return
    content_length, generator = file

    headers: dict[str, str] = {}
    if content_length is not None:
        headers["Content-Length"] = str(content_length)

    filename = path.split("/")[-1]
    mimetype = guess_type(filename)[0] or "application/octet-stream"
    headers["Content-Type"] = mimetype

    return Response(stream_with_context(generator), status=200, headers=headers)
