# evernote_utils

Got an old Evernote `.enex` export sitting on your disk and no working way to open it? This script turns one (or many) `.enex` files into a tidy folder of HTML you can read in any browser, with attachments saved next to each note and a clickable index of everything.

No Evernote account, login, or API token needed. The script only reads the files you already have. Runs locally with a small GUI — no command-line gymnastics.

## What you get

For an export with N notes, you get:

```
output/
├── index.html                              ← clickable list of every note
├── 2024-03-12_141522 my-first-note/
│   ├── index.html                          ← the note, with metadata
│   ├── note.pdf                            ← optional, if WeasyPrint is installed
│   └── attachments/
│       ├── photo.jpg
│       └── slides.pdf
└── 2024-03-15_092008 another-note/
    └── …
```

Each note keeps its title, created/updated dates, tags, and original attachments. Inline images stay inline. Links between notes that point at attachments still resolve. Checkboxes (`<en-todo>`) become real HTML checkboxes.

## Why this exists

If you ever exported a notebook from Evernote — whether years ago, when leaving the app, or just as a backup — you ended up with one or more `.enex` files. They're XML, technically readable, but useless without something that understands ENML (Evernote's internal HTML dialect) and can pull the base64-encoded attachments back out.

Most of the existing converters either need an Evernote account, a paid app, or a now-broken cloud service. This one needs none of that. Just Python, a few libraries, and your `.enex` file.

## Features

- **Streams huge exports** with `lxml.iterparse` — works on multi-GB `.enex` files without loading everything into memory
- **One folder per note**, named with the creation date and a slugified title, so they sort chronologically
- **Per-note or shared attachments** — keep each note's media alongside it, or pool everything into a single `attachments/` directory
- **Clean ENML → HTML** — strips Evernote's `data-*` cruft, fixes `<en-media>` references, makes inline images and attachment links work
- **Optional PDF per note** via [WeasyPrint](https://weasyprint.org/) — same content as the HTML, just printable
- **Top-level index.html** with sortable rows of every note, so you can browse the whole export at a glance
- **GUI included** — pick input/output, toggle options, click Run. No flags to memorize.

## Install

Requires Python 3.9+.

```bash
git clone https://github.com/lucasgfsvd/evernote_utils.git
cd evernote_utils
pip install -r requirements.txt
```

WeasyPrint is only pulled in if you want PDF output — and it has [native dependencies](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) (Pango, GTK on Windows). If PDF isn't important to you, install only the first three lines of `requirements.txt`; HTML output works fine without WeasyPrint.

## Run

```bash
python evernote_extract.py
```

A small window opens:

| Field | What to put |
|---|---|
| **Input** | An `.enex` file, or a folder containing several. The Browse button asks for a file first; cancel that dialog to pick a folder instead. |
| **Output folder** | Where the per-note folders will be written. Created if it doesn't exist. |
| **Use one shared attachments/ folder** | Off (default): each note gets its own `attachments/` subdirectory. On: a single `attachments/` directory at the top level, shared by all notes. |
| **Also write a PDF per note** | Off (default). Requires WeasyPrint installed. If checked but WeasyPrint is missing, you get HTML anyway plus a warning marker. |
| **Max folder-name length** | Default 80. Longer titles are truncated when used as folder names. |

Click **Run**. Processing runs on a background thread so the window stays responsive. When it finishes, open `index.html` in your output folder to start browsing.

## Getting a `.enex` file in the first place

If you still have the Evernote desktop app:

1. Right-click a notebook (or select multiple notes) → **Export notes…**
2. Choose **ENEX (.enex)** as the format
3. Save anywhere

If you don't have Evernote installed anymore but have an old export from years back, that file is still good — `.enex` is a stable, self-contained format. It includes the notes' text, metadata, and base64-encoded attachments all in one XML file.

## Limitations

- ENML is forgiving and the wild has some unusual variants. The parser uses `recover=True` and `huge_tree=True`, but if you find a note that comes out wrong, an issue with the offending `.enex` snippet (anonymized) is the fastest way to get it fixed.
- Encrypted note contents (`<en-crypt>`) are passed through as-is — Evernote's per-note encryption isn't unwrapped here.
- Calendar/reminder metadata is preserved as note metadata but not rendered specially.

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, ship it in something else. No warranty.
