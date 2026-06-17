# VHDriversAge — Mapeo de entrada a migración Flyway

## Paso 1 — Archivo que entrega negocio

Disponibles en `fixtures/rules/business-reference/`:

| Versión | Archivo | Notas |
|---|---|---|
| V23 | `Cotizador_MotorIndividualV23.xlsx` | Histórico |
| V24 | `Cotizador_MotorIndividualV24.xlsx` | Histórico |
| V25 | `Cotizador_MotorIndividualV25.xlsx` | **Actual** — usar para nuevas migraciones |

Contraseña: variable de entorno `BUSINESS_EXCEL_PASSWORD` (guardada en `.env.local`).

| Atributo | Valor |
|---|---|
| Hoja de origen | `Relatividades` |
| Tabla de interés | `EDAD_INPUT` — comienza cuando la celda B = `'EDAD_INPUT'` |
| Columnas fuente | B=edad, C=DAPA FREC, D=DAPA CM, E=DATO FREC, F=DATO CM, G=RC FREC, H=RC CM, I=ROPA FREC, J=ROPA CM, K=ROTO FREC, L=ROTO CM |
| Filas de datos | 65 filas de edad (17–79 individuales + `80+`) + `P.JURIDICA` (descartar) |

### Estructura real de la fila (columnas B–L, columnas A y M+ son None/metadata)

```
Row 23: (None, '17', 1.50688248, 1.098170527, 2.578253235, 1.018156048, 1.827510806, 1, 1, 1, 1.84010788, 1, ...)
Row 86: (None, '80+', 1.34, 1, 1, 1, 1, 1, 1, 1, 1, 1, ...)
Row 87: (None, 'P.JURIDICA', 1, 1, ...)   ← DESCARTAR
```

---

## Paso 2 — Transformación (lógica del generador)

| Cotizador (col B) | `Drivers age from` | `Drivers age to` | Nota |
|---|---|---|---|
| `'17'` … `'79'` | int(edad) | int(edad) | Rango de un año |
| `'80+'` | 80 | 998 | Límite superior convencional |
| `'P.JURIDICA'` | — | — | **Omitir** |
| *(sentinel)* | 999 | 999 | Fila fija, todos factores=1 — agregar al final |

Columnas de factor: mapeo directo, misma posición, mismo nombre normalizado:

| Cotizador | Flyway column |
|---|---|
| `DAPA FREC` | `DAPA_FREC` |
| `DAPA CM` | `DAPA_CM` |
| `DATO FREC` | `DATO_FREC` |
| `DATO CM` | `DATO_CM` |
| `RC FREC` | `RC_FREC` |
| `RC CM` | `RC_CM` |
| `ROPA FREC` | `ROPA_FREC` |
| `ROPA CM` | `ROPA_CM` |
| `ROTO FREC` | `ROTO_FREC` |
| `ROTO CM` | `ROTO_CM` |

---

## Paso 3 — Archivo de salida (migración Flyway)

`VHDriversAge_reference.xlsx` — copia de la última migración real del sistema
(`V2026_02_05_12_00_00__INC23253455_VHDriversAge.xlsx`, versión 6, febrero 2026).
Sirve como base para auto-detectar la versión actual e incrementarla.

| Hoja | Contenido |
|---|---|
| `RuleKit` | Solo encabezados (sin datos) |
| `RatingList` | 2 filas: OLD (versión anterior) + NEW (versión nueva, incrementada en +1) |
| `VHDriversAge` | 65 filas de datos (63 edades individuales + `80+`→`80-998` + sentinel `999-999`) |
| `LOV` | 52 filas — copiadas desde la última migración de esta entidad (`_write_lov(last_migration)`) |

### Discrepancia conocida — edad 67, DAPA_CM

El cotizador V25 actual entrega `DAPA_CM=0.905193266` para edad 67. La última migración
cargada en el sistema (febrero 2026) tiene `0.985193266`. Negocio no ha solicitado
actualizar el sistema con el valor del cotizador V25. Cuando lo haga, el generador
producirá automáticamente el valor correcto desde la fuente de verdad (cotizador).

### Columnas del sheet VHDriversAge

```
ID | Rating list | Drivers age from | Drivers age to | DAPA_FREC | DAPA_CM | DATO_FREC | DATO_CM | RC_FREC | RC_CM | ROPA_FREC | ROPA_CM | ROTO_FREC | ROTO_CM
```

- `ID` siempre `None` (asignado por el sistema)
- `Rating list` siempre `'NEW'`

---

## Paso 4 — Archivo Java (clase vacía)

`VHDriversAge_reference.java` — clase que extiende `LoadFromFileMigrationTask`, nombre = stem del xlsx.

---

## Errores esperados

| Situación | Error |
|---|---|
| Contraseña incorrecta | `msoffcrypto.exceptions.InvalidKeyError` |
| Archivo sin contraseña pasado sin `password=` | `zipfile.BadZipFile` |
| `EDAD_INPUT` no encontrada en hoja `Relatividades` | `ValueError: EDAD_INPUT table not found in 'Relatividades'` |
| Factor no numérico en celda de la tabla | `ValueError: Age XX: non-numeric factor(s) in EDAD_INPUT: DAPA_FREC='abc'` |
| Sin migración previa en el repo destino | `FileNotFoundError: No previous migration found for VHDriversAge` |

---

## Resumen del flujo

```
negocio entrega:
  Cotizador_MotorIndividualV25.xlsx (protegido con contraseña)
      └─ hoja "Relatividades" → tabla EDAD_INPUT (65+1 filas)
                                                       │
                            transformación generador   │
                                                       ▼
  VyyyyMMddHHmmss__TICKET_VHDriversAge.xlsx
      ├─ RuleKit (headers)
      ├─ RatingList (OLD v_n + NEW v_n+1)
      ├─ VHDriversAge (65 filas: 17→79 + 80-998 + 999-999)
      └─ LOV (52 filas estáticas)
  +
  VyyyyMMddHHmmss__TICKET_VHDriversAge.java  (clase vacía)
```
