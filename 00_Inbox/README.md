# 00_Inbox

## Purpose

Drop zone for incoming PDF files. Place new literature PDFs here for processing.

## Auto-Generated Content

None. This directory expects manual PDF placement.

## User Editing

**Yes** — add PDF files to be processed by the Scientra Copilot workflow.

## Workflow

1. Place `.pdf` files here
2. Run `python workflow.py run --input-dir 00_Inbox`
3. PDFs are copied to `01_PDF/` and processed through the pipeline
