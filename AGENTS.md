# Aerotech Docflow — Agent Instructions 

This system automates document scanning and linking physical documents to Planfix tasks.

It is a lightweight MVP service that connects:
- Planfix (task system)
- Local scanner (EPSON DS-790WN)
- File storage (local folder + Yandex Disk sync)

Language: Russian
- The system is designed for Russian-speaking operators.
- Russian is the only allowed language for logs, UI, and errors.
- English is allowed only for code-level constructs (functions, classes, APIs).

---

# 1. PURPOSE

The system converts physical documents into digital files and links them to Planfix tasks.

Core idea:

Planfix Task → Sent Request → Local Python Service → Scanner → PDF File → Storage → Planfix Update

---

# 2. SYSTEM OVERVIEW (SIMPLE ARCHITECTURE)

This is a single backend service.

Components:

- Planfix → triggers scan request via HTTP
- Python Service → processes request and coordinates everything
- Scanner → produces PDF ( via scan-to-folder)
- Storage → filesystem + Yandex Disk sync

---

# 3. MAIN WORKFLOW

1. Operator creates or opens a Planfix task "Document Entry"
2. Operator clicks "Scan"
3. Planfix sends HTTP request to backend service:
   POST /scan
4. Service receives request and starts scan process
5. Scanner produces PDF file in a folder
6. Service detects new file OR receives file directly
7. File is renamed and moved to archive structure
8. File is synced to Yandex Disk (automatic folder sync)
9. Service returns file path or link
10. Planfix task is updated with file reference

---

# 4. CORE PRINCIPLE

The system is NOT a document management system.

It is only a pipeline:

Scan → File → Link → Planfix

---

# 5. CODE STRUCTURE 

Simple structure only:

app/
  main.py
  planfix.py
  scanner.py
  storage.py

docs/
  technical-spec.md
  api-contract.md
  failure-map.md

.env
requirements.txt
README.md

---

# 6. API CONTRACT 

POST /scan

Request:
- planfix_task_id
- document_type
- number
- date
- counterparty (optional)

Response:
- status (ok/error)
- file_name
- file_path
- file_link (if available)

---

# 7. SCANNER MODEL

Preferred approach :

SCAN-TO-FOLDER MODE

- Scanner saves PDF into a known folder
- Service watches folder for new files
- Service picks up file and processes it

---

# 8. FILE HANDLING RULES

- Each scan generates one PDF file
- Files are never overwritten
- Filenames must be deterministic:

FORMAT:
DOCTYPE_DDMMYY_HHMMSS_NUMBER.pdf

Example:
НКЛ_090626_145712_2455B.pdf

---

# 9. RELIABILITY RULES

System must handle:

- scanner not available
- duplicate scan requests
- delayed file creation
- missing Planfix task ID
- corrupted or incomplete PDFs

System must NOT crash on errors.

---

# 10. LOGGING

All events must be logged locally:

- scan request received
- scan started
- file detected
- file saved
- response sent to Planfix

No external logging services in MVP.

---

# 11. NON-GOALS (IMPORTANT)

This system does NOT:

- store business data
- replace Planfix
- manage users or authentication
- implement database
- implement complex workflows

---

# 13. DEFINITION OF DONE

A feature is complete when:

- Planfix can send scan request
- scanner produces PDF
- service captures file
- file is saved correctly
- Planfix receives file link
- system can restart without breaking workflow