# Modalità autonoma e risposta finale preservata — 0.3.0

## Problema e comportamento finale

La continuazione Stop della 0.2.0 aggiungeva un debrief dopo la risposta del task e le proposte
richiedevano conferme ricorrenti. La 0.3.0 elimina ogni decision=block da Stop, anche in review.
Stop acquisisce silenziosamente; UserPromptSubmit recupera eventuale delta precedente e job
pendenti. Il lavoro semantico si svolge prima della risposta finale dell'agente corrente.

Tre modalità: off (default distribuito), review (revisione utente), autonomous (delega esplicita
all'agente per normali note nel vault configurato). In autonomous la skill richiede propose,
lettura del diff/prove, autorevisione critica e apply dell'esatto token come agent:self-review,
senza domande per nota né risposte aggiuntive di manutenzione. Il reviewer rimane nel journal.
Non si eliminano controlli di revisione, fonti, lifecycle draft/disputed, conflitti o recovery.
Non si autorizzano profilazione inferita, chiusure task o push del vault.

## Verifiche

- 87 test unitari passati. Cinque nuovi casi coprono opt-in autonomo, separazione da review,
  recupero del precedente finale al nuovo prompt, soppressione di output tail anche se un
  runtime simulato restituisce block/systemMessage e assenza di messaggi UI su errore tail.
- 10/10 scenari meccanici sintetici preesistenti.
- Bridge/runtime effettivamente installati: 9 controlli in autonomous e 9 in review, su
  transcript e vault temporanei. Nessun modello avviato dai test.
- 15 controlli di qualità precedenti sul plugin installato passati.
- Ruff lint/format, controllo package e validazione delle due skill passati.
- API hooks/list: sette handler rilevati, abilitati, attualmente modified e quindi da rivedere
  nel client. Nessuna modifica alle approvazioni o bypass di trust.
- Runtime/plugin 0.3.0 installati. Configurazione personale impostata su autonomous con backup.
  Doctor conferma la delega configurata. Hash dei 36 file Markdown controllati nel vault
  personale invariati durante l'attivazione: nessuna pubblicazione personale eseguita nel test.

## Limiti e avvio

I test provano il protocollo, i meccanismi e l'assenza di continuazioni; non dimostrano che il
modello selezioni o autorevisioni sempre correttamente le note. L'autorevisione non è una
valutazione indipendente e non viene presentata come pilot umano completato. Se l'agente
non conclude la memoria prima del finale, il lavoro rimane queued per il prompt successivo.

La nuova policy delle skill richiede una nuova sessione/ricaricamento e la revisione dei soli
hook modificati imposta dal client. È distinta dalle conferme per ogni nota, rimosse in autonomous.
Il core aggiornato già non genera più continuazioni Stop per le invocazioni del vecchio bridge.
Resta da osservare nel client riaperto l'uso semantico autonomo della nuova policy.
