#!/usr/bin/env python3
"""
ENEX extractor: notes + attachments → organized folders, HTML (and optional PDF).

- Streams very large .enex with lxml.iterparse
- Each note goes in its own folder
- Attachments saved next to the note (or shared folder toggle)
- ENML → clean HTML with working links and inline images
- Optional PDF via WeasyPrint
- Builds a root index.html

Deps:
  pip install lxml beautifulsoup4 python-slugify weasyprint  # weasyprint optional
"""

from __future__ import annotations
import base64, binascii, hashlib, os, re, datetime as dt, textwrap
from pathlib import Path
from typing import Dict, Optional, Tuple, List

from lxml import etree
from bs4 import BeautifulSoup
from slugify import slugify

try:
    from weasyprint import HTML as WHTML

    WEASY_OK = True
except Exception:
    WEASY_OK = False

MIME_EXT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
    "image/tiff": "tif",
    "application/pdf": "pdf",
    "application/zip": "zip",
    "application/x-zip-compressed": "zip",
    "text/plain": "txt",
    "text/csv": "csv",
    "text/html": "html",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/wav": "wav",
    "video/mp4": "mp4",
}

SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._ -]+")


def slug(text: str, max_length: int) -> str:
    try:
        # python-slugify ≥ 5 supports max_length; lowercase may not exist
        return slugify(text, max_length=max_length)
    except TypeError:
        # very old slugify: fall back to a simple sanitizer
        s = re.sub(r"\s+", "-", text.strip())
        s = re.sub(r"[^A-Za-z0-9._-]+", "-", s)
        return s[:max_length] if max_length else s


def safe_filename(name: str, max_len: int = 127) -> str:
    name = name.strip().replace("\n", " ").replace("\r", " ")
    name = SAFE_NAME_RE.sub("_", name)
    name = re.sub(r"\s+", " ", name)
    return name[:max_len] if len(name) > max_len else name


def timestamp_to_datestr(ts: str) -> str:
    ts = ts.strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ", "%Y%m%dT%H%M%S%z"):
        try:
            d = dt.datetime.strptime(ts, fmt)
            return d.strftime("%Y-%m-%d_%H%M%S")
        except Exception:
            pass
    return ts.replace(":", "").replace(" ", "_").replace("T", "_").replace("Z", "")


def guess_ext(mime: Optional[str], fallback: str = "bin") -> str:
    return MIME_EXT.get((mime or "").lower(), fallback)


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def load_enml_to_html(
    enml: str,
    hash_to_attachment: Dict[str, Tuple[str, str]],  # md5 -> (rel_path, mime)
) -> str:
    soup = BeautifulSoup(enml or "", "html.parser")
    root = soup.find("en-note")
    body = root if root else soup

    for todo in body.find_all("en-todo"):
        checked = todo.get("checked", "").lower() in ("true", "checked")
        checkbox = soup.new_tag("input")
        checkbox.attrs["type"] = "checkbox"
        if checked:
            checkbox.attrs["checked"] = ""
        checkbox.attrs["disabled"] = ""
        todo.replace_with(checkbox)

    for media in body.find_all("en-media"):
        h = (media.get("hash") or "").lower()
        mime = media.get("type", "")
        if h and h in hash_to_attachment:
            rel_path, amime = hash_to_attachment[h]
            mm = amime or mime or ""
            if mm.startswith("image/"):
                img = soup.new_tag("img")
                img.attrs["src"] = rel_path
                if media.get("width"):
                    img.attrs["width"] = media.get("width")
                if media.get("height"):
                    img.attrs["height"] = media.get("height")
                media.replace_with(img)
            else:
                a = soup.new_tag("a", href=rel_path)
                a.string = Path(rel_path).name
                media.replace_with(a)
        else:
            media.replace_with(soup.new_tag("span").insert(0, "[missing attachment]"))

    for tag in body.find_all():
        for k in [k for k in list(tag.attrs.keys()) if k.startswith("data-")]:
            del tag.attrs[k]

    html = str(body)
    if not html.lower().strip().startswith("<html"):
        html = f"<html><head><meta charset='utf-8'></head><body>{html}</body></html>"
    return html


def html_wrap(
    title: str, body_html: str, meta: Dict[str, str], attachments: List[Tuple[str, str]]
) -> str:
    meta_rows = "".join(
        f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in meta.items() if v
    )
    meta_table = f"<table class='meta'>{meta_rows}</table>" if meta_rows else ""
    att_ul = ""
    if attachments:
        items = "".join(
            f"<li><a href='{rel}' target='_blank'>{Path(rel).name}</a> <small>({mime})</small></li>"
            for rel, mime in attachments
        )
        att_ul = f"<section><h3>Attachments</h3><ul>{items}</ul></section>"
    css = """
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,'Helvetica Neue',Arial,sans-serif;margin:2rem;line-height:1.45}
    h1{font-size:1.6rem;margin-top:0}
    .meta{border-collapse:collapse;margin:1rem 0}
    .meta th,.meta td{border:1px solid #ccc;padding:.4rem .6rem;text-align:left}
    img{max-width:100%;height:auto}
    hr{margin:1.5rem 0;border:none;border-top:1px solid #ddd}
    """
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<h1>{title}</h1>
{meta_table}
<hr/>
{body_html}
{att_ul}
</body>
</html>"""


def write_pdf_if_enabled(html_path: Path, pdf_path: Path) -> Optional[str]:
    if not WEASY_OK:
        return "WeasyPrint not installed. Skipping PDF."
    try:
        WHTML(filename=str(html_path)).write_pdf(str(pdf_path))
        return None
    except Exception as e:
        return f"PDF error: {e}"


def build_index(root_out: Path, entries: List[Dict[str, str]]) -> None:
    rows = []
    for e in entries:
        rows.append(
            f"<tr><td>{e.get('created','')}</td>"
            f"<td><a href='{e['rel_html']}'>{e['title']}</a></td>"
            f"<td>{e.get('updated','')}</td>"
            f"<td>{e.get('tags','')}</td></tr>"
        )
    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>ENEX export index</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,'Helvetica Neue',Arial,sans-serif;margin:2rem}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.4rem .6rem;text-align:left;vertical-align:top}}
th{{background:#f7f7f7}}
</style>
</head>
<body>
<h1>Notes</h1>
<table>
<thead><tr><th>Created</th><th>Title</th><th>Updated</th><th>Tags</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody></table>
</body></html>"""
    (root_out / "index.html").write_text(html, encoding="utf-8")


def parse_note(note_el: etree._Element) -> Dict:
    get = lambda tag: (note_el.findtext(tag, default="") or "").strip()
    title = get("title") or "Untitled"
    content = get("content")
    created = get("created")
    updated = get("updated")
    tags = [t.text.strip() for t in note_el.findall("tag") if t is not None and t.text]
    guid = get("guid")

    resources = []
    for res in note_el.findall("resource"):
        data_el = res.find("data")
        mime_el = res.find("mime")
        attrs_el = res.find("resource-attributes")
        filename_el = attrs_el.find("file-name") if attrs_el is not None else None

        raw = b""
        if data_el is not None and data_el.text:
            blob = data_el.text.strip()
            try:
                raw = base64.b64decode(blob)
            except binascii.Error:
                raw = b""
        mime = mime_el.text.strip() if (mime_el is not None and mime_el.text) else ""
        fname = (
            filename_el.text.strip()
            if (filename_el is not None and filename_el.text)
            else ""
        )
        md5 = md5_bytes(raw) if raw else None

        resources.append({"data": raw, "mime": mime, "filename": fname, "md5": md5})

    return {
        "title": title,
        "content": content,
        "created": created,
        "updated": updated,
        "tags": tags,
        "guid": guid,
        "resources": resources,
    }


def extract_one_enex(
    enex_path: Path,
    out_root: Path,
    shared_attachments: bool,
    make_pdf: bool,
    max_title: int,
) -> int:
    out_root.mkdir(parents=True, exist_ok=True)
    shared_att_dir = out_root / "attachments"
    if shared_attachments:
        shared_att_dir.mkdir(parents=True, exist_ok=True)

    parser = etree.iterparse(
        str(enex_path), events=("end",), tag="note", recover=True, huge_tree=True
    )
    index_entries: List[Dict[str, str]] = []
    note_counter = 0

    for _, note_el in parser:
        note_counter += 1
        note = parse_note(note_el)
        title = note["title"] or f"Untitled {note_counter}"
        created_ds = timestamp_to_datestr(note["created"]) if note["created"] else ""
        base_name = f"{created_ds} {title}" if created_ds else title
        base_name = safe_filename(slug(base_name, max_title)) or f"note_{note_counter}"

        note_dir = out_root / base_name
        i = 1
        while note_dir.exists():
            i += 1
            note_dir = out_root / f"{base_name}__{i}"
        note_dir.mkdir(parents=True, exist_ok=True)

        att_dir = shared_att_dir if shared_attachments else (note_dir / "attachments")
        if not shared_attachments:
            att_dir.mkdir(parents=True, exist_ok=True)

        hash_to_att: Dict[str, Tuple[str, str]] = {}
        att_list: List[Tuple[str, str]] = []
        for idx, res in enumerate(note["resources"], start=1):
            data = res["data"] or b""
            mime = res["mime"] or ""
            ext = guess_ext(mime)
            name = res["filename"] if res["filename"] else f"attachment_{idx}.{ext}"
            name = safe_filename(name)
            dest = att_dir / name
            j = 1
            while dest.exists():
                dest = att_dir / f"{dest.stem}_{j}{dest.suffix}"
                j += 1
            if data:
                dest.write_bytes(data)
                rel = os.path.relpath(dest, start=note_dir)
                att_list.append((rel, mime))
                if res["md5"]:
                    hash_to_att[res["md5"].lower()] = (rel, mime)

        body_html = load_enml_to_html(note["content"] or "", hash_to_att)
        meta = {
            "Created": note["created"] or "",
            "Updated": note["updated"] or "",
            "Tags": ", ".join(note["tags"]) if note["tags"] else "",
            "GUID": note["guid"] or "",
        }
        final_html = html_wrap(title, body_html, meta, att_list)

        html_path = note_dir / "index.html"
        html_path.write_text(final_html, encoding="utf-8")

        if make_pdf:
            err = write_pdf_if_enabled(html_path, note_dir / "note.pdf")
            if err:
                marker = out_root / "_PDF_WARNING.txt"
                if not marker.exists():
                    marker.write_text(
                        "PDF generation requested but WeasyPrint is missing or failed. "
                        "Install: pip install weasyprint",
                        encoding="utf-8",
                    )

        rel_html = os.path.relpath(html_path, start=out_root)
        index_entries.append(
            {
                "rel_html": rel_html,
                "title": title,
                "created": meta["Created"],
                "updated": meta["Updated"],
                "tags": meta["Tags"],
            }
        )

        note_el.clear()
        while note_el.getprevious() is not None:
            del note_el.getparent()[0]

    build_index(out_root, index_entries)
    return len(index_entries)


def run(
    INPUT_PATH: Path,
    OUTPUT_ROOT: Path,
    SHARED_ATTACHMENTS: bool,
    MAKE_PDF: bool,
    MAX_TITLE: int,
) -> None:
    INPUT_PATH = Path(INPUT_PATH)
    OUTPUT_ROOT = Path(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    if INPUT_PATH.is_file() and INPUT_PATH.suffix.lower() == ".enex":
        print(f"Processing {INPUT_PATH.name}")
        n = extract_one_enex(
            INPUT_PATH, OUTPUT_ROOT, SHARED_ATTACHMENTS, MAKE_PDF, MAX_TITLE
        )
        print(f"Notes extracted: {n}")
    elif INPUT_PATH.is_dir():
        total = 0
        for p in sorted(INPUT_PATH.rglob("*.enex")):
            print(f"Processing {p.relative_to(INPUT_PATH)}")
            # put each .enex into its own subfolder under OUTPUT_ROOT
            enex_out = OUTPUT_ROOT / p.stem
            n = extract_one_enex(p, enex_out, SHARED_ATTACHMENTS, MAKE_PDF, MAX_TITLE)
            total += n
        print(f"Done. Total notes extracted: {total}")
    else:
        raise FileNotFoundError(
            "INPUT_PATH must be a .enex file or a folder containing .enex files"
        )

    print(
        f"Open: {OUTPUT_ROOT / 'index.html' if (OUTPUT_ROOT/'index.html').exists() else OUTPUT_ROOT}"
    )


def launch_gui() -> None:
    import threading
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("Evernote ENEX Extractor")
    root.resizable(False, False)

    input_var = tk.StringVar()
    output_var = tk.StringVar()
    shared_var = tk.BooleanVar(value=False)
    pdf_var = tk.BooleanVar(value=False)
    title_var = tk.IntVar(value=80)
    status_var = tk.StringVar(
        value="Pick an .enex file (or a folder containing .enex files) to begin."
    )

    def pick_input() -> None:
        path = filedialog.askopenfilename(
            title="Select an .enex file (Cancel to pick a folder instead)",
            filetypes=[("Evernote export", "*.enex"), ("All files", "*.*")],
        )
        if not path:
            path = filedialog.askdirectory(
                title="Select a folder containing .enex files"
            )
        if path:
            input_var.set(path)

    def pick_output() -> None:
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            output_var.set(path)

    def on_run() -> None:
        in_path = input_var.get().strip()
        out_path = output_var.get().strip()
        if not in_path or not Path(in_path).exists():
            messagebox.showerror(
                "Missing input", "Please select an existing .enex file or folder."
            )
            return
        if not out_path:
            messagebox.showerror(
                "Missing output", "Please select an output folder."
            )
            return
        if pdf_var.get() and not WEASY_OK:
            cont = messagebox.askyesno(
                "WeasyPrint not available",
                "PDF output is selected but WeasyPrint isn't installed.\n\n"
                "HTML will still be produced for every note. Continue anyway?",
            )
            if not cont:
                return

        run_btn.config(state="disabled")
        status_var.set("Working… this can take a while for big exports.")

        def worker() -> None:
            try:
                run(
                    Path(in_path),
                    Path(out_path),
                    shared_var.get(),
                    pdf_var.get(),
                    int(title_var.get()),
                )

                def on_done() -> None:
                    status_var.set("Done.")
                    messagebox.showinfo(
                        "Done", f"Notes extracted to:\n{out_path}"
                    )

                root.after(0, on_done)
            except Exception as exc:
                err = str(exc)

                def on_err() -> None:
                    status_var.set("Error.")
                    messagebox.showerror("Error", err)

                root.after(0, on_err)
            finally:
                root.after(0, lambda: run_btn.config(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    frm = ttk.Frame(root, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")
    pad = {"padx": 8, "pady": 4}

    ttk.Label(frm, text="Input (.enex file or folder):").grid(
        row=0, column=0, sticky="w", **pad
    )
    ttk.Entry(frm, textvariable=input_var, width=60).grid(
        row=1, column=0, sticky="we", **pad
    )
    ttk.Button(frm, text="Browse…", command=pick_input).grid(row=1, column=1, **pad)

    ttk.Label(frm, text="Output folder:").grid(row=2, column=0, sticky="w", **pad)
    ttk.Entry(frm, textvariable=output_var, width=60).grid(
        row=3, column=0, sticky="we", **pad
    )
    ttk.Button(frm, text="Browse…", command=pick_output).grid(row=3, column=1, **pad)

    opts = ttk.LabelFrame(frm, text="Options", padding=8)
    opts.grid(row=4, column=0, columnspan=2, sticky="we", **pad)
    ttk.Checkbutton(
        opts,
        text="Use one shared attachments/ folder (instead of per-note)",
        variable=shared_var,
    ).grid(row=0, column=0, sticky="w")
    ttk.Checkbutton(
        opts,
        text="Also write a PDF per note (requires WeasyPrint)",
        variable=pdf_var,
    ).grid(row=1, column=0, sticky="w")

    title_row = ttk.Frame(opts)
    title_row.grid(row=2, column=0, sticky="w", pady=(4, 0))
    ttk.Label(title_row, text="Max folder-name length:").pack(side="left")
    ttk.Spinbox(
        title_row, from_=20, to=200, width=5, textvariable=title_var
    ).pack(side="left", padx=(6, 0))

    ttk.Label(
        frm,
        textvariable=status_var,
        foreground="#555",
        wraplength=560,
        justify="left",
    ).grid(row=5, column=0, columnspan=2, sticky="we", **pad)

    run_btn = ttk.Button(frm, text="Run", command=on_run)
    run_btn.grid(row=6, column=0, columnspan=2, **pad)

    root.mainloop()


if __name__ == "__main__":
    launch_gui()
