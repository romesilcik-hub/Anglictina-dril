# Plán implementace — AJ Dril refaktoring

## Stav před startem
- Stará data v databázi smazána (americká AJ, testovací)
- Nová data: 43 TSV souborů ze složky Prompty vložena do xlsm a exportována jako JSON

## Kroky v pořadí

### 1. Předělat patterny v databázi a konfiguraci
- Oddělit `pattern` (typ věty) od `person` (osoba/číslo)
- `pattern`: affirmative / negative / question / wh_question / imperative / comparison / tag_question / time_clause / passive / indirect / conditional
- `person`: first / second / third_singular / plural (nové pole, volitelné)
- Existující věty: third_person → pattern: affirmative + person: third_singular atd.
- Upravit `aj_dril_generator_config.json` — patterns bez osob, nový klíč `persons`

### 2. Upravit generátor (get_next_task.py + prompt)
- Generátor střídá osoby v rámci každého patternu
- Prompt instrukce rozšířeny o požadavek na střídání osob

### 3. Přidat frekvenční prioritizaci do get_next_task.py
- Při startu načte aj_dril_databaze.json + TSV soubory ve složce Prompty
- Spočítá deficit každé gramatiky vůči cílovým frekvencím
- Vybere příští kombinaci podle největšího deficitu (ne sekvenčně)
- Progress soubor slouží jen k zabránění duplicitních TSV

### 4. V aplikaci — vážený výběr gramatiky
- Automatický trénink vybírá gramatiku podle reálné frekvence
- Filtr úrovně zůstává aktivní vždy
- Filtry téma/gramatika jsou pro cílený mód
- Oblíbená témata — uživatel si vybere více témat, aplikace preferuje věty z nich
