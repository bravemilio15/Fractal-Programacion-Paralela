# Inicio Rapido - GUI del Cluster Dask

## Instalacion (Una sola vez)

```bash
pip install -r requirements.txt
```

## Ejecutar Master (GUI)

```bash
python master.py
```

**Que veras:**
- Ventana con 3 pestanas
- IP del Master en la barra de estado
- Dashboard disponible en http://IP:8787

## Ejecutar Worker (GUI)

```bash
python worker.py <IP_DEL_MASTER>
```

**Ejemplo:**
```bash
python worker.py 192.168.1.100
```

**Que veras:**
- Ventana compacta con LED de conexion
- Preview del frame en tiempo real
- Estadisticas de rendimiento

## Prueba Local (Sin Red)

**Terminal 1:**
```bash
python master.py
```

**Terminal 2:**
```bash
python worker.py 127.0.0.1
```

## Flujo de Trabajo

1. **Inicia Master** → Anota la IP
2. **Conecta Workers** → Verifica LED verde
3. **Configura** → Selecciona preset (ej: "720p HD")
4. **Renderiza** → Click "Iniciar Renderizado"
5. **Observa** → Preview en Worker, progreso en Master
6. **Genera Video** → Pestana "Galeria" → "Generar Video MP4"

## Presets Disponibles

- **480p Rapido**: 1-2 min (pruebas)
- **720p HD**: 3-5 min (recomendado)
- **1080p Full HD**: 10-15 min (alta calidad)
- **Custom**: Configuracion manual

## Modo CLI (Sin GUI)

```bash
python master.py --no-gui
python worker.py <IP> --no-gui
```

## Ayuda

Ver `GUI_README.md` para documentacion completa.
