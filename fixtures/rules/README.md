# fixtures/rules — Referencias para migraciones de tipo `rules`

Cada subdirectorio contiene los archivos de referencia de un tipo de entidad:

| Directorio | Entidad | Descripción |
|---|---|---|
| `drivers-age/` | `VHDriversAge` | Factores por edad del propietario |
| `plan-rules/` | `VHPlanRules` | Reglas de planes (años, suma asegurada, etc.) |

## Estructura de cada subdirectorio

```
<entidad>/
  Cotizador_*.xlsx          ← archivo que entrega negocio (fuente de datos)
  <Entidad>_reference.xlsx  ← migración Flyway de referencia (salida esperada)
  <Entidad>_reference.java  ← clase Java vacía de referencia
  MAPPING.md                ← mapeo paso a paso: fuente → transformación → salida
```

## Uso

El `MAPPING.md` de cada entidad documenta:
1. Qué hoja/tabla leer del archivo de negocio
2. La lógica de transformación (renombrado de columnas, casos especiales, filas a omitir)
3. La estructura exacta del xlsx de migración generado
