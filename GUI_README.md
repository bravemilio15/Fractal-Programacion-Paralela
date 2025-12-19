# GUI del Cluster Dask - Guia de Uso

## Instalacion de Dependencias

Antes de usar la interfaz grafica, instala las dependencias necesarias:

```bash
pip install -r requirements.txt
```

Esto instalara PyQt5 y todas las demas dependencias necesarias.

---

## Modo de Ejecucion

El sistema ahora soporta **DOS MODOS**:

### 1. Modo GUI (Por Defecto)
Interfaz grafica completa con preview en tiempo real.

### 2. Modo CLI (Linea de Comandos)
Modo original sin interfaz grafica (usa flag `--no-gui`).

---

## Ejecutar el Master (Modo GUI)

```bash
python master.py
```

Se abrira una ventana con 3 pestanas:

### Pestana 1: Configuracion
- **Presets**: Selecciona entre 480p, 720p, 1080p o Custom
- **Sliders**: Ajusta resolucion, frames, iteraciones, zoom
- **Coordenadas**: Define el punto focal del fractal
- **Boton Iniciar**: Comienza el renderizado (requiere al menos 1 worker conectado)

### Pestana 2: Cluster Dashboard
- **Tabla de Workers**: Muestra workers conectados en tiempo real
- **Barra de Progreso**: Progreso global del renderizado
- **Log de Eventos**: Mensajes del sistema

### Pestana 3: Galeria de Frames
- **Miniaturas**: Preview de frames completados
- **Generar Video**: Crea el archivo MP4 final

**Dashboard Web**: Accede a `http://<IP_MASTER>:8787` para ver el dashboard de Dask.

---

## Ejecutar el Worker (Modo GUI)

```bash
python worker.py <IP_MASTER>
```

Ejemplo:
```bash
python worker.py 192.168.1.100
```

Se abrira una ventana compacta que muestra:

- **Estado de Conexion**: LED verde cuando esta conectado
- **Preview en Tiempo Real**: Canvas mostrando el frame mientras se renderiza
- **Progreso**: Barra vertical con porcentaje
- **Estadisticas**: Frames completados, datos enviados
- **Historial**: Ultimos 5 frames con tiempos

---

## Ejecutar en Modo CLI (Sin GUI)

Si prefieres el modo original de linea de comandos:

### Master CLI:
```bash
python master.py --no-gui
```

### Worker CLI:
```bash
python worker.py <IP_MASTER> --no-gui
```

---

## Flujo de Trabajo Completo

### 1. Iniciar Master
```bash
# En la PC principal
python master.py
```

- Anota la IP que aparece en la barra de estado
- Espera a que se conecten workers

### 2. Conectar Workers
```bash
# En cada PC worker
python worker.py 192.168.1.100
```

- Verifica que el LED se ponga verde
- Revisa que aparezca en la tabla del Master

### 3. Configurar Renderizado
- En el Master, ve a la pestana "Configuracion"
- Selecciona un preset (recomendado: "720p HD" para pruebas)
- O elige "Custom" y ajusta manualmente

### 4. Iniciar Renderizado
- Click en "Iniciar Renderizado"
- El sistema cambiara automaticamente a la pestana "Dashboard"
- Observa el progreso en tiempo real

### 5. Monitorear Workers
- En cada Worker GUI veras el preview del frame actual
- La barra de progreso muestra el avance
- El preview se actualiza cada 50 filas

### 6. Generar Video
- Cuando termine el renderizado, ve a "Galeria de Frames"
- Click en "Generar Video MP4"
- El video se guardara como `mandelbrot_zoom.mp4`

---

## Presets Disponibles

| Preset | Resolucion | Frames | Iteraciones | Tiempo Estimado |
|--------|-----------|--------|-------------|-----------------|
| **480p Rapido** | 854x480 | 30 | 80 | 1-2 min |
| **720p HD** | 1280x720 | 50 | 100 | 3-5 min |
| **1080p Full HD** | 1920x1080 | 100 | 150 | 10-15 min |
| **Custom** | Variable | Variable | Variable | Variable |

---

## Prueba Local (Sin Red)

Puedes probar todo en tu PC abriendo multiples terminales:

```bash
# Terminal 1 - Master
python master.py

# Terminal 2 - Worker 1
python worker.py 127.0.0.1

# Terminal 3 - Worker 2 (opcional)
python worker.py 127.0.0.1
```

Cada worker aparecera con un nombre unico en la tabla del Master.

---

## Solución de Problemas

### Error: "PyQt5 no esta instalado"
```bash
pip install PyQt5
```

### Worker no se conecta
- Verifica que ambas PCs esten en la misma red WiFi
- Revisa que la IP del Master sea correcta
- Desactiva firewall temporalmente para probar

### Preview no se actualiza en Worker
- El preview se actualiza cada 50 filas
- En resoluciones bajas puede ser muy rapido
- Verifica que `tareas.py` tenga el callback implementado

### Video no se genera
- Verifica que ffmpeg este instalado: `pip install imageio-ffmpeg`
- Revisa que todos los frames se hayan completado
- Mira el log en la pestana Dashboard

---

## Archivos del Sistema

| Archivo | Descripcion |
|---------|-------------|
| `master.py` | Punto de entrada del Master (CLI/GUI) |
| `worker.py` | Punto de entrada del Worker (CLI/GUI) |
| `gui_master.py` | Interfaz grafica del Master |
| `gui_worker.py` | Interfaz grafica del Worker |
| `tareas.py` | Logica de renderizado del fractal |
| `presets.json` | Configuraciones predefinidas |
| `requirements.txt` | Dependencias del proyecto |

---

## Atajos de Teclado

- **Master**: `Ctrl+W` para cerrar (pregunta si hay renderizado activo)
- **Worker**: `Ctrl+W` para cerrar

---

## Caracteristicas Avanzadas

### Cambiar Punto Focal
En modo "Custom", puedes explorar diferentes regiones del fractal:

- **Punto clasico**: X=-0.743, Y=0.131 (por defecto)
- **Espiral**: X=-0.75, Y=0.1
- **Valle**: X=-0.7, Y=0.27

### Ajustar Zoom
- Zoom bajo (100-1000): Vista general
- Zoom medio (1000-10000): Detalles interesantes
- Zoom alto (10000-50000): Estructuras fractales profundas

---

## Notas Importantes

1. **Rendimiento**: Mas workers = renderizado mas rapido
2. **Memoria**: Resoluciones altas requieren mas RAM
3. **Red**: WiFi estable es importante para cluster distribuido
4. **Preview**: El preview en Worker es aproximado, el frame final sera mas nitido
5. **Compatibilidad**: Funciona en Windows, Mac y Linux

---

## Contacto y Soporte

Para problemas o preguntas sobre la GUI, revisa:
- Log en la pestana "Dashboard" del Master
- Mensajes de consola en las terminales
- Archivo `CLUSTER_SETUP.txt` para configuracion basica
