# Correzione discovery — 0.1.3

## Difetto riprodotto

Codex CLI 0.167.0: plugin/read mostra le due skill, ma hooks vuoto; hooks/list non
restituisce nessun hook Learning Brain. La 0.1.2 usava root plugin.json nel formato
AgentPlugin. Dichiarare esplicitamente extensions.com.openai.hooks e aggiungere un overlay
senza rimuovere root plugin.json non risolve il problema.

La causa è verificata nel codice della release rust-v0.167.0:
https://github.com/openai/codex/blob/rust-v0.167.0/codex-rs/core-plugins/src/loader.rs
Il loader restituisce hook_sources vuoto quando format == PluginManifestFormat::AgentPlugin.
La documentazione web corrente descrive funzionalità più ampie della release locale.

## Correzione e verifica

Il pacchetto usa solo .codex-plugin/plugin.json, con hooks e skills espliciti.
Root plugin.json rimosso: altrimenti avrebbe precedenza. Versione 0.1.3 installata, cache
verificata senza manifest portabile. Runtime aggiornato separatamente.

hooks/list del vero app-server locale ora restituisce esattamente:
- sessionStart: enabled=true, trustStatus=untrusted
- userPromptSubmit: enabled=true, trustStatus=untrusted
- subagentStart: enabled=true, trustStatus=untrusted

pluginId è learning-brain@learning-brain-local. Nessun errore o warning di caricamento
nell'esperimento prima/dopo. Non è stato avviato un modello o alterato lo stato di trust.
I tre comandi della cache installata producono il JSON atteso. 66 test unitari, 10/10 scenari
meccanici sintetici, Ruff e controllo package passati.

scripts/check_codex_discovery.py rende riproducibile il controllo della discovery dopo
installazione. scripts/check_package.py impedisce di reintrodurre root plugin.json.
La CI standard esegue il controllo statico; quello del vero runtime Codex è locale e richiede
il plugin installato, non viene dichiarato coperto dai runner CI senza Codex.

## Limite rimanente

Discovery confermata non equivale a esecuzione automatica: il client aperto deve ricaricare
il plugin aggiornato e l'utente deve rivedere i tre hook ora rilevabili. La verifica della
consegna del contesto nella sessione utente resta successiva al trust. Nessun salvataggio
automatico abilitato, nessun contenuto personale o configurazione di trust inserito in Git.
