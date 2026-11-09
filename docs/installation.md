# Installazione locale e verifica dopo il riavvio

## Componenti persistenti

La repository distribuisce il marketplace `.agents/plugins/marketplace.json`, che punta alla
root del plugin `integrations/codex`. Registrazione e installazione si eseguono con il CLI Codex:

```sh
codex plugin marketplace add /absolute/path/to/learning-brain --json
codex plugin add learning-brain@learning-brain-local --json
codex plugin list --json
```

Il runtime Python è un'installazione distinta e persistente del pacchetto. Per l'installazione
personale, usare una directory dedicata sotto `~/.local/share/learning-brain/`, una configurazione
TOML sotto `~/.config/learning-brain/` e la registrazione `runtime.json` descritta nel README del
plugin. Usare percorsi assoluti per CLI e obsidian-wiki. Non inserire questi file personali in Git.

Le skill invocano il launcher incluso nel plugin. Il launcher legge la registrazione da XDG_CONFIG_HOME
oppure `~/.config`; non dipende dal PATH del terminale, dall'attivazione di una virtualenv o dalla
directory corrente. Il runtime installato è una copia del pacchetto: modificare la repository non
aggiorna automaticamente il runtime. Ricostruire/reinstallare il pacchetto quando cambia il core.

## Verifica eseguita prima del riavvio

Installazione locale effettuata il 2026-11-07 con Codex CLI 0.167.0:

- Il CLI elenca learning-brain@learning-brain-local come installed=true, enabled=true.
- La cache installata contiene entrambe le skill e il launcher condiviso.
- Il launcher della cache supera doctor in un ambiente con il solo PATH di sistema.
- Il runtime trova obsidian-wiki 2026.10.2 e la superficie di memoria adottata.
- La suite passa 51 test: 47 del core e 4 per risoluzione del runtime/config senza PATH applicativo.
- Nessun hook viene registrato; la configurazione del vault viene soltanto letta.

Questa verifica non dimostra ancora che una sessione Codex già aperta abbia aggiornato il proprio
catalogo di skill. Il client può conservare il catalogo fino al riavvio/nuova sessione.

## Dopo il riavvio

1. Verificare che learning-brain sia presente e attivo nel catalogo plugin del client.
2. Verificare che siano disponibili brain-recall e brain-debrief, senza duplicati.
3. Invocare brain-recall per una domanda già coperta dal vault; verificare il launcher effettivamente
   usato, le citazioni, il limite del contesto e l'assenza di scritture alla conoscenza.
4. Eseguire il ciclo di debrief con una fixture/vault di prova, controllando proposta, revisione,
   applicazione, replay e recupero. Il test non deve pubblicare fixture nel vault personale.
5. Registrare separatamente eventuali problemi di discovery, esecuzione o qualità semantica.

L'installazione non abilita la pubblicazione automatica e non sostituisce il pilot semantico.
Dalla 0.1.2 il plugin distribuisce hook di solo caricamento skill: dopo aggiornamento e
riavvio/nuova sessione, rivedere e considerare attendibili le definizioni nel client.
Il trust non è implicito nell’installazione. Non abilitiamo Stop/SessionEnd né pubblicazione.

Riferimenti: [CLI plugin](https://learn.chatgpt.com/docs/cli/reference) e
[marketplace locali](https://developers.openai.com/plugins/build/plugins).

## Correzione discovery 0.1.3

Il formato portabile della 0.1.2 caricava skill ma non hook in Codex CLI 0.167.0.
La 0.1.3 usa il manifest di compatibilità `.codex-plugin/plugin.json` senza root `plugin.json`.
Il controllo `scripts/check_codex_discovery.py` verifica hooks/list del runtime effettivo:
distingue discovery, enabled e trust. Dopo aggiornamento ricaricare/riavviare il client e
rivedere i tre hook Learning Brain visibili in /hooks. Se non compaiono, non limitarsi a
ripetere il riavvio: eseguire il controllo di discovery e confrontare runtime/ambiente.

## Attivazione 0.2.0

Nel TOML personale impostare automation = "review"; il valore predefinito è off.
Installare runtime e plugin aggiornati, riavviare e rivedere i nuovi hook. Eseguire
scripts/check_codex_discovery.py (sette handler su cinque eventi) e scripts/check_automation.py
con --plugin-root e --runtime assoluti: il secondo usa solo sorgenti sintetiche e un vault temporaneo.
La prova sintetica non dimostra la selezione semantica automatica nel client riavviato.

## Modalità autonoma 0.3.0

Impostare automation = "autonomous" nel TOML personale per delegare all'agente la pubblicazione
ordinaria dopo autorevisione. Il default del pacchetto resta off; review rimane disponibile.
L'aggiornamento del runtime elimina immediatamente i decision=block da Stop, anche per il
vecchio bridge. Per caricare istruzioni e protezione del bridge aggiornate, reinstallare il
plugin e rivedere una volta gli handler nuovi/modificati nel client. Non è una richiesta di
approvazione delle singole note e non va aggirato il trust degli hook.

check_automation.py supporta --mode autonomous e --mode review. Verifica che Stop non generi
continuazioni e che la capture successiva recuperi la precedente risposta finale. La verifica
delle decisioni semantiche dell'agente richiede uso reale: non viene simulata dal test meccanico.
