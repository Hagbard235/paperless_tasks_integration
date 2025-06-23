# paperless_tasks_integration
Ein Tool das beim erstellen/ändern von paperless-Dokumenten einen Eintrag bei Google Tasks macht undn einen Bearbeitugnsstatus integriert

## Konfiguration

Die Anwendung liest ihre Einstellungen aus `config.json`. Neu hinzugekommen sind
`SERVER_BASE_URL` (Basis-URL des Servers), `CUSTOM_FIELD_BEARBEITET` sowie die
Parameter `STATUS_LABEL_NEW` und `STATUS_LABEL_DONE`. Damit lassen sich die
Custom-Field-IDs und Bezeichnungen der Bearbeitungsstatus frei anpassen. Die
Google-Token-Datei kann über `GOOGLE_TASKS_TOKEN` gewählt werden. Alle diese
Werte werden beim Erzeugen von Links und beim Setzen der Statuswerte verwendet.


Im Konfigurationsdialog werden die Google-Parameter (Client-ID, Secret,
Token-Datei und Scopes) nicht mehr angezeigt, da diese üblicherweise nicht von
Hand geändert werden.
