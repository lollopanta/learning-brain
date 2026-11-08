# Criteri di accettazione e stato della release

## Alpha 0.1 — workflow manuale

| Criterio | Evidenza richiesta |
|---|---|
| Replay senza duplicati tecnici | Test su acquisizione e pubblicazione ripetute |
| Sessioni ancora aperte | Append elaborata come nuovo intervallo; riga parziale conservata |
| Nessuna perdita silenziosa del checkpoint | JSON invalido, troncamento e riscrittura rifiutati |
| Prove esistenti | Quote esatta in messaggio acquisito; ruolo coerente con l'etichetta |
| Revisione concreta | Diff completo, estratti, thread e token del bundle |
| Protezione delle modifiche concorrenti | Base revision obbligatoria e conflitto prima dell'applicazione |
| Ripresa | Crash dopo snapshot/note e errore del CLI esterno; stato recuperabile |
| Interoperabilità reale | Demo con manifest, indice, snapshot, todo, log e lint |
| Isolamento | Stato esterno al vault, allowlist fonti, path traversal/symlink rifiutati |
| Privacy minima | Nessun contenuto reale in Git; system/developer/reasoning/tool output esclusi |
| Plugin | Manifest e skill verificati staticamente; hook di bootstrap skill; checkpoint di esempio non attivi |

Questi criteri sono esercitati dalla suite e dalla demo. I risultati locali, con comandi e limiti,
sono registrati in `evals/results/baseline.md`; la CI verifica solo gli ambienti che ha realmente eseguito.
La verifica aggiuntiva del plugin installato e i difetti corretti in alpha 0.1.1 sono descritti
in `evals/results/quality-2026-11-08.md`. Non sostituiscono il pilot umano.

## Gate prima della pubblicazione automatica sul vault personale

Pilot di almeno dieci sessioni rappresentative, con revisione umana e domande di recupero.
Soglie iniziali da mantenere fisse durante quel pilot:

- Zero claim non sostenuti accettati come verificati.
- Zero perdite/sovrascritture nei casi di interruzione e replay.
- Almeno 90% dei candidati proposti giudicati utili o necessari dal revisore.
- Almeno 80% degli elementi importanti del gold set conservati.
- Almeno 80% delle domande di recupero risolte correttamente con fonti adiacenti.
- Mediana di revisione entro tre minuti per sessione, esclusa la migrazione iniziale del vault.

Sono obiettivi progettuali, non misure già ottenute. Campione piccolo: riportare sempre conteggi
e denominatori, non soltanto percentuali. Se una soglia fallisce, correggere il problema e usare
un nuovo set di valutazione; non modificare il gold set per far passare il sistema.

## Stato e lavoro residuo

Implementati: core manuale, coda, proposte, open thread, recupero, adattatore, contesto e plugin
di skill, con bootstrap istruzioni dalla 0.1.2. Disponibile ma non installato: recorder hook di riferimenti. Nessuna pubblicazione
automatica è implementata o abilitata. Il recorder non trasforma un checkpoint in conoscenza.

Da validare con l'utente: pilot semantico reale e utilità del contesto in una nuova sessione;
caricamento del plugin e hook nella specifica superficie Codex usata. Da progettare soltanto
se serve: scheduler installabile, esecuzione LLM autonoma, artefatti runtime/test come fonti,
consolidamento editoriale, propagazione delle correzioni e portabilità Windows.

La replica di uno stesso fatto in chat, snapshot e nota non conta come tre prove indipendenti.
La prima versione non dichiara deduplicazione semantica automatica o atomicità multi-file.

## Preparazione automatica 0.2.0

Disponibili: acquisizione opt-in, baseline senza import storico, una continuazione Stop per turno,
pausa persistente per sessione e acquisizione SessionEnd senza modello. La pubblicazione resta
manuale e il gate semantico non è soddisfatto. La suite sintetica verifica le proprietà meccaniche;
la qualità delle proposte automatiche nelle sessioni reali resta da misurare.
