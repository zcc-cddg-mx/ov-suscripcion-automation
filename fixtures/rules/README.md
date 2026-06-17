# fixtures/rules — Referencias para migraciones de tipo `rules`

## Fuente principal de negocio

`business-reference/` contiene el archivo actuarial que entrega negocio.
De aquí nacen la mayoría de los cambios para el módulo `ams-rule`.

| Archivo | Descripción |
|---|---|
| `Cotizador_MotorIndividualV25.xlsx` | Base actuarial completa — hoja `Relatividades` con todas las tablas de factores por variable (EDAD_INPUT, GENERO_INPUT, ZONA_EMBLEM, TIPOVEHICULO, etc.) |

> Los xlsx están excluidos de git (`fixtures/**/*.xlsx`). Se distribuyen por separado.
> Contraseña: variable de entorno `BUSINESS_EXCEL_PASSWORD` (ver `.env.local`).

---

## Entidades disponibles

| Directorio | Entidad Flyway | Última migración de referencia |
|---|---|---|
| `drivers-age/` | `VHDriversAge` | `VHDriversAge_reference.xlsx` — v5→6, 65 filas (edades 17–80+999) |
| `plan-rules/` | `VHPlanRules` | `V2026_06_05_12_00_00__RITM2497361_VHPlanRules.xlsx` |
| `cover-clause/` | `VHCoverClause` | `V2026_04_29_12_00_00__INC23649033_VHCoverClause.xlsx` |
| `deductible/` | `VHDeductible` | `V2025_10_17_12_00_00__ZNRX_64279_VHDeductible.xlsx` |
| `make-model/` | `VHVehicleMakeModel` | `V2026_02_05_13_00_00__INC23253455_VHVehicleMakeModel.xlsx` |
| `plan-setup/` | `VHPlanSetup` | `V2026_02_10_14_00_00__INC23253572_VHPlanSetup.xlsx` |
| `production-unit/` | `VHProductionUnit` | `V2025_06_25_13_00_00__ZNRX_64446_VHProductionUnit.xlsx` |
| `type-of-vehicle/` | `VHTypeOfVehicle` | `V2025_06_01_12_00_00__ZNRX_63672_VHTypeOfVehicle.xlsx` |

---

## Archivos en git por directorio

Solo se versionan archivos de texto:

| Archivo | En git | Motivo |
|---|---|---|
| `drivers-age/MAPPING.md` | ✅ | Documentación del pipeline de transformación |
| `drivers-age/PLAN.md` | ✅ | Flujo e2e y pasos de verificación |
| `drivers-age/VHDriversAge_reference.java` | ✅ | Plantilla clase Java (vacía) |
| `*.xlsx` | ❌ | Datos de negocio — distribuir por separado |

> El LOV ya no se guarda en JSON. El generador lo lee directamente desde la última
> migración de cada entidad (`_write_lov(last_migration)`). Cada entidad tiene su
> propio LOV: VHDriversAge=52 filas, VHCoverClause=338, VHPlanSetup=351, etc.

---

## Estructura de un directorio con soporte completo

```
drivers-age/
  MAPPING.md                ← mapeo paso a paso: fuente → transformación → salida
  VHDriversAge_reference.java  ← plantilla clase Java vacía
  VHDriversAge_reference.xlsx  ← migración Flyway de referencia (gitignored)
```

El `MAPPING.md` documenta:
1. Qué hoja/tabla leer del cotizador (`business-reference/`)
2. La lógica de transformación (renombrado de columnas, casos especiales, filas a omitir)
3. La estructura exacta del xlsx de migración generado (columnas, orden, filas especiales)
