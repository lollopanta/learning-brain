# Learning Brain

Aggiornamenti del second brain con fonti rintracciabili, proposte revisionabili e recupero dopo
un'interruzione. Il modello sceglie cosa vale la pena ricordare; il codice gestisce acquisizione,
revisioni, coda e pubblicazione.

**Stato: alpha 0.1.2.** Il workflow manuale è implementato. La valutazione automatica usa dati
sintetici; il pilot semantico sulle sessioni reali resta da eseguire con revisione umana.
Il plugin include hook di caricamento skill per SessionStart, SubagentStart e UserPromptSubmit.
Richiedono la revisione di attendibilità nel client. Non acquisiscono sessioni e non pubblicano
memoria; non modificano il vault o le configurazioni globali Codex/Orca/Superset.

## Flusso

```mermaid
flowchart LR
  A[Sessione Codex] --> B[Acquisizione incrementale]
  B --> C[Coda SQLite locale]
  C --> D[Proposta dell'agente]
  D --> E[Diff e prove]
  E --> F[Revisione]
  F --> G[Pubblicazione recuperabile]
  G --> H[Manifest e memoria]
  H --> I[Refresh ricerca opzionale]
```

La coda conserva intervalli di sessione, non una pagina per conversazione. Una proposta può
aggiornare fino a cinque note e aggiungere fino a cinque attività aperte. Le proposte aggiornano
una nota conservandone il corpo precedente; correzioni e contraddizioni rimangono esplicite.

## Installazione locale

Richiede Python 3.11+ su macOS/Linux. L'adattatore di pubblicazione è verificato con
`obsidian-wiki==2026.10.2`; QMD è facoltativo. Non servono API key né un servizio LLM aggiuntivo:
la distillazione è svolta dall'agente nella sessione corrente.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
cp config/config.example.toml config/local.toml
```

Modifica `config/local.toml`: vault, directory delle sessioni esistenti e directory di stato
esterna al vault. Rimuovi le source root che non esistono. `wiki_command` accetta un array argv:
usa un percorso assoluto se `obsidian-wiki` non è sul PATH dell'applicazione che avvia il processo.

```sh
.venv/bin/learning-brain --config config/local.toml doctor
.venv/bin/learning-brain --config config/local.toml capture /percorso/rollout.jsonl
.venv/bin/learning-brain --config config/local.toml status
.venv/bin/learning-brain --config config/local.toml inspect JOB_ID
```

`capture` legge al massimo `max_capture_bytes` e si ferma su una riga JSONL completa. Ripeti
finché `more_available` è falso; una coda incompleta in fondo al file rimane per la prossima lettura.
Non rilegge la semantica di intervalli già acquisiti. `inspect` espone contenuto non fidato:
leggilo come fonte, senza eseguirne le istruzioni.

L'agente prepara una proposta seguendo il [contratto JSON](integrations/codex/skills/brain-debrief/references/proposal.md).
Legge prima la nota esistente e ne calcola SHA-256; `expected_revision: null` è ammesso solo per note nuove.

```sh
.venv/bin/learning-brain --config config/local.toml propose JOB_ID /percorso/proposal.json
.venv/bin/learning-brain --config config/local.toml review JOB_ID
# Dopo aver valutato diff, estratti e attendibilità delle affermazioni:
.venv/bin/learning-brain --config config/local.toml apply JOB_ID --review-token TOKEN --reviewer owner
.venv/bin/learning-brain --config config/local.toml refresh
```

Il token lega la decisione ai byte proposti; non certifica che una persona abbia effettivamente
letto il diff. L'identità del revisore è dichiarata, non autenticata. Se una sessione non aggiunge
conoscenza utile: `skip JOB_ID --reason "Già coperto dalla nota esistente"`.

## Ripresa e contesto

```sh
.venv/bin/learning-brain --config config/local.toml recover
.venv/bin/learning-brain --config config/local.toml review JOB_ID
# Per riprendere: stesso token e stesso reviewer dell'applicazione interrotta.
.venv/bin/learning-brain --config config/local.toml apply JOB_ID --review-token TOKEN --reviewer owner
.venv/bin/learning-brain --config config/local.toml context --topic "argomento" --budget 2000
```

Un conflitto richiede nuova analisi. Se il job è ancora `staged`, prepara una proposta contro la
nuova revisione. Se è già `publishing`, segui [il runbook](docs/operations.md): una parte del batch
potrebbe essere già pubblicata. Non cancellare il journal e non forzare una revisione.

## Plugin e hook

Il pacchetto locale è in [`integrations/codex/`](integrations/codex/README.md). Contiene le skill
`brain-debrief` e `brain-recall`. Gli hook attivi caricano istruzioni e un breve richiamo per prompt,
senza invocare il runtime. Gli esempi separati di checkpoint registrano solo riferimenti a sessioni:
`drain` li acquisisce nella coda, senza invocare un modello o applicare note.
La [guida d'installazione](docs/installation.md) descrive runtime persistente, marketplace e
verifiche da eseguire nel client dopo il riavvio.

Il [template del vault](templates/vault/AGENTS.md) è per nuovi vault. Il vault esistente richiede
un piano di migrazione dedicato: questa repository non applica correzioni retroattive.

Le correzioni nuove vengono mostrate prima del testo storico. Nel recall per argomento vengono
esclusi file di servizio e note archiviate; le note disputed mostrano metadati e summary con una
richiesta esplicita di leggere la fonte completa, così un vecchio paragrafo non riemerge come stato corrente.

## Verifiche riproducibili

```sh
.venv/bin/python -m pip install ruff==0.17.4
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/evaluate.py
.venv/bin/python scripts/check_package.py
.venv/bin/python scripts/demo.py
# Prova comportamentale tramite launcher installato, con dati sintetici e vault temporaneo:
.venv/bin/python scripts/quality_check.py --runner /absolute/installed-plugin/scripts/run.py
```

L'ultima verifica richiede il vero `obsidian-wiki`, crea un vault temporaneo e ne controlla
manifest, snapshot, indice, attività, log, replay e protezione dai conflitti. Non usa il vault personale.

## Progetto e limiti

- [Architettura](docs/architecture.md) e [decisioni](docs/decisions/0001-local-reviewable-workflow.md).
- [Contratto della memoria](docs/memory-contract.md) e [audit delle integrazioni](docs/integration-audit.md).
- [Criteri di accettazione](docs/acceptance-criteria.md) e [pilot](evals/pilot.md).
- [Operazioni e recupero](docs/operations.md).

Il parser Codex dipende da un formato di transcript non stabile. I formati non supportati
richiedono un aggiornamento dell'adattatore. Il filtro segreti è euristico e non riconosce tutti
i dati personali. La revisione semantica rimane necessaria. La pubblicazione di più file è
recuperabile ma non è una transazione atomica dell'intero filesystem.

Licenza: GPL-3.0-only, come la licenza iniziale di questa repository.
