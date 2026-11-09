# ADR 0001 — Workflow locale con proposte revisionabili

Stato: adottata per alpha 0.1.0.

Il vault esistente è piccolo e usa obsidian-wiki, ma le istruzioni delle skill non sono uniformi.
Serve prima una catena verificabile, poi l'attivazione automatica.

Decisione: core Python 3.11+, SQLite locale, nessun servizio LLM aggiuntivo; dipendenza PyYAML
per leggere in sicurezza i metadati esistenti. Usare il CLI pubblico di obsidian-wiki e pin del
contratto supportato. Plugin Codex come confezione delle istruzioni; hook facoltativi per i soli
checkpoint. Ogni applicazione richiede una proposta concreta revisionata.

Alternative valutate:

- Scrittura diretta dal modello alla wiki: meno componenti, ma replay, conflitti e provenienza
  dipendono interamente dal prompt.
- Copia/fork delle 40 skill: amplia il costo di manutenzione e duplica i contratti.
- Daemon con chiamate LLM: utile in seguito, ma anticipa costi, credenziali e failure mode.
- Adozione integrale di Company Brain OS: introduce operatori e un secondo indice di memoria.

Da Company Brain OS riprendiamo debrief, stato compatto e preservazione della storia, senza
copiarne codice o imporne il flusso Git. Il template è orientato ai team; qui il target è personale.

Conseguenze: il ciclo iniziale richiede un agente e revisione umana. L'aggiornamento conservativo
può far crescere le note; misureremo quando introdurre consolidamento. Non promettiamo atomicità
globale o semantica exactly-once. Gli indici sono ricostruibili, le prove selezionate rimangono.
