# Baseline tecnica — alpha 0.1.0

Data: 2026-11-07. Ambiente locale: macOS, Python 3.11.17; adattatore reale
obsidian-wiki 2026.10.2. Nessuna sessione reale è stata pubblicata nel vault.

| Verifica | Risultato |
|---|---|
| Suite unittest | 47 test superati |
| Matrice meccanica sintetica | 10/10 scenari, 20 test selezionati dalla suite |
| Integrazione con obsidian-wiki reale | Pass, vault temporaneo con dati sintetici |
| Ruff lint e format | Pass |
| Validazione statica del plugin | Pass, due skill, hook non attivi |
| Skill Creator quick_validate | Entrambe le skill valide |
| Compatibilità locale delle dipendenze | pip check senza errori |
| Doctor sul vault configurato | Memoria adottata e release supportata; sola lettura |
| Audit formato delle sessioni locali | 13/13 header session_meta con id; envelope testuali supportati |
| Pilot umano sulla qualità delle note | Non eseguito |
| Installazione/caricamento nel client Codex | Non eseguita |
| CI macOS/Linux e Python 3.11/3.13 | Configurata; riportare l'esito GitHub effettivo separatamente |

La demo verifica acquisizione, staging, diff, applicazione, replay, delta di fonte, manifest
con origine e snapshot, indice, todo, log senza doppioni, protezione di una modifica concorrente,
snapshot coerenti e link risolti. La suite verifica anche l'uscita improvvisa di un processo
subordinato: lock rilasciato dal kernel e intento ripreso da SQLite dopo il riavvio.

L'audit delle sessioni ha contato strutture senza salvare testo o identificatori in Git. Questo
non misura comprensione semantica, completezza della memoria, precisione dei candidati o qualità
del recall. Le metriche semantiche restano N/A, non 100% sulla base dei test sintetici.

Limiti osservati: contratto del CLI vincolato a una release; due incompatibilità del parser
frontmatter risolte con block list indentate e snapshot scalari non spezzati su più righe.
Gli avvisi generali del lint su file di servizio non vengono mascherati da un PASS semantico.

Per riprodurre i risultati usare i comandi della sezione Verifiche nel README. Per valutare
la qualità della conoscenza seguire `evals/pilot.md` su una copia del vault, con revisione umana.
