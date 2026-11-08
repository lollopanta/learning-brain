# Operazioni e recupero

## Preparazione del vault

Usare prima `doctor`. Se obsidian-wiki segnala una memoria non adottata, esaminare
`obsidian-wiki memory migrate --vault <vault>` in preview, poi applicare la migrazione soltanto
nel vault previsto. La creazione di una directory `_staging/` non abilita staged writes.
Il nostro staging è nel journal esterno: non serve cambiare WIKI_STAGED_WRITES.

Il template è copiabile in un vault nuovo. Non sovrapporlo al vault personale. Nessun comando
learning-brain modifica la struttura del vault come parte di doctor, capture, propose o review.
`apply` crea il suo lock e pubblica solo il bundle approvato.

## Riconciliazione iniziale del vault esistente

Prima di abilitare gli hook, preparare un piano separato per: identità repository e checkout,
fonti generiche senza locator, corrispondenza snapshot/manifest, eventuale tassonomia e collezioni QMD.
Un vecchio percorso assente è unavailable, non prova che il progetto sia stato cancellato.
Non alzare confidence per riparare i metadati. Non normalizzare automaticamente tutti i warning
del lint: distinguere note e file di servizio.

## Stato e fallimenti

| Stato | Operazione consentita |
|---|---|
| queued | inspect, propose, skip |
| staged | review, nuova proposta contro la revisione corrente, apply, skip |
| publishing | review e ripresa dello stesso bundle; nessuna sostituzione della proposta |
| published | replay innocuo; nuova conoscenza richiede un nuovo intervallo |
| skipped | terminale, con ragione; non viene riproposto silenziosamente |

Se `apply` fallisce prima dell'intento, nessuna nota/snapshot è stata scritta. Se è publishing,
alcuni file potrebbero essere già arrivati: non cancellarli. `recover` elenca i job interrotti;
`review` mostra il bundle. Ripetere apply con token e reviewer originali.

Se una nota già parzialmente pubblicata è stata modificata da un editor, fermare gli altri
scrittori, conservare una copia della loro versione fuori dal target e confrontarla con il diff
originale. La ripresa accetta solo base o risultato approvato. Una riconciliazione manuale deve
riportare i target a uno di questi stati con il consenso del proprietario, poi completare il job
e proporre separatamente le modifiche conservate. Non usare reset --hard, non editare SQLite
per dichiarare un successo, non forzare il nuovo hash nel vecchio bundle.

Il lock è advisory: applicazioni esterne non sono coordinate. La prima versione richiede una
finestra di scrittura esclusiva per le note toccate. Un batch non è atomico fra tutti i file.

L'aggiornamento a 0.1.1 non modifica i byte di bundle già approvati. Se una correzione era ancora
staged nella 0.1.0, prepararla e revisionarla di nuovo per usare il nuovo layout. Per un job già
publishing vale la ripresa dello stesso intento, senza cambiare il token. Il recall 0.1.1 protegge
anche le vecchie note disputed, ma non riscrive in massa le note già pubblicate.

## Hook e recupero dei checkpoint

`hooks.py` registra solo percorso/id sessione e turno. Il file di richiesta è scritto in modo
atomico e deduplicato per envelope. `drain` elabora una porzione limitata per richiesta; ripetere
finché i riferimenti sono stati acquisiti. Richieste fallite rimangono e sono segnalate. Un tail
parziale non viene perso: se resta oltre l'offset, la richiesta deve essere mantenuta.

Nessuno scheduler è installato. Eseguire drain manualmente durante il pilot. I checkpoint sono
un'accelerazione: una riconciliazione periodica può chiamare capture su ogni rollout consentito,
senza usare l'mtime come prova di già elaborato. La scansione di una sessione riscritta fallisce
esplicitamente e richiede un'analisi, non una cancellazione del checkpoint.

## Ricerca e backup

QMD è opt-in; verificare prima che la collezione wiki escluda raw, staging, archivi, metadati e
file derivati, oppure predisporre una directory proiettata con sole note finali. `qmd update`
non promette che tutti gli embedding siano aggiornati. Eseguire embed esplicitamente quando serve.
Un errore di ricerca non fa rollback delle note. Evitare refresh per ogni singola nota.

Backup del vault con il normale strumento dell'utente. Per lo stato SQLite, fermare il processo
e usare l'API SQLite backup oppure copiare DB/WAL/SHM in modo coerente; copiare solo queue.sqlite
durante una scrittura non è un backup garantito. La perdita dello stato non va risolta
riacquisendo e pubblicando automaticamente tutte le fonti: serve riconciliare con il vault.

Disinstallazione: rimuovere il plugin/hook dalla sorgente in cui è stato installato, preservando
gli altri hook. Conservare vault e stato. La rimozione del software non cancella la memoria.
