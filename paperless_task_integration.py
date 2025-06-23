import os
import re
import requests
import datetime
import sys
import threading
import time
import json
from flask import Flask, request, render_template_string, redirect, url_for, Response, jsonify
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

CONFIG_PATH = os.environ.get("CONFIG_PATH", "config.json")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise Exception(f"Config-Datei fehlt: {CONFIG_PATH}")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_config(key, default=None):
    config = load_config()
    return config.get(key, default)

def set_config(key, value):
    config = load_config()
    config[key] = value
    save_config(config)

# ==== INIT/CONFIG DEFAULT (zum ersten Start!) ====
if not os.path.exists(CONFIG_PATH):
    save_config({
        "PAPERLESS_URL": "http://qnapserver:8010",
        "PAPERLESS_TOKEN": "DeinTokenHier",
        "SCOPES": ["https://www.googleapis.com/auth/tasks"],
        "ACTION_TASK_LIST_ID": "LISTE_ID_HIER",
        "ACTION_THRESHOLD": 49,
        "CUSTOM_FIELD_STATUS": 4,
        "CUSTOM_FIELD_AKTION": 5,
        "STATUS_LABEL_TO_ID": {
            "Unbearbeitet": "WBdb3hOCyFRkINdn",
            "Weitergeleitet": "mn1jNm0aR7zWhQgx",
            "Erledigt": "g6Nl8hQ56BDasAER",
            "keine Aktion": "WjcuDvnb9wWhkSEz",
            "Gelöscht": "iJEaIedgGFmn72dI"
        }
    })

# ==== GOOGLE TASKS SERVICE ====
def get_tasks_service():
    creds = Credentials.from_authorized_user_file('token.json', get_config("SCOPES"))
    return build('tasks', 'v1', credentials=creds)

# ==== PAPERLESS API HELPER ====
def get_document_meta_by_id(doc_id):
    api_url = f"{get_config('PAPERLESS_URL')}/api/documents/{doc_id}/"
    headers = {"Authorization": f"Token {get_config('PAPERLESS_TOKEN')}"}
    resp = requests.get(api_url, headers=headers)
    if resp.status_code != 200:
        print("Paperless-API Fehler:", resp.text)
        return None
    return resp.json()

def get_document_meta(doc_url=None, doc_id=None):
    if doc_id:
        return get_document_meta_by_id(doc_id)
    if doc_url:
        match = re.search(r'/documents/(\d+)/', doc_url)
        if not match:
            print("Konnte Dokumenten-ID nicht extrahieren!")
            return None
        doc_id = match.group(1)
        return get_document_meta_by_id(doc_id)
    print("Weder doc_url noch doc_id angegeben!")
    return None

def get_bearbeitet_am(doc):
    for cf in doc.get('custom_fields', []):
        if cf['field'] == 3:
            return cf['value']
    return None

def get_bearbeitungsstatus(doc):
    cf_status = get_config("CUSTOM_FIELD_STATUS")
    status_id_to_label = {v: k for k, v in get_config("STATUS_LABEL_TO_ID").items()}
    for cf in doc.get('custom_fields', []):
        if cf['field'] == cf_status:
            value = cf['value']
            return status_id_to_label.get(value, value)
    return "Unbearbeitet"

def get_aktion_wert(doc):
    cf_aktion = get_config("CUSTOM_FIELD_AKTION")
    for cf in doc.get('custom_fields', []):
        if cf['field'] == cf_aktion:
            try:
                return float(cf['value'] or 0)
            except Exception:
                return 0
    return 0

def set_bearbeitet_am(doc_id, datum):
    api_url = f"{get_config('PAPERLESS_URL')}/api/documents/{doc_id}/"
    headers = {"Authorization": f"Token {get_config('PAPERLESS_TOKEN')}"}
    resp = requests.get(api_url, headers=headers)
    if resp.status_code != 200:
        print(f"Fehler beim Abrufen von Dokument {doc_id}: {resp.text}")
        return False
    doc = resp.json()
    custom_fields = doc.get('custom_fields', [])
    for cf in custom_fields:
        if cf['field'] == 3:
            cf['value'] = datum
    payload = {'custom_fields': custom_fields}
    patch_resp = requests.patch(api_url, headers=headers, json=payload)
    if patch_resp.status_code != 200:
        print(f"Fehler beim Setzen von bearbeitet_am: {patch_resp.text}")
        return False
    print(f"Erledigt: Dokument {doc_id} wurde als bearbeitet markiert ({datum})")
    return True

def set_bearbeitungsstatus(doc_id, status_label):
    api_url = f"{get_config('PAPERLESS_URL')}/api/documents/{doc_id}/"
    headers = {"Authorization": f"Token {get_config('PAPERLESS_TOKEN')}"}
    resp = requests.get(api_url, headers=headers)
    if resp.status_code != 200:
        print(f"Fehler beim Abrufen von Dokument {doc_id}: {resp.text}")
        return False
    doc = resp.json()
    custom_fields = doc.get('custom_fields', [])
    found = False
    status_id = get_config("STATUS_LABEL_TO_ID").get(status_label)
    if not status_id:
        print(f"Unbekannter Status: {status_label}")
        return False
    cf_status = get_config("CUSTOM_FIELD_STATUS")
    for cf in custom_fields:
        if cf['field'] == cf_status:
            cf['value'] = status_id
            found = True
    if not found:
        custom_fields.append({'field': cf_status, 'value': status_id})
    payload = {'custom_fields': custom_fields}
    patch_resp = requests.patch(api_url, headers=headers, json=payload)
    if patch_resp.status_code != 200:
        print(f"Fehler beim Setzen von Bearbeitungsstatus: {patch_resp.text}")
        return False
    print(f"Bearbeitungsstatus für Dokument {doc_id} auf '{status_label}' gesetzt")
    return True

# ==== GOOGLE TASKS ====
def create_task(title, notes, list_id=None):
    if not list_id:
        list_id = get_config("ACTION_TASK_LIST_ID")
    service = get_tasks_service()
    body = {'title': title, 'notes': notes}
    task = service.tasks().insert(tasklist=list_id, body=body).execute()
    print('Aufgabe angelegt:', task.get('title'))

def is_task_already_present(service, doc_id, list_id=None):
    if not list_id:
        list_id = get_config("ACTION_TASK_LIST_ID")
    tasks = service.tasks().list(tasklist=list_id, showCompleted=True, showHidden=True).execute().get('items', [])
    marker = f"Dokument-ID: {doc_id}"
    for task in tasks:
        if marker in (task.get('notes') or ""):
            return True
    return False

def update_task_note_with_status(doc_id, new_status):
    service = get_tasks_service()
    heute = datetime.date.today().isoformat()
    tasks = service.tasks().list(tasklist=get_config("ACTION_TASK_LIST_ID"), showCompleted=True, showHidden=True).execute().get('items', [])
    for task in tasks:
        if f"Dokument-ID: {doc_id}" in (task.get('notes') or ""):
            notes = task['notes'] or ""
            # Status-Zeile ersetzen oder hinzufügen
            if "Status:" in notes:
                notes = re.sub(r"Status: .*", f"Status: {new_status} (am {heute})\n", notes)
            else:
                notes = f"Status: {new_status} (am {heute})\n" + notes
            service.tasks().patch(tasklist=get_config("ACTION_TASK_LIST_ID"), task=task['id'], body={"notes": notes}).execute()
            print(f"Status in Task-Notiz für Doc {doc_id} aktualisiert.")
            break

def get_status_from_notes(notes):
    match = re.search(r"Status:\s*([\wäöüÄÖÜß]+)", notes)
    if match:
        return match.group(1).capitalize()
    return None

def update_bearbeitet_am_for_completed_tasks():
    service = get_tasks_service()
    heute = datetime.date.today().isoformat()
    tasks = service.tasks().list(
        tasklist=get_config("ACTION_TASK_LIST_ID"),
        showCompleted=True,
        showHidden=True
    ).execute().get('items', [])
    erledigt = 0
    for task in tasks:
        if not task.get('completed'):
            continue
        notes = task.get('notes', '')
        match = re.search(r'Dokument-ID: (\d+)', notes)
        if not match:
            continue
        doc_id = match.group(1)
        status = get_status_from_notes(notes) or "Erledigt"
        doc = get_document_meta_by_id(doc_id)
        set_bearbeitet_am(doc_id, heute)
        set_bearbeitungsstatus(doc_id, "Erledigt")
        update_task_note_with_status(doc_id, "Erledigt")
        erledigt += 1
    if erledigt:
        print(f"{erledigt} Dokument(e) als erledigt markiert.")

app = Flask(__name__)

@app.route("/paperless_webhook", methods=["POST"])
def paperless_webhook():
    data = request.get_json(force=True)
    print("\nWebhook erhalten:", data)
    doc_id = data.get("id")
    if not doc_id:
        doc_url = data.get("doc_url")
        if doc_url:
            match = re.search(r'/documents/(\d+)/', doc_url)
            if match:
                doc_id = match.group(1)
    if not doc_id:
        print("Keine Dokumenten-ID im Payload!")
        return "Fehler", 400
    doc = get_document_meta_by_id(doc_id)
    if not doc:
        return "Fehler", 500
    aktion_wert = get_aktion_wert(doc)
    status = get_bearbeitungsstatus(doc)
    service = get_tasks_service()
    task = get_task_for_document(service, doc_id, list_id=get_config("ACTION_TASK_LIST_ID"))
    if task:
        notes = task.get('notes', '')
        status_in_task = get_status_from_notes(notes)
        if status != status_in_task:
            update_task_note_with_status(doc_id, status)
            print(f"Status in Google Tasks für Doc {doc_id} aktualisiert: {status_in_task} → {status}")
        else:
            print("Status schon synchron.")
        return "Status abgeglichen", 200
    if aktion_wert <= get_config("ACTION_THRESHOLD"):
        print(f"Dokument benötigt laut KI keine Bearbeitung ({aktion_wert}%)")
        return "Keine Aufgabe erzeugt", 200
    if status == "Erledigt":
        print(f"Dokument {doc_id} ist bereits erledigt – kein Task mehr nötig.")
        return "Bereits erledigt", 200
    paperless_url = get_config("PAPERLESS_URL")
    link_webui = f"{paperless_url}/documents/{doc_id}/"
    link_view_pdf = f"/view_pdf/{doc_id}"
    status_link = f"/status/{doc_id}"
    title = doc.get("title", "Paperless-Dokument")
    doc_type = doc.get("document_type")
    correspondent = doc.get("correspondent")
    added = doc.get("added")
    notes = (
        f"Status: Unbearbeitet\n"
        f"Status bearbeiten: {status_link}\n"
        f"Typ: {doc_type}\n"
        f"Person: {correspondent}\n"
        f"Hinzugefügt am: {added}\n"
        f"Web-Ansicht: {link_webui}\n"
        f"PDF-Ansicht: {link_view_pdf}\n"
        f"Dokument-ID: {doc_id}"
    )
    set_bearbeitungsstatus(doc_id, "Unbearbeitet")
    create_task(title=title, notes=notes, list_id=get_config("ACTION_TASK_LIST_ID"))
    return "OK", 200

def get_task_for_document(service, doc_id, list_id=None):
    if not list_id:
        list_id = get_config("ACTION_TASK_LIST_ID")
    tasks = service.tasks().list(tasklist=list_id, showCompleted=True, showHidden=True).execute().get('items', [])
    marker = f"Dokument-ID: {doc_id}"
    for task in tasks:
        if marker in (task.get('notes') or ""):
            return task
    return None

@app.route("/status/<int:doc_id>", methods=["GET", "POST"])
def set_status(doc_id):
    status_options = list(get_config("STATUS_LABEL_TO_ID").keys())
    if request.method == "POST":
        new_status = request.form.get("status")
        heute = datetime.date.today().isoformat()
        set_bearbeitet_am(doc_id, heute)
        set_bearbeitungsstatus(doc_id, new_status)
        update_task_note_with_status(doc_id, new_status)
        return f"<p>Status auf <b>{new_status}</b> gesetzt (bearbeitet am {heute}).<br><a href=\"{get_config('PAPERLESS_URL')}/documents/{doc_id}/\">Zurück zum Dokument</a></p>"
    doc = get_document_meta_by_id(doc_id)
    current_status = get_bearbeitungsstatus(doc)
    html = f"""
    <h2>Status für Dokument {doc_id} ändern</h2>
    <form method="post">
      <select name="status">
        {''.join([f'<option value="{s}"{" selected" if s==current_status else ""}>{s}</option>' for s in status_options])}
      </select>
      <button type="submit">Speichern</button>
    </form>
    <p>Aktueller Status: <b>{current_status}</b></p>
    """
    return render_template_string(html)

def start_periodic_completed_tasks_update(interval_minutes=5):
    def job():
        while True:
            try:
                print(f"[{datetime.datetime.now().isoformat()}] Prüfe erledigte Google Tasks ...")
                update_bearbeitet_am_for_completed_tasks()
            except Exception as e:
                print("Fehler beim Update-Job:", e)
            time.sleep(interval_minutes * 60)
    thread = threading.Thread(target=job, daemon=True)
    thread.start()

@app.route("/proxy_download/<int:doc_id>")
def proxy_download(doc_id):
    api_url = f"{get_config('PAPERLESS_URL')}/api/documents/{doc_id}/download/"
    headers = {"Authorization": f"Token {get_config('PAPERLESS_TOKEN')}"}
    resp = requests.get(api_url, headers=headers)
    if resp.status_code != 200:
        return f"Fehler beim Download von Dokument {doc_id}: {resp.text}", 500
    return Response(
        resp.content,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="paperless_{doc_id}.pdf"'
        }
    )

@app.route("/view_pdf/<int:doc_id>")
def view_pdf(doc_id):
    return render_template_string(f"""
    <html>
      <head><title>PDF-Ansicht {doc_id}</title></head>
      <body style="margin:0">
        <embed src="/proxy_download/{doc_id}" width="100%" height="98%" type="application/pdf">
        <div style="text-align:center;margin-top:8px">
          <a href="/proxy_download/{doc_id}" download>PDF herunterladen</a>
        </div>
      </body>
    </html>
    """)

    # === CONFIG-ADMIN-UI ===
@app.route("/config", methods=["GET", "POST"])
def config_ui():
    config = load_config()
    message = None

    if request.method == "POST":
        for key in config.keys():
            if key in request.form:
                value = request.form[key]
                # Versuche, JSON zu parsen (für Dicts und Listen)
                try:
                    parsed = json.loads(value)
                    config[key] = parsed
                except Exception:
                    config[key] = value
        save_config(config)
        message = "Konfiguration gespeichert."

    # HTML-Formular generieren
    html_fields = ""
    for key, value in config.items():
        field_type = "text"
        disp_value = value
        if isinstance(value, dict) or isinstance(value, list):
            disp_value = json.dumps(value, ensure_ascii=False, indent=2)
            field_type = "textarea"
        if field_type == "textarea":
            html_fields += f"""
            <label for="{key}">{key}</label><br>
            <textarea name="{key}" rows="5" cols="60">{disp_value}</textarea><br><br>
            """
        else:
            html_fields += f"""
            <label for="{key}">{key}</label>
            <input type="text" name="{key}" value="{disp_value}"><br><br>
            """

    html = f"""
    <html>
      <head>
        <title>Konfiguration bearbeiten</title>
        <style>
          body {{ font-family: sans-serif; margin: 40px; background: #f8f8fa; }}
          input[type="text"], textarea {{ width: 80%; border-radius: 6px; border: 1px solid #bbb; padding: 6px; }}
          label {{ font-weight: bold; margin-top: 12px; display: block; }}
          .save {{ margin-top: 18px; padding: 10px 18px; background: #4186e0; color: white; border-radius: 7px; border: none; font-size: 1.1em; }}
        </style>
      </head>
      <body>
        <h2>Konfiguration bearbeiten</h2>
        {f"<div style='color:green'>{message}</div>" if message else ""}
        <form method="POST">
            {html_fields}
            <button class="save" type="submit">Speichern</button>
        </form>
        <hr>
        <a href="/">Zurück zur Startseite</a>
      </body>
    </html>
    """
    return html


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "update_tasks":
        update_bearbeitet_am_for_completed_tasks()
    else:
        start_periodic_completed_tasks_update(interval_minutes=5)
        host = get_config("SERVER_HOST", "0.0.0.0")
        port = int(get_config("SERVER_PORT", 8080))
        print(
            f"Starte Webhook-Empfänger auf http://{host}:{port}/paperless_webhook"
        )
        app.run(host=host, port=port)
