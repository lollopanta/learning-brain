# Audit delle integrazioni

Audit iniziale: 2026-11-07. Sono state censite le 40 skill distribuite con obsidian-wiki
2026.10.2 e approfondite le istruzioni/implementazioni dei percorsi usati dal workflow.

## Matrice delle responsabilità

| Gruppo | Skill | Uso previsto |
|---|---|---|
| Schema/config | llm-wiki, wiki-setup, wiki-switch | Convenzioni e configurazione, senza installazione implicita |
| Acquisizione | wiki-capture, wiki-ingest, wiki-update | Criteri di distillazione, mantenuti fuori dai meccanismi deterministici |
| Storia | wiki-history-ingest e codex/claude/copilot/hermes/openclaw/pi-history-ingest | Recupero delle fonti; v1 implementa soltanto Codex |
| Recall storico | wiki-agent, session-brain, session-search, memory-bridge | Consultazione mirata, non richiamata automaticamente dalla coda |
| Contesto | wiki-query, wiki-context-pack, wiki-narrate | Recap e context pack attraverso il CLI |
| Salute | wiki-status, wiki-lint, daily-update, impl-validator | Audit e verifica del risultato, senza eseguire fix generici |
| Organizzazione | tag-taxonomy, cross-linker, wiki-dedup, wiki-synthesize | Operazioni editoriali separate dal publisher |
| Ricerca/viste | wiki-research, wiki-dashboard, wiki-digest | Workflow indipendenti |
| Promozione | wiki-stage-commit | Riferimento per revisioni; il core mantiene il proprio journal del bundle |
| Trasferimento | wiki-export, wiki-import, wiki-rebuild | Backup/portabilità, fuori dal ciclo automatico |
| Procedure | code-understand, vault-skill-factory, skill-creator | Comprensione e produzione di skill su richiesta |
| Aspetto | graph-colorize, obsidian-layout-adjustment | Nessuna responsabilità nell'aggiornamento della memoria |

## Funzioni riutilizzate e verifica

- `cache-update <vault> <snapshot> --key <origin> --pages ...`: origine portabile.
- `cache-update <vault> <snapshot> --pages ...`: associazione snapshot → note.
- `memory todo add`: deduplicazione per testo; ripetere può aggiornare touched, non creare doppioni.
- `memory sync`: ricostruzione coordinata di indice e hot cache, con log separatamente deduplicato
  da operation_id. Dopo un crash la riconciliazione si ripete anche quando il log esiste già.
- `memory status --json`: prerequisito di adozione della superficie di memoria.
- `memory recap` e `context-pack`: consultazione limitata e in sola lettura.

`scripts/demo.py` usa il vero CLI e controlla anche i risultati con `lint`. La prima esecuzione
ha evidenziato che il parser del lint non legge le block list YAML senza indentazione. Il renderer
genera quindi liste indentate e title/summary folded: YAML genericamente valido non basta per
garantire interoperabilità con un consumer specifico.

L'adattatore richiede la release testata 2026.10.2 e fallisce esplicitamente sulle altre.
La matrice CI del core non installa obsidian-wiki; la verifica dell'adattatore reale è un test
separato e locale, senza dipendere dalla disponibilità del pacchetto su un registry.

## Incoerenze che non ereditiamo

- wiki-capture quick prescrive sia lo stop dopo `_raw/` sia, altrove, scritture profile/todo.
  Qui acquisizione, proposta e pubblicazione sono comandi diversi.
- wiki-agent contiene esempi con `confidence: high` e lifecycle stable, differenti dallo schema
  corrente. Qui la proposta ha uno schema esplicito e stati epistemici per claim.
- Alcune istruzioni del manifest usano ingested_at/pages_created, altre
  last_ingested/pages_produced. Qui il CLI possiede tutte le scritture al manifest.
- Lo script daily-update può dichiarare freschezza senza il campo globale last_updated;
  non lo usiamo come segnale che tutte le fonti siano elaborate.
- doctor controlla gli hook Claude; non lo usiamo per dichiarare funzionanti gli hook Codex.
- Cross-linker/dedup possono creare snapshot Git con add -A. Non vengono eseguiti automaticamente.
- Il lint tratta anche alcuni file di servizio come note; il suo stato aggregato non viene
  interpretato come verdetto sulla qualità semantica di un batch.
- La promozione staged esistente controlla revisioni ma non possiede il journal di un intero
  batch. Riutilizziamo le API della memoria; implementiamo qui l'intento di pubblicazione.

## Codex e Company Brain OS

Fonti ufficiali consultate per il packaging e il ciclo degli eventi:

- [Plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [Hooks](https://learn.chatgpt.com/docs/hooks)

Gli hook bundled sono una capacità di installazioni manuali supportate, non una garanzia per
ogni superficie cloud. Gli hook richiedono fiducia esplicita. SessionEnd ha un budget molto
ridotto; registra solo una richiesta. Il formato del transcript non è un'interfaccia stabile.

[Company Brain OS](https://github.com/marcogalluccio/company-brain-os) è utile per debrief,
preserve-first e stato operativo compatto. Il suo flusso multi-operatore e Git non viene importato.
Non viene creata una seconda memoria MEMORY.md parallela al vault.
