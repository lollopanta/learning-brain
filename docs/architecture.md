# Architettura

## Confini

`learning-brain` è un livello di orchestrazione sopra un vault Obsidian e il CLI obsidian-wiki.
La conoscenza personale vive nel vault. Codice, template e casi sintetici vivono qui.
SQLite, copie ridotte dei messaggi acquisiti, percorsi locali e richieste hook vivono in
`state_dir`, che deve essere esterna al vault e non va sincronizzata con Git.

## Componenti

| Modulo | Responsabilità |
|---|---|
| `config.py` | Configurazione TOML esplicita, percorsi fisici e source root consentite |
| `sources.py` | Lettura JSONL incrementale, fingerprint, messaggi consentiti, redazione euristica |
| `store.py` | Journal SQLite, checkpoint e stati; identità del vault associata alla directory di stato |
| `proposals.py` | Prove, revisioni, rendering conservativo e diff immutabile per la revisione |
| `publishing.py` | Lock per vault, intento persistente, verifiche e ripresa |
| `adapters.py` | Comandi pubblici di obsidian-wiki e refresh QMD separato |
| `retrieval.py` | Filtro del pack JSON: sole note, stato disputed esplicito, budget e copertura |
| `automation.py` | Baseline, acquisizione opt-in, pausa e singola continuazione Stop |
| `hooks.py` | Registrazione facoltativa di richieste, senza leggere il transcript |
| `cli.py` | Comandi manuali, output JSON, nessuna chiamata LLM |

## Acquisizione e stati

SQLite usa WAL e synchronous FULL. Checkpoint e job vengono scritti nella stessa transazione.
Il checkpoint rappresenta byte **acquisiti**, non conoscenza già approvata. I job preservano
questa distinzione: `queued → staged → publishing → published`, oppure `queued/staged → skipped`.
Un errore di pubblicazione lascia il job `publishing` con errore consultabile; un conflitto
prima del primo intento lascia `staged`. Una proposta modificata produce un nuovo review token.

Un input oltre il limite viene suddiviso su righe complete. Le code parziali non avanzano il
checkpoint. Un evento singolo troppo grande viene rifiutato. La riscrittura/troncamento del
prefisso già acquisito genera conflitto. Il costo di controllare il prefisso cresce con il
transcript: scelta conservativa iniziale; non viene promesso O(delta) per il fingerprint.

## Identità e prove

Identità della fonte: `agent:codex/<session-id>`. Identità del job: SHA-256 ridotto di fonte,
intervallo e byte. I messaggi acquisiti hanno un locator a byte. Il parser seleziona soltanto
`response_item` di tipo `message`, con ruolo user/assistant e canali visibili supportati.
Non acquisisce system/developer, reasoning, function outputs o token telemetry.

Gli estratti citati vengono pubblicati in `_raw/_archived/learning-brain/<job>.md`. Il vault
conserva gli estratti selezionati; la coda conserva il contesto visibile acquisito. Non vengono
copiate conversazioni intere nel vault. Il range originale viene ricontrollato prima della proposta
e prima della pubblicazione. Perciò una fonte locale non più disponibile blocca l'applicazione.

## Pubblicazione

Il token identifica l'intero bundle: note prima/dopo, revisioni, estratti e attività aperte.
Prima delle scritture si verificano tutti i target. Si persiste l'intento, poi si scrivono snapshot
e note con replace atomico per file e fsync. La ripresa accetta esclusivamente il vecchio contenuto
atteso o il contenuto esatto già approvato. Terminano il flusso manifest, todo e memory sync.

Il lock POSIX `.learning-brain.lock` coordina tutti i publisher Learning Brain dello stesso vault,
anche con directory di stato diverse. Non coordina editor e agenti esterni: il controllo della
revisione riduce il rischio ma non è un compare-and-swap atomico contro scrittori non cooperanti.
Per applicare proposte sullo stesso file, sospendere gli altri scrittori. Gli indici esterni hanno
lock propri; non tratteniamo i loro lock mentre invochiamo il CLI.

L'applicazione non fa rollback distruttivi di batch parziali. Una recovery persiste lo stesso
intento e completa le scritture mancanti. QMD viene aggiornato separatamente e non decide il
successo della pubblicazione. Nessun embedding o modello viene scaricato automaticamente.

## Scelte intenzionali della prima versione

- Una proposta integra contenuto in sezioni datate e conserva il corpo preesistente. Il
  consolidamento editoriale di note cresciute troppo sarà un workflow separato e revisionabile.
- Dalla 0.1.1 una correzione precede il testo storico nella nota. Il recall per argomento legge
  il pack JSON pubblico del CLI: esclude servizi e note archived, e per le disputed restituisce
  metadati/summary con una richiesta di lettura integrale anziché l'introduzione potenzialmente
  superata. Il recap operativo resta un percorso separato. Il filtro può ridurre la copertura
  rispetto al pack originario: i conteggi di esclusione e budget sono riportati esplicitamente.
- Le attività aperte vengono aggiunte con prove dirette dell'utente. Chiusura automatica e
  inferenza del profilo sono escluse.
- Il core usa il CLI di obsidian-wiki, ma non duplica le sue skill. Le skill del plugin descrivono
  soltanto come usarlo per questo workflow.
- Il processo LLM è la sessione agente corrente; nessun daemon e nessuna API key richiesta.
- QMD è opzionale e disattivato di default, finché le collezioni non separano fonti e wiki.

## Bootstrap Codex 0.1.2

Gli hook del plugin iniettano solo istruzioni delle skill: complete a SessionStart/SubagentStart,
un richiamo a UserPromptSubmit. Non chiamano il core, non leggono il vault e non acquisiscono
transcript. Restano distinti dal recorder facoltativo e dalla pubblicazione revisionata.

## Automazione opt-in 0.2.0

Il default resta off. Con `automation="review"`, SessionStart/UserPromptSubmit stabiliscono
una baseline per sessioni mai acquisite e iniettano routing e job pendenti (massimo dieci).
La baseline registra solo path/cursore/hash, senza copiare i messaggi storici; preserva eventuali
checkpoint manuali già esistenti. Se manca l'evento iniziale, il primo Stop crea la baseline e
segnala il gap anziché importare tutta la cronologia. Massimo 50 MB per la baseline automatica.

Stop acquisisce un intervallo limitato da max_capture_bytes. Solo se ci sono nuovi messaggi
supportati e job queued restituisce decision=block con una richiesta di debrief all'agente
corrente. Il turno viene marcato prima della risposta, e stop_hook_active impedisce ricorsione.
Il messaggio sintetico ha un prefisso riservato escluso dal parser delle prove user; le risposte
di manutenzione sono comunque dati non verificati e non vanno trasformate in conoscenza.
Una pausa per sessione impedisce ulteriori acquisizioni automatiche, preservando la coda esistente.

SessionEnd acquisisce soltanto se permission_mode è esplicito e non plan; se il client
lo omette non deduce il permesso e lascia il lavoro agli Stop. Non può avviare distillazione: i job restano queued per una ripresa.
Nessun hook avvia codex exec, un subagente o un daemon. Il core non pubblica mai da hook.
La selezione semantica, il recall pertinente e la produzione della proposta sono istruzioni
all'agente, non garanzie deterministiche. Bundle staged che toccano lo stesso target richiedono
una revisione prima di preparare l'aggiornamento concorrente; gli altri job restano queued.

Il bridge esegue il runtime registrato con argv, non shell; timeout core 8s (SessionEnd 2s),
bridge 10s e hook 15s (SessionEnd 3s). Errori/timeout lasciano un avviso e il percorso manuale;
non equivalgono a debrief riuscito. SQLite e i checkpoint rimangono transazionali. Il lock
locale dell'automazione serializza le invocazioni senza attendere altri hook concorrenti.

## Risposta finale preservata 0.3.0

La continuazione Stop della 0.2.0 è rimossa in ogni modalità: produceva un secondo messaggio
che copriva il risultato del task. Stop/SessionEnd ora acquisiscono soltanto e restituiscono {}.
Il bridge elimina anche eventuali decision/reason/systemMessage restituiti da un runtime
regredito; errori rimangono su stderr senza far ripartire l'agente o aggiungere una risposta.
Se manca l'avvio, Stop stabilisce la baseline silenziosamente.

UserPromptSubmit acquisisce al massimo un delta precedente prima di esporre i job pendenti.
Il routing include sessione e percorso verificato del transcript per consentire la capture
prima della risposta finale. In modalità autonomous la skill autorizzata dal proprietario
prepara, autorevisiona e pubblica una selezione limitata di note senza conferme ricorrenti.
In review prepara e chiede la revisione utente. Nessun hook chiama il publisher: l'azione
semantica e la sequenza propose/review/apply sono eseguite dall'agente corrente. Non esistono
scheduler o modelli nascosti in background. Se l'agente non completa il debrief prima della
risposta, il materiale rimane queued e può essere recuperato al prompt successivo.
