# Integrazione Codex locale

Questa directory è la root del plugin. Il CLI Python va installato separatamente dalla
repository con `pip install -e .` nell'ambiente scelto. Non viene incluso un server MCP e non
vengono duplicate le 40 skill wiki installate.

1. Preparare e verificare una configurazione locale con `learning-brain --config <file> doctor`.
2. Installare il CLI in un ambiente Python persistente e registrare i percorsi locali in
   `~/.config/learning-brain/runtime.json` (oppure sotto XDG_CONFIG_HOME):

   ```json
   {"schema_version": 1, "executable": "/absolute/runtime/bin/learning-brain", "config": "/absolute/config.toml"}
   ```

   Il file è personale e non va in Git. `scripts/run.py` legge questa registrazione: le skill
   funzionano anche se l'app riavviata non eredita il PATH del terminale. Il TOML dovrebbe usare
   un wiki_command assoluto. LEARNING_BRAIN_CONFIG rimane un override opzionale.
3. Dalla root della repository, registrare e installare il marketplace locale:

   ```sh
   codex plugin marketplace add . --json
   codex plugin add learning-brain@learning-brain-local --json
   ```

   Il manifest non registra hook; le skill sono brain-debrief e brain-recall.
4. Verificare il caricamento in una sessione nuova e usare prima un vault di prova.

La presenza dei file non prova il caricamento nel client. Le capacità e procedure del client
vanno controllate nella [documentazione ufficiale](https://developers.openai.com/plugins/build/plugins).

## Checkpoint opzionali, dopo il pilot

`hooks/checkpoints.example.json` è volutamente un esempio: non si chiama `hooks.json` e il
manifest non lo referenzia. Per abilitarlo in un'installazione manuale supportata, creare una
configurazione hook effettiva a partire dall'esempio dopo aver completato il gate di valutazione.
Non sovrascrivere `~/.codex/hooks.json`: aggiungere una sorgente/plugin e preservare Orca/Superset.

Il comando richiede `LEARNING_BRAIN_PYTHON` con il percorso assoluto del Python che ha installato
learning-brain e `LEARNING_BRAIN_CONFIG` con la configurazione. La disponibilità di queste
variabili nel terminale non implica che siano presenti nell'app desktop: verificarle nel processo
che avvia Codex. Gli hook nuovi o cambiati devono essere rivisti e considerati attendibili nel client.

Il recorder non pubblica note, non legge transcript, non avvia il modello e non blocca Stop.
Risponde con JSON valido anche se la registrazione fallisce; il fallimento è segnalato su stderr.
La perdita di un checkpoint non deve essere trattata come avvenuta acquisizione: il recupero
periodico via capture resta necessario. `drain` acquisisce solo i riferimenti registrati.

Per disabilitare, rimuovere la sorgente hook attivata o disattivarla nel client. I dati del vault
e la coda rimangono. Non sono previsti script che cancellano automaticamente questi dati.
