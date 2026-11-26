# garden_irrigation v2 — specifica (bozza da approvare)

Riscrittura pulita dell'integrazione. Stesso dominio `garden_irrigation`,
nessuna migrazione dei dati v1: si riparte da zero e il deficit iniziale si
imposta a mano (vedi §8).

Stato: **bozza**. I punti marcati ❓ aspettano una decisione.

---

## 1. Obiettivo e perimetro

- Supporto decisionale all'irrigazione con bilancio idrico giornaliero
  **FAO-56** (ET0 Penman-Monteith, ETc = ET0 × Kc, TAW/RAW, pioggia efficace).
- Zone in numero libero, ciascuna una **subentry** dell'integrazione.
- Pensata per essere **condivisibile via HACS**: nessun nome di marca nel
  codice, unità convertite automaticamente, testi in inglese (base) + italiano.
- **v2.0 non comanda hardware.** Consiglia e registra. L'architettura lascia
  un punto d'aggancio per una futura lettura/comando di entità `valve`
  (vedi §11), ma non lo implementa.
- Nessuna notifica inviata. Problemi di configurazione/dati → **Repairs**.

## 2. Versioni

| | Minimo | Testato in CI |
|---|---|---|
| Home Assistant | **2026.2.0** | 2026.2.x (Python 3.13) e ultima stabile (Python 3.14) |
| Python | 3.13 | 3.13, 3.14 |

Motivo: le subentry con riconfigurazione e `statistics_during_period` con
conversione di unità sono già presenti in 2026.2 (verificato sulla versione
installata nel venv). Un minimo più basso allarga il pubblico HACS.

## 3. Struttura del codice

```
custom_components/garden_irrigation/
  __init__.py          setup/unload, registrazione servizi
  manifest.json        dependencies: recorder
  const.py             solo costanti condivise, niente storia
  config_flow.py       entry principale + subentry "zone" + options
  coordinator.py       orchestrazione: job giornaliero, recupero giorni mancanti
  daily_weather.py     legge le statistiche orarie del recorder → giorno meteo
  forecast.py          (opzionale) pioggia prevista da un'entità weather
  store.py             UN solo Store versionato
  services.py          record_irrigation, set_deficit
  repairs.py
  diagnostics.py
  entity.py / sensor.py / binary_sensor.py
  model/               Python puro, nessun import di Home Assistant
    fao56.py           ET0 Penman-Monteith (+ Hargreaves opzionale)
    soils.py           tabella terreni FAO-56 (AWC, blocco max)
    crops.py           profili Kc mensili, p
    balance.py         passo giornaliero del bilancio (funzione pura)
    recommendation.py  consiglio (funzione pura)
```

Regola: tutto ciò che è agronomia/calcolo sta in `model/`, è puro e testato
con vettori di riferimento. Il resto è "colla" con Home Assistant.

## 4. Dati meteo giornalieri — ❓ decisione

**Proposta:** non più accumulatori locali. Ogni mattina l'integrazione chiede
al recorder le **statistiche orarie** (mean/min/max, e `change` per la pioggia)
del giorno precedente, con una sola query limitata.

| Grandezza FAO-56 | Da statistiche orarie |
|---|---|
| Tmax / Tmin | max dei max / min dei min |
| RHmax / RHmin | max dei max / min dei min |
| Rs (MJ/m²/giorno) | media delle medie W/m² × 0,0864 |
| u2 | media velocità vento, riportata a 2 m (eq. 47) |
| Pressione | media (fallback: da quota, eq. 7) |
| Pioggia | `change` del sensore pioggia nel giorno |

Vantaggi: elimina ~600 righe di accumulatori e logica di reset pioggia;
permette di **recuperare i giorni persi** se HA era spento; le unità le
converte il recorder (`units=`).

Requisiti/limiti:
- i sensori devono avere `state_class` (`measurement`, pioggia
  `total_increasing`/`total`). Il config flow lo verifica.
- se una sorgente ha meno di 20 ore di statistiche nel giorno → giorno
  **incompleto** (Repair + avviso, nessun valore inventato):
  - mancano dati per l'ET0 → ET0 `unknown`; il bilancio del giorno viene
    applicato **senza ETc** (solo pioggia efficace e irrigazione) e il giorno
    è marcato incompleto (deciso il 26/11/2026);
  - pioggia incompleta → si usa la pioggia delle ore disponibili, giorno
    marcato incompleto.
- dipende dalla retention delle statistiche a lungo termine (illimitata di
  default in HA).

Approvato il 26/11/2026 (sostituisce gli accumulatori locali della v1).

## 5. Configurazione

### 5.1 Entry principale (config flow)
- Sensori: temperatura, umidità, radiazione solare, velocità vento, pioggia
  giornaliera (obbligatori); pressione (opzionale).
- Altezza anemometro (default 2 m). Latitudine e quota da HA (modificabili).

### 5.2 Subentry "zona"
- Nome, superficie (m²).
- Coltura: profilo Kc (default "prato microtermo / festuca", vedi §6.2) o
  personalizzato (12 valori mensili).
- Terreno: menu FAO-56 (§6.1) oppure AWC personalizzato (mm/m).
- Profondità radicale (default 150 mm), frazione p (default 0,40).
- **Intensità di irrigazione per fonte** (mm/min): rete, cisterna. Ognuna
  opzionale; almeno una obbligatoria (vedi §7.1).
- Sensore umidità suolo (opzionale) + soglie secco/umido (§9).

### 5.3 Opzioni (modificabili in ogni momento)
- Pioggia efficace: fattore (0,8) e soglia minima (2 mm).
- Ora del calcolo giornaliero (05:30).
- Hargreaves come fallback se mancano radiazione/vento: **spento**.
- Entità `weather` per pioggia prevista: **nessuna** (disattivato).
- Avvisi: intervallo minimo, tetto settimanale, blocco massimo (§10).

## 6. Modello agronomico

### 6.1 Terreni (FAO-56, tab. 19 — valore centrale di θFC−θWP)

| Terreno | AWC mm/m | Blocco max suggerito (mm) |
|---|---|---|
| Sabbioso | 80 | 12 |
| Sabbioso-franco | 90 | 10 |
| Franco-sabbioso | 130 | 8 |
| Franco | 155 | 6 |
| Franco-limoso | 160 | 6 |
| Limoso | 180 | 5 |
| Franco-limoso-argilloso | 155 | 5 |
| Limoso-argilloso | 160 | 4 |
| Argilloso | 160 | 4 |

Nota: la v1 usa AWC = 200 mm/m, sopra qualsiasi valore FAO: sovrastima la
riserva del suolo. I "blocchi max" sono indicazioni pratiche da validare, non
valori FAO.

### 6.2 Kc mensile di default (prato microtermo)

FAO-56 tab. 12 dà Kc ≈ 0,90–0,95 per prato microtermo in piena crescita.
Default proposto (modificabile, da validare sul campo):

| Gen | Feb | Mar | Apr | Mag | Giu | Lug | Ago | Set | Ott | Nov | Dic |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0,70 | 0,70 | 0,80 | 0,95 | 0,95 | 0,95 | 0,95 | 0,95 | 0,95 | 0,80 | 0,70 | 0,70 |

Frazione p: 0,40 (FAO-56 tab. 22, prato microtermo). Correzione opzionale
p = p_tab + 0,04 × (5 − ETc) (FAO-56 §8), spenta di default.

### 6.3 Bilancio giornaliero (invariato nella sostanza)
```
ETc       = ET0 × Kc(mese)
TAW       = (Zr/1000) × AWC          RAW = p × TAW
pioggia_e = 0                         se pioggia < soglia
          = min(pioggia × fattore, deficit_prec + ETc)   altrimenti
deficit   = clamp(deficit_prec + ETc − pioggia_e − irrigazione, 0, TAW)
```
- Applicato una volta per giorno chiuso, idempotente (`last_balance_date`),
  con recupero in ordine dei giorni mancanti.
- **Deficit attuale** mostrato = deficit di ieri − irrigazioni registrate oggi
  (così, dopo aver registrato, il consiglio scende subito).

## 7. Consiglio per zona

- "Da irrigare" se deficit attuale ≥ RAW.
- Quantità consigliata = deficit attuale (riporta a capacità di campo).
- Per ogni fonte configurata: minuti = mm / intensità_fonte, litri stimati =
  mm × superficie. Sempre etichettati come **stime**.
- Divisione in blocchi (ciclo-e-pausa) se mm > blocco max del terreno.
- Ogni consiglio ha un elenco di **motivi** e **avvisi** leggibili.

### 7.1 Due fonti con intensità diverse
Ogni zona ha un'intensità per fonte, misurata con la prova dei barattoli
(o, per la rete, litri al contatore ÷ superficie ÷ minuti). Il consiglio
mostra i minuti per entrambe; quando registri scegli la fonte usata e i
millimetri vengono calcolati con l'intensità di quella fonte. Se una fonte
non è misurata, per quella non si mostrano minuti.

## 8. Impostare il deficit a mano (avvio)

Servizio `garden_irrigation.set_deficit` (zona, mm) e scorciatoia "terreno a
capacità di campo" (deficit = 0).

Come stimarlo:
1. **Caso semplice (consigliato):** parti il giorno dopo una pioggia
   abbondante (> TAW, es. > 25 mm) o un'irrigazione profonda → deficit = 0.
2. **Stima:** dal giorno dell'ultima "bagnata" completa, somma per ogni giorno
   ETc − pioggia efficace − irrigazione, senza scendere sotto 0 né superare
   TAW. Esempio con TAW = 23 mm: 3 giorni a ETc 4 mm, nessuna pioggia →
   deficit ≈ 12 mm.
3. **Indizio dal prato:** impronte che restano, colore grigio-bluastro →
   sei intorno o oltre RAW.

## 9. Sensore umidità suolo (es. WH51)

La percentuale di questi sensori **non** è umidità volumetrica: dipende dal
sensore e da come è interrato. Uso in v2:
- **Diagnostico:** entità "Sensore umidità suolo" per zona con stato
  secco / tra le soglie / umido / soglie non impostate / non aggiornato
  (> 6 h senza letture) / non disponibile; valore e ultimo aggiornamento
  negli attributi. Batteria e segnale restano sul dispositivo del sensore.
- **Conferma (soft):** l'utente imposta per zona due soglie *sue* (secco /
  umido) guardando il sensore nel tempo. Se il modello dice "irriga" ma il
  sensore è sopra "umido" → avviso "il sensore indica terreno umido,
  verifica". Viceversa se il modello dice "non serve" e il sensore è sotto
  "secco". **Non cambia mai i numeri** del bilancio né blocca il consiglio.
- Niente apprendimento automatico di 14 giorni: senza soglie impostate, il
  sensore resta solo diagnostico.

### 9.1 Come tarare le soglie — esempio reale

26/11/2026: pioggia di **67 mm** (≈ 3 × TAW). Letture WH51 lo stesso giorno:

| Zona | Lettura il giorno della pioggia | Significato |
|---|---|---|
| Zona piccola | 75 % | **saturo** (valore massimo atteso) |
| Zona grande | 78 % | **saturo** (valore massimo atteso) |

Procedura (le letture sono nello storico delle entità di HA):
1. **+24/48 h**, quando la discesa rallenta → valore a **capacità di campo**.
   Soglia "umido" = poco sotto questo valore.
2. **Giorni seguenti senza pioggia** → osservare la velocità di discesa.
3. **Primi segni di stress** del prato (impronte che restano, colore
   grigio-bluastro) → soglia "secco".

Le soglie sono **per zona**: i 3 punti di differenza tra le due zone sono la
normale variabilità tra sensori. Questo stesso evento è anche il punto di
partenza ideale per il bilancio v2: deficit = 0.

## 10. Limiti → avvisi (non vincoli)

| v1 | v2 proposta | Perché |
|---|---|---|
| max 15 min per ciclo | **blocco max in mm** dal terreno + pausa 30 min | i minuti dipendono dalla fonte; ciò che conta è quanta acqua il terreno assorbe prima di ruscellare |
| ≥ 48 h tra irrigazioni (vincolo) | avviso, default 48 h | con la logica deficit ≥ RAW l'intervallo nasce da sé |
| ≤ 30 mm/7 gg (vincolo) | avviso opzionale, **spento** di default | a luglio ETc ≈ 6 × 0,95 × 7 ≈ 40 mm/settimana: un tetto a 30 fa sotto-irrigare |

## 11. Futuro: valvole (fuori da v2.0)

Gancio previsto ma non implementato: per zona un'entità `valve`/`switch`
opzionale. Primo passo (v2.x): **solo lettura** — se la valvola risulta
aperta per N minuti, l'irrigazione viene registrata in automatico. Il comando
vero e proprio resta una decisione futura separata.

## 12. Entità

**Dispositivo "Garden Irrigation"**
- `sensor.et0_yesterday` (mm), `sensor.rain_yesterday` (mm)
- `sensor.data_quality` (ok / incomplete / stale) con motivi
- `sensor.forecast_rain` (mm, solo se configurato)

**Per ogni zona (dispositivo della subentry)**
- `sensor.deficit` (mm, attuale)
- `binary_sensor.needs_irrigation`
- `sensor.recommended_irrigation` (mm) — attributi: blocchi, motivi, avvisi
- `sensor.recommended_minutes_mains`, `sensor.recommended_minutes_tank`
- Diagnostici: TAW, RAW, Kc del mese, ETc ieri, pioggia efficace ieri,
  irrigazione 7 gg, ultima irrigazione, stato sensore suolo

**Servizi**
- `record_irrigation(zone, source, minutes | mm, note?)` — timestamp attuale
- `set_deficit(zone, mm)`

Niente select modalità, niente pulsanti avvia/termina ciclo o calibrazione.

## 13. Storage

Un solo `Store` versionato:
```
{ zones: { <subentry_id>: { deficit_mm, last_balance_date,
                            days: [ {date, et0, etc, rain, eff_rain,
                                     irrigation, deficit} ... 365 gg ],
                            irrigations: [ {ts, source, minutes, mm, note} ... 365 gg ] } } }
```

## 14. Test

- `model/` al 100%: FAO-56 contro gli esempi numerici del manuale (es. 18,
  Bruxelles 6 luglio, ET0 ≈ 3,9 mm/giorno), bilancio, pioggia efficace,
  blocchi, p corretto.
- `daily_weather` con statistiche finte (giorno completo, incompleto, unità
  diverse).
- Config flow + subentry, servizi, recupero giorni, entità.
- Ruff + mypy puliti; CI: hassfest, HACS validate, pytest.

## 15. Card / dashboard

Le card in `www/` restano, ma vanno adattate alle nuove entità (ultima fase).

## 16. Fasi di lavoro

1. Scheletro: manifest, const, store, config flow + subentry + options,
   traduzioni, CI.
2. `model/`: FAO-56, terreni, Kc, bilancio, consiglio + test di riferimento.
3. `daily_weather` da statistiche + data quality + repairs.
4. Coordinator: job giornaliero, recupero giorni, servizi.
5. Entità e traduzioni.
6. Sensore suolo (soglie) e pioggia prevista.
7. Card/dashboard, README, docs, nuovo CLAUDE.md.

Una fase alla volta, CI verde prima della successiva.
