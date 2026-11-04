# RealScope

A website for **2nd PU Biology** students. It puts each specimen's **lab-manual diagram** next to a
**real microscope image** of the same specimen. The site has four parts:

* **Specimens**: search and filter all 53 specimens by topic. Each card shows the lab-manual diagram.
* **Slide viewer**: the diagram and the real image side by side, with zoom, a labels on/off switch, the image source and the manual page.
* **Mistakes**: 13 common slide mistakes (air bubbles, dust and so on), with how to spot and fix each one.
* **Lab manual**: the full manual, page by page.

Everything is built from two inputs: the lab manual PDF and a CSV of image links.

---

## Quick start (Windows, VS Code)

1. **Install Python 3.9 or newer** from python.org. During setup, tick **"Add python.exe to PATH"**.
2. **Install Tesseract OCR.** It is a separate program, used to read figure captions:
   https://github.com/UB-Mannheim/tesseract/wiki
   Keep the default install folder `C:\Program Files\Tesseract-OCR`.
3. **Open the `RealScope` folder in VS Code**, open a terminal, and run:
   ```
   python -m pip install -r requirements.txt
   python Scripts/run_all.py
   ```
4. The website opens in your browser when the run finishes. You can open it again any time from
   `Data/website/index.html`.

**You need an internet connection for the first run**, so that the real images can be downloaded.

On Mac or Linux, use the same commands; you may need `python3` instead of `python`. Install Tesseract with
`brew install tesseract` (Mac) or `sudo apt install tesseract-ocr` (Linux).

### How long it takes

* **First run:** about 4–5 minutes. It extracts the diagrams, downloads the images and renders the manual pages.
* **Later runs:** a few seconds. Anything that has not changed is reused, and images are never downloaded twice.

---

## Folders

```
RealScope/
├── README.md                          this file
├── requirements.txt                   Python packages
├── Source/
│   └── lab_manual.pdf                 the II PUC Biology lab manual (keep this exact name)
├── Scripts/                           all code (.py only)
│   ├── run_all.py                     <- RUN THIS: does every step in order
│   ├── extraction/                    cuts the diagrams out of the PDF
│   ├── fetch/fetch_real_images.py     downloads the real images (once)
│   ├── website/                       matches CSV rows to diagrams, builds the website
│   └── validation/                    checks the diagrams and the website
└── Data/
    ├── input/specimens.csv            THE SPECIMEN LIST: the only thing you normally edit
    ├── raw_data/                      extracted pages, diagram crops, images_metadata.csv
    ├── real_slide_images/             downloaded images (created by the run)
    │   └── manual/                    put images here by hand if a link won't download
    ├── specimen_matching.csv          which CSV row was matched to which diagram
    ├── website_report.csv             per specimen: diagram / image / page status
    ├── website/                       THE WEBSITE: open index.html
    └── run_log.txt                    everything the last run printed (created by the run)
```

---

## How the real images get onto the website

For each specimen, the website uses the first of these that works:

1. **An image you saved yourself** in `Data/real_slide_images/manual/`, named after the figure (for example `Metaphase.jpg`) or its image id (for example `img_016_03.jpg`).
2. **The downloaded copy.** The first run downloads each link once and keeps it, so it works offline after that.
3. **The link itself.** If a download fails, the browser loads the image straight from the link in the CSV whenever the site is opened with internet.

If none of these works, the viewer shows "Image could not be loaded" with a button to open the original link.
Links that failed to download are listed in `Data/real_slide_images/FAILED_DOWNLOADS.txt`, with the reason.

Known issue: the **Pentalocular ovary** link (row 5, Cornell) does not respond, so that image will not show.
Fix it by replacing that link in the CSV, or by saving an image into the `manual/` folder.

---

## Changing the specimen list

Edit `Data/input/specimens.csv` in Excel and save it as CSV. The columns are:
No., Manual page, Figure, Magnification, Your image Links, Licencse.
Then run `python Scripts/run_all.py` again.

* Rows are matched to diagrams by **manual page + figure name**, not by row number. You can reorder or
  delete rows safely. Check `Data/specimen_matching.csv` to see each match.
* If a name is reported as **unmatched**, either use the name printed in the manual, or add the new name to
  `NAME_ALIASES` in `Scripts/website/site_content.py`.
* If the same link is given for two different specimens, that image is held back and the run warns you.
* Only the steps affected by your change run again.

---

## Options

```
python Scripts/run_all.py [option]
```

| Option | What it does |
|---|---|
| *(none)* | normal run: reuses everything that hasn't changed |
| `--offline` | no internet; use the images already downloaded |
| `--retry-failed` | try again the links that were refused last time |
| `--refetch` | download every image again |
| `--rebuild` | redo everything from scratch |
| `--no-open` | don't open the browser at the end |
| `--install` | install missing Python packages first |

---

## If something goes wrong

| Message | Fix |
|---|---|
| `Tesseract OCR ... was not found` | Install Tesseract (step 2) and restart VS Code. |
| `No module named ...` | Run `python -m pip install -r requirements.txt` (or add `--install`). |
| `lab_manual.pdf not found` | Put the PDF in `Source/` with exactly that name. |
| An image is missing on the site | See `FAILED_DOWNLOADS.txt`. Fix the link in the CSV, or save the image into `Data/real_slide_images/manual/`. |
| A specimen is "not matched" | Check its page number and name against the manual (see `specimen_matching.csv`). |

The last line of the run says **RESULT: PASS** when every check succeeded.

---

## Notes

* Diagram crops keep every printed label whole. The website copies are straightened and cleaned, and the original crops are not changed.
* The Mistakes pictures are generated by code and marked "Simulated view".
* The short descriptions are general textbook facts written for the site, not quotes from the manual.
* Image credits are shown as written in the CSV.

**Authors:** BN.MOHITH (website and code), ATIF K (image collection and specimen CSV).
**Repository:** https://github.com/BN-Mohith/RealScope
