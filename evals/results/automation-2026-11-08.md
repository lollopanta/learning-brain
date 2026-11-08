# Automazione revisionata — alpha 0.2.0

## Comportamento

Opt-in automation="review": il runtime acquisisce delta a Stop e può chiedere una sola
continuazione all'agente corrente per preparare proposte. Il richiamo pertinente delle note
è guidato dalla skill; non è una ricerca forzata su ogni prompt. Non avvia codex exec,
subagenti, servizi esterni o scheduler. La pubblicazione richiede ancora revisione del bundle.

Baseline di una sessione mai acquisita: solo cursore/hash, senza import storico. Eventuali
checkpoint manuali sono preservati. Plan, subagenti, Stop ricorsivi e sessioni escluse non
acquisiscono automaticamente. automation-pause esclude una sessione e conserva i job già
presenti. SessionEnd senza permission_mode esplicito non acquisisce: i client possono omettere
questo campo. Gli Stop ordinari costituiscono il percorso principale.

La richiesta sintetica di manutenzione usa un prefisso riservato escluso dalle prove user.
I job senza utilità possono essere skipped. Target già toccati da un bundle staged richiedono
risoluzione della revisione prima di preparare aggiornamenti concorrenti: è una regola della
skill, non una garanzia automatica di deduplicazione semantica. La coda non equivale a memoria
pubblicata. Gli errori di hook vengono segnalati senza bloccare il normale lavoro dell'utente.

## Verifiche eseguite

- 81 test unitari passati, inclusi 15 nuovi casi di automazione: baseline, delta, staging reale
  di una proposta, zero scritture al vault, guard di ricorsione/turno, plan, pausa, identità,
  sorgenti riscritte, coda parziale, SessionEnd senza permesso e richiesta sintetica esclusa.
- 10/10 scenari sintetici meccanici preesistenti.
- 8 verifiche tramite bridge/launcher/runtime realmente installati, con sessioni sintetiche,
  configurazione isolata e vault temporaneo (scripts/check_automation.py).
- 15 verifiche di qualità preesistenti tramite plugin installato, tutte passate.
- Ruff lint/format, package check e validazione delle due skill passati.
- hooks/list del vero Codex rileva sette handler su cinque eventi, abilitati. Quelli modificati
  o nuovi richiedono revisione del trust: non è stato modificato il database delle approvazioni.
- Runtime/plugin 0.2.0 installati; configurazione personale impostata a review con backup.
  Baseline della sessione corrente stabilita senza acquisire la cronologia.
- Hash dei 34 file Markdown/manifest controllati nel vault personale invariati.

## Limiti della misura

Le prove del bridge non eseguono un modello: dimostrano acquisizione, protocollo di continuazione,
limiti e isolamento. La selezione semantica automatica, l'effettiva consegna della continuazione
nel client riaperto e il tempo di revisione restano da misurare dopo trust dei nuovi hook.
Nessun risultato sintetico è presentato come pilot indipendente su sessioni reali.
Una citazione esatta non garantisce una sintesi corretta. Nessuna pubblicazione autonoma,
chiusura automatica dei task o inferenza del profilo è stata abilitata.

## Riscontro dal client dopo il riavvio

Consegna del contesto SessionStart/UserPromptSubmit osservata e sette handler trusted.
La continuazione Stop è stata ricevuta davvero; il debrief ha elaborato e scartato intervalli
contenenti solo manutenzione, senza pubblicare note. Non è un pilot semantico rappresentativo.

È emersa una differenza rispetto alla fixture iniziale: Codex avvolge il prompt sintetico in
<hook_prompt ...>, quindi il solo startswith del marker non lo escludeva dal messaggio user.
Il parser ora riconosce anche l'involucro. Un test di regressione verifica che escluda il prompt
automatico preservando un autentico messaggio utente adiacente. Suite aggiornata: 82 test.
La correzione è nel core Python, reinstallato localmente; file del plugin e definizioni hook
restano invariati, senza richiedere un nuovo trust o riavvio.
