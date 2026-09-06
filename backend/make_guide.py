import os
from fpdf import FPDF

OUT = "/app/frontend/public/Guida_Gestionale_CambiaOra_RS.pdf"
MC = dict(new_x="LMARGIN", new_y="NEXT")
pdf = FPDF(format="A4", unit="mm")
pdf.set_auto_page_break(auto=True, margin=18)

def h1(t):
    pdf.set_font("helvetica", "B", 20)
    pdf.set_text_color(90, 20, 110)
    pdf.multi_cell(0, 12, t, **MC)
    pdf.set_draw_color(190, 40, 130)
    pdf.set_line_width(0.8)
    y = pdf.get_y()
    pdf.line(10, y, 200, y)
    pdf.set_xy(10, y + 3)
    pdf.set_text_color(30, 30, 30)

def h2(t):
    pdf.set_font("helvetica", "B", 13)
    pdf.set_text_color(30, 60, 160)
    pdf.multi_cell(0, 8, t, **MC)
    pdf.set_text_color(30, 30, 30)

def p(t):
    pdf.set_font("helvetica", "", 10.5)
    pdf.multi_cell(0, 5.5, t, **MC)
    pdf.ln(1)

def bullet(items):
    pdf.set_font("helvetica", "", 10.5)
    for it in items:
        pdf.set_x(12)
        pdf.multi_cell(185, 5.5, "- " + it, **MC)
    pdf.ln(1)

pdf.add_page()
pdf.ln(12)
if os.path.exists("/app/frontend/public/rs-logo.png"):
    pdf.image("/app/frontend/public/rs-logo.png", x=35, w=55)
if os.path.exists("/app/frontend/public/cambiaora-logo.jpg"):
    pdf.image("/app/frontend/public/cambiaora-logo.jpg", x=105, w=70)
pdf.set_xy(10, 118)
pdf.set_font("helvetica", "B", 24)
pdf.set_text_color(90, 20, 110)
pdf.multi_cell(0, 12, "Gestionale RS & CambiaOra", align="C", **MC)
pdf.set_font("helvetica", "I", 15)
pdf.multi_cell(0, 9, "Tutto sotto controllo", align="C", **MC)
pdf.ln(3)
pdf.set_font("helvetica", "", 12)
pdf.set_text_color(80, 80, 80)
pdf.multi_cell(0, 7, "Presentazione del progetto e guida completa alle funzioni", align="C", **MC)
pdf.multi_cell(0, 7, "Energia - Riparazioni - Telefonia - Magazzino - Ritiri usato - WhatsApp", align="C", **MC)
pdf.ln(6)
pdf.set_font("helvetica", "", 10)
pdf.multi_cell(0, 6, "Versione 1.0 - Giugno 2026 - Documento interno", align="C", **MC)

pdf.add_page()
h1("1. Presentazione del progetto")
p("Il gestionale e la piattaforma unica di RS Riparazioni e CambiaOra per amministrare tutti i negozi (Tirano, Sondalo, Sondrio, Sondrio Grosio, Gravedona, Morbegno e collaboratori esterni) da un solo punto. Sostituisce i fogli Google con un sistema condiviso, con permessi per ruolo e numerazione automatica dei documenti.")
h2("Cosa fa in sintesi")
bullet([
    "Anagrafica clienti unica: un cliente puo avere piu servizi (energia, riparazioni, telefonia) e il sistema riconosce i clienti Premium",
    "Energia: rinnovi a 10 mesi con alert automatici, importazione dai fogli Google, export Excel, PDF unificato delle bollette",
    "Riparazioni: stati di lavorazione, calcolo automatico del prezzo consigliato, scheda stampabile, ricambi scalati dal magazzino",
    "Telefonia: SIM, internet e linee fisse con tracciamento dei vincoli (es. 48 mesi) e report scadenze",
    "Magazzino: giacenze separate per negozio, visibilita incrociata, categoria rigenerati/usati con prezzo manuale",
    "Ritiri usato: bolla PDF con numerazione progressiva per negozio, pronta da firmare con documento del cliente",
    "WhatsApp: un numero per negozio, invio link privacy e richiesta recensione Google automatici",
])

h1("2. Accesso e ruoli")
p("Ogni utente accede con email e password. L'amministratore crea gli utenti dalla pagina Utenti, assegnando ruolo, negozi e sezioni visibili (Energia, Riparazioni, Telefonia).")
bullet([
    "Admin: vede e gestisce tutto, tutti i negozi, compensi e bollette",
    "Operatore: gestisce clienti e servizi su tutti i negozi, senza amministrazione",
    "Negozio: vede solo i clienti e i servizi del proprio negozio",
    "Tecnico: vede tutte le riparazioni (nessun filtro per negozio), niente telefonia/energia",
])

h1("3. Dashboard")
p("La prima pagina dopo il login. Mostra: clienti totali, rinnovi in scadenza, compensi da pagare, riparazioni attive, numeri WhatsApp connessi, e il pannello 'Scadenze della settimana' con tre colonne: rinnovi energia entro 7 giorni, vincoli telefonia in scadenza, riparazioni pronte da consegnare. Sotto, l'alert 'Magazzino sotto scorta' segnala gli articoli che stanno finendo. Ogni voce e cliccabile e porta alla pagina di competenza.")

h1("4. Clienti - inserimento e gestione")
h2("Inserimento")
p("Pagina Clienti > 'Nuovo cliente'. Obbligatori: nome, cognome, telefono. Il codice fiscale e consigliato (serve per bollette e ritiri usato). Si assegnano negozio e operatore. Per i clienti business: P.IVA al posto del CF.")
h2("Gestione")
bullet([
    "Ricerca per nome, telefono, CF; filtri per stato lavorazione, tipo bolletta, negozio",
    "Badge Premium automatico: Step 1 (1 categoria di servizi), Step 2 (2 categorie), Premium (energia + telefonia + riparazioni) - utile per sconti e accortezze",
    "Dalla scheda cliente: allegati (PDF/foto), PDF unificato, storico lavorazioni, invio link privacy WhatsApp",
    "La data di rinnovo energia si calcola automaticamente a 10 mesi dalla data contratto",
])

h1("5. Energia (luce/gas)")
p("I clienti energia sono gestiti dalla pagina Clienti. Stati lavorazione: da contattare, contattato, interessato, rinnovato, non interessato, ecc. Gli alert in dashboard segnalano i rinnovi imminenti e quelli passati non gestiti. Il pulsante Export genera l'Excel; 'PDF unificato' unisce le bollette del cliente.")

h1("6. Riparazioni - inserimento e gestione")
h2("Inserimento")
p("Pagina Riparazioni > 'Nuova riparazione'. Si sceglie il cliente (o si crea al volo), il negozio, il dispositivo e il problema. Campi utili: codice sblocco (simbolo/PIN/password), email e password account dispositivo (Google/Apple ID), operazioni svolte. Se serve un ricambio da ordinare, attivare 'Richiede ricambio' e inserire costo componente e minuti di lavoro: il sistema calcola il prezzo consigliato IVA inclusa.")
h2("Gestione")
bullet([
    "Numero riparazione automatico per negozio (es. RM109 = Riparazione Morbegno 109) - distinto dai numeri dei ritiri",
    "Stati: Ingresso, Attesa ricambio (col cliente / in carico), In attesa cliente, Preventivo, In lavorazione, Pronto, Consegnato",
    "Dal dettaglio: assegnare ricambi dal magazzino (la giacenza scala da sola; se il pezzo e in un altro negozio il sistema lo segnala), scaricare la Scheda riparazione PDF da far firmare",
    "Ricambi 'Rigenerati/Usati': il prezzo si inserisce a mano al momento dell'uso",
])

h1("7. Telefonia (SIM, Internet, Fisso)")
p("Pagina Telefonia > 'Nuovo servizio': tipo (SIM/internet/fisso), operatore, numero, ICCID per le SIM, data attivazione, vincolo in mesi (es. 48), importo mensile. Per internet e linea fissa e presente il flag 'Cliente contattato'. Il tab 'Vincoli' mostra le scadenze con i giorni rimanenti, cosi si ricontatta il cliente prima che scada il vincolo.")

h1("8. Magazzino")
h2("Inserimento")
p("Pagina Magazzino > 'Nuovo articolo': nome (es. 'Display iPhone 13'), categoria (Display, Ricambi, Accessori, SIM, Rigenerati/Usati, Altro), negozio, giacenza, prezzi di acquisto e vendita.")
h2("Gestione")
bullet([
    "Ogni negozio ha la SUA giacenza: l'inventario e per negozio, l'admin vede tutto",
    "Pulsanti + e - sulla riga per carico/scarico rapido (es. vendita accessori al banco)",
    "Quando un ricambio viene usato in una riparazione, la giacenza scala automaticamente",
    "Le giacenze basse (0-2 pezzi) compaiono nell'alert 'sotto scorta' della Dashboard",
    "Export Excel completo con il pulsante in alto (utile per l'inventario fiscale)",
])

h1("9. Ritiri usato")
h2("Inserimento")
p("Pagina Ritiri usato > 'Nuovo ritiro': scegliere il negozio, cercare il cliente in anagrafica (si compilano da soli nome, cognome e CF) oppure digitarli a mano, poi articolo, IMEI, prezzo di ritiro, numero del documento (carta d'identita) e numero di allegati.")
h2("Gestione")
bullet([
    "Il sistema genera la bolla PDF pronta da stampare e firmare, con numerazione progressiva per negozio che prosegue i fogli esistenti (Morbegno M8, Sondrio SO7, Gravedona G3, Tirano T1, Sondalo SA1, Grosio GR1)",
    "Le bolle restano archiviate e riscaricabili dalla tabella (icona download)",
    "Le numerazioni dei ritiri (M, SO, G...) sono SEPARATE da quelle delle riparazioni (RM, RSO, RG...) per non confondersi",
    "Export Excel dell'intero registro con il pulsante in alto",
])

h1("10. WhatsApp multi-numero")
p("Pagina WhatsApp: una card per negozio piu la card 'Principale (fallback)'. Ogni numero si collega UNA VOLTA con QR o con codice numerico (consigliato: 'Genera codice', poi sul telefono WhatsApp > Dispositivi collegati > Collega con numero di telefono). La sessione resta salvata sul server.")
bullet([
    "I messaggi partono dal numero DEL NEGOZIO del cliente; se quel numero non e collegato, parte il Principale",
    "Dalla scheda cliente: 'Invia link privacy' manda il messaggio con il link del modulo; dopo 5 minuti parte in automatico la richiesta di recensione Google del negozio giusto",
    "Se un numero risulta 'Non connesso', ricollegarlo dalla sua card",
    "La sezione 'Ultimi invii' in fondo alla pagina mostra il registro dei messaggi (inviati/falliti, numero, negozio, ora)",
])

h1("11. Negozi, Operatori, Utenti")
p("Pagine riservate all'admin. Negozi: anagrafica punti vendita e link recensione Google (usato dai messaggi WhatsApp). Operatori: venditori con percentuale compenso. Utenti: account di accesso con ruolo, negozi assegnati e sezioni visibili. La pagina Compensi calcola le provvigioni per negozio e operatore.")

h1("12. Consigli operativi")
bullet([
    "Mattina: aprire la Dashboard e controllare 'Scadenze della settimana' e 'Magazzino sotto scorta'",
    "Ogni riparazione: compilare subito codice sblocco e account del dispositivo, prima di iniziare il lavoro",
    "Quando arriva un ricambio: caricarlo in Magazzino (+), cosi le giacenze sono sempre vere",
    "Dopo ogni consegna: stato 'Consegnato' + invio link privacy (la recensione parte da sola)",
    "Ritiri usato: generare la bolla SEMPRE dal gestionale, mai a mano, cosi la numerazione resta ordinata",
])

pdf.output(OUT)
print("PDF OK:", OUT, os.path.getsize(OUT), "bytes,", pdf.page_no(), "pagine")
