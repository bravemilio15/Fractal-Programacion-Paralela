# Solucion: Worker GUI Preview

## Problema Identificado

El Worker GUI se conectaba correctamente pero el preview se quedaba en blanco. Esto ocurria porque:

1. **Dask ejecuta tareas en procesos separados** (multiprocessing)
2. **Los callbacks de PyQt no funcionan entre procesos** diferentes
3. La funcion `generar_frame_mandelbrot` corre en un proceso worker separado
4. No hay forma directa de pasar callbacks de GUI a ese proceso

## Solucion Implementada

### Monitoreo de Stdout

En lugar de callbacks directos, ahora el Worker GUI:

1. **Captura el stdout** del proceso worker
2. **Parsea los mensajes** `[FRAME X] Renderizando...` y `[FRAME X] Listo...`
3. **Emite señales PyQt** cuando detecta estos eventos
4. **Actualiza la GUI** con la informacion capturada

### Cambios Realizados

**gui_worker.py:**
- Agregado `TeeOutput` class para capturar stdout
- Agregado `process_output()` para parsear mensajes
- Agregado `task_info` signal para mensajes generales
- Agregado progreso simulado con animacion
- Removido `progress_update` signal (no funcional)

### Comportamiento Actual

**Cuando inicia un frame:**
- Detecta `[FRAME X] Renderizando...`
- Muestra "Renderizando Frame X..."
- Inicia animacion de progreso (0% → 95%)
- Actualiza cada 200ms

**Cuando completa un frame:**
- Detecta `[FRAME X] Listo. Enviando...`
- Calcula tiempo transcurrido
- Muestra "Frame X completado! Y.YY segundos"
- Actualiza estadisticas (frames completados, MB enviados)
- Agrega al historial

## Limitaciones

- **No hay preview visual** del frame mientras renderiza (solo texto)
- **Progreso es simulado** (no refleja filas reales)
- **Depende de formato de mensajes** en tareas.py

## Ventajas

- **Funciona sin modificar Dask** internamente
- **Compatible con multiprocessing**
- **Retroalimentacion visual clara** para el usuario
- **Tracking preciso** de inicio/fin de frames

## Prueba

```bash
# Terminal 1
python master.py

# Terminal 2
python worker.py 127.0.0.1
```

**Observaras:**
- LED verde al conectar
- "Renderizando Frame X..." cuando inicia
- Barra de progreso animada
- "Frame X completado!" cuando termina
- Historial actualizado
- Estadisticas de MB enviados
