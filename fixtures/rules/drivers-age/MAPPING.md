# VHDriversAge — Mapeo de entrada a migración Flyway

## Paso 1 — Archivo que entrega negocio

`fixtures/rules/business-reference/Cotizador_MotorIndividualV25- Modelos Enero2026.xlsx`
(contraseña: variable de entorno `BUSINESS_EXCEL_PASSWORD`, guardada en `.env.local`)

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

`VHDriversAge_reference.xlsx` — 4 hojas, generado por `src/generator_rules.py`:

| Hoja | Contenido |
|---|---|
| `RuleKit` | Solo encabezados (sin datos) |
| `RatingList` | 2 filas: OLD (versión anterior) + NEW (versión nueva, incrementada en +1) |
| `VHDriversAge` | 67 filas de datos (65 edades + `80+`→`80-998` + sentinel `999-999`) |
| `LOV` | 96 filas estáticas desde `fixtures/lov_ams_rule.json` |

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

## Resumen del flujo

```
negocio entrega:
  Cotizador_MotorIndividualV25- Modelos Enero2026.xlsx (protegido con contraseña)
      └─ hoja "Relatividades" → tabla EDAD_INPUT (65+1 filas)
                                                       │
                            transformación generador   │
                                                       ▼
  VyyyyMMddHHmmss__TICKET_VHDriversAge.xlsx
      ├─ RuleKit (headers)
      ├─ RatingList (OLD v_n + NEW v_n+1)
      ├─ VHDriversAge (67 filas: 17→79 + 80-998 + 999-999)
      └─ LOV (96 filas estáticas)
  +
  VyyyyMMddHHmmss__TICKET_VHDriversAge.java  (clase vacía)
```
