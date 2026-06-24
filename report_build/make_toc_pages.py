#!/usr/bin/env python3
"""Extract real page numbers for each TOC entry from the rendered PDF and write toc_pages.json."""
import subprocess, json, re, sys

PDF = "/Volumes/BLACK_SHARK/MINOR_PROJECT/report_build/Meridian_Data_Mini_Project_Report.pdf"
txt = subprocess.run(["pdftotext","-layout",PDF,"-"],capture_output=True,text=True).stdout
pages = txt.split("\f")  # 1 entry per page; index0 = page1

def page_lines(i):  # 1-indexed
    return [l.strip() for l in pages[i-1].splitlines()] if 0 < i <= len(pages) else []

# body starts where Chapter 1's first sentence appears
body_start = None
for i in range(1, len(pages)+1):
    if "Databases are the backbone" in pages[i-1]:
        body_start = i; break
assert body_start, "could not locate body start"
offset = body_start - 1  # arabic = pdfpage - offset

ROMAN = {1:"i",2:"ii",3:"iii",4:"iv",5:"v",6:"vi",7:"vii",8:"viii",9:"ix",10:"x",11:"xi",12:"xii"}

def find_body(prefixes):
    for i in range(body_start, len(pages)+1):
        for ln in page_lines(i):
            if any(ln.startswith(p) for p in prefixes):
                return i - offset
    return None

def find_caps(token):
    for i in range(1, len(pages)+1):
        for ln in page_lines(i):
            if ln.startswith(token):
                return ROMAN.get(i-1, str(i-1))  # roman = pdfpage-1 (title page unnumbered)
    return None

def find_exact_line_body(s):
    for i in range(body_start, len(pages)+1):
        for ln in page_lines(i):
            if ln == s:
                return i - offset
    return None

entries = [
  "List of Tables","List of Figures","Abbreviations","Abstract",
  "Chapter 1: Introduction","1.1 State of the Art","1.2 Motivation","1.3 Problem Statement","1.4 Objectives",
  "1.5 Methodology","1.6 Innovation","1.7 Organization of the Report",
  "Chapter 2: Literature Review","2.1 Literature Review",
  "Chapter 3: Requirements","3.1 Functional Requirements","3.2 Non-Functional Requirements",
  "3.3 Hardware Requirements","3.4 Software Requirements","3.5 Summary",
  "Chapter 4: Module Design & Architecture","4.1 Design Description","4.2 High Level Design","4.2.1 System Architecture",
  "4.3 Detailed Design","4.3.1 Structure Chart","4.3.2 Functional Description of the Modules",
  "Chapter 5: Implementation","5.1 Dataset Description","5.2 Programming Language Selection","5.3 Platform Selection",
  "5.4 Code Snippet / Pseudocode","5.5 Summary",
  "Chapter 6: Results and Discussion","6.1 Evaluation Metrics","6.2 Experimental Results","6.3 Validation and Testing",
  "6.3.1 Unit Testing","6.3.2 Integration Testing","6.3.3 System Testing","6.4 Performance Analysis","6.5 Summary",
  "Chapter 7: Summary, Conclusion & Future Enhancements","7.1 Summary","7.2 Conclusion","7.3 Future Enhancements",
  "References","Appendix A: Publication Details","Appendix B: Certificate for External Internship",
]
caps = {"List of Tables":"LIST OF TABLES","List of Figures":"LIST OF FIGURES",
        "Abbreviations":"ABBREVIATIONS","Abstract":"ABSTRACT"}

out = {}
for t in entries:
    if t in caps:
        out[t] = find_caps(caps[t])
    elif t == "References":
        out[t] = find_exact_line_body("References")
    elif t.startswith("Chapter") or t.startswith("Appendix"):
        out[t] = find_body([t.split(":")[0] + ":"])
    else:
        out[t] = find_body([t])

missing = [k for k,v in out.items() if v is None]
json.dump(out, open("/Volumes/BLACK_SHARK/MINOR_PROJECT/report_build/toc_pages.json","w"), indent=1)
print("body_start pdf page:", body_start, "offset:", offset)
print("resolved:", sum(1 for v in out.values() if v is not None), "/", len(entries))
if missing: print("MISSING:", missing)
for k,v in out.items(): print(f"  {v!s:>5}  {k}")
