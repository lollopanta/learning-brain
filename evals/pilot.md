# Pilot semantico con sessioni reali

Stato: non eseguito. L'esecuzione delle fixture non sostituisce questo pilot.

Selezionare almeno dieci sessioni con varietà: debugging risolto, tentativo fallito,
decisione, ricerca, correzione, sessione senza risultati, sessione ripresa, lavoro operativo,
argomento già coperto, sessione con ipotesi ancora aperte. Tenere transcript e risultati reali
fuori dalla repository, in una directory locale non sincronizzata, usando una copia del vault.

Prima di generare proposte, il revisore annota il gold set degli elementi importanti, cosa è
decisione/proposta/risultato, quali affermazioni sono smentite e quali non vanno salvate. Il modello
che produce le proposte non deve vedere le risposte attese. Registrare il punto di partenza del
vault e preparare domande di recall che richiedano le nuove informazioni.

Per ogni sessione misurare:

| Campo | Misura |
|---|---|
| Precisione candidati | Elementi utili proposti / elementi proposti |
| Copertura | Elementi importanti conservati / elementi importanti del gold set |
| Claim non sostenuti | Conteggio e stato con cui sarebbero stati pubblicati |
| Duplicati semantici | Note/claim ripetuti senza nuovo contenuto |
| Revisione | Secondi per leggere proposta, prove e decidere |
| Recall | Risposte corrette con fonti / domande, in una sessione nuova |
| Correzioni | Claim obsoleti recuperati senza mostrare la smentita |

Separare falsi positivi di selezione, errori di supporto e omissioni. Non assegnare uno score
unico che nasconda perdite di dati. Non trasformare la classificazione del modello in giudizio
umano. Una sessione senza elementi importanti ha copertura N/A, non 100% inventato.

Le soglie sono in docs/acceptance-criteria.md. Una volta iniziato il pilot non cambiarle per
farlo passare. Pubblicare in Git soltanto conteggi aggregati e limiti; mai quote, nomi di clienti,
token, percorsi privati o conversazioni. Lasciare gli hook disattivati finché il gate non passa.
