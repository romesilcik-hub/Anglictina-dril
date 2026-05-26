# AJ Dril — Procvičování anglické gramatiky

Webová aplikace pro systematické procvičování anglické gramatiky metodou drilu.  
Určena pro české studenty angličtiny na úrovních A0–B1.

## Součásti

### 🇬🇧 Drilová aplikace (`aj_dril/index.html`)
- Procvičování vět CZ → EN s přehráváním přes Web Speech API
- Filtry podle úrovně, gramatického jevu, tématu a typu věty
- Hodnocení vět (✓ / ~ / ✗), statistiky, denní cíl
- Oblíbené věty, tmavý režim, klávesové zkratky
- PWA — lze nainstalovat na mobil

### ⚙️ Generátor promptů (`Generátor/prompt_builder.html`)
- Generátor promptů pro AI (Claude / ChatGPT) pro tvorbu nových drilových vět
- Výstup ve formátu tabulky pro import do Excelu
- Pokrývá všechny gramatické jevy A0–B1 s explicitními pravidly pro správnou gramatiku

## Databáze

Věty jsou uloženy v souboru `aj_dril/aj_dril_databaze.json` exportovaném z Excelu.  
Aplikace databázi automaticky stáhne při spuštění.

## Licence

© 2025 Roman Ilčík  
Licencováno pod [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) —  
volné použití a sdílení s uvedením autora, nekomerční užití.
