# Proyecto Final - Renderizado Distribuido de Fractales de Mandelbrot

.\.venv\Scripts\activate
desactivate


## 🎯 Descripción

Sistema de renderizado distribuido de fractales de Mandelbrot utilizando computación paralela con **Dask Distributed**. El sistema genera animaciones de zoom profundo en el conjunto de Mandelbrot aprovechando múltiples computadoras conectadas en red.

## ✨ Características Principales

- **Arquitectura Master-Worker distribuida** con Dask
- **Renderizado optimizado** con NumPy vectorizado y Numba JIT (10-100x más rápido)
- **Sistema de caché** para evitar re-renderizar frames idénticos
- **Compresión de datos** en tránsito para reducir uso de red
- **Logging estructurado** con niveles configurables
- **Estimación de tiempo** basada en historial
- **Configuración centralizada** con YAML
- **Interfaz GUI** con PyQt5 (master y worker)
- **Tests unitarios** con pytest

## 📋 Requisitos

- Python 3.7+
- FFmpeg (para generación de video)

## 🚀 Instalación

```bash
# Clonar repositorio
git clone https://github.com/bravemilio15/Fractal-Programacion-Paralela.git
cd "Proyecto Final"

# Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

## 💻 Uso

### Modo CLI (Sin GUI)

**Master:**
```bash
python master.py --no-gui
```

**Worker:**
```bash
python worker.py <IP_MASTER> --no-gui
```

### Modo GUI (Por defecto)

**Master:**
```bash
python master.py
```

**Worker:**
```bash
python worker.py <IP_MASTER>
```

## ⚙️ Configuración

Edita `config/config.yaml` para personalizar:

- Puertos del cluster
- Preset de renderizado por defecto
- Activar/desactivar caché
- Nivel de compresión
- Usar versión optimizada (NumPy/Numba)
- Nivel de logging

### Presets Disponibles

- **480p_rapido**: 854×480, 30 frames (1-2 min)
- **720p_hd**: 1280×720, 50 frames (3-5 min)
- **1080p_fullhd**: 1920×1080, 100 frames (10-15 min)
- **custom**: Personalizable

## 📁 Estructura del Proyecto

```
Proyecto Final/
├── config/
│   ├── config.yaml          # Configuración principal
│   └── presets.json         # Presets de renderizado
├── core/                    # Módulos core (futuro)
├── fractals/
│   ├── base.py              # Clase base abstracta
│   ├── mandelbrot.py        # Versión estándar
│   └── mandelbrot_optimized.py  # Versión optimizada
├── gui/
│   ├── gui_master.py        # GUI del master
│   └── gui_worker.py        # GUI del worker
├── utils/
│   ├── cache.py             # Sistema de caché
│   ├── config.py            # Gestor de configuración
│   ├── estimator.py         # Estimador de tiempo
│   ├── exceptions.py        # Excepciones personalizadas
│   ├── logger.py            # Logging estructurado
│   └── network.py           # Utilidades de red
├── tests/
│   ├── test_mandelbrot.py
│   ├── test_render_engine.py
│   └── test_config.py
├── master.py                # Punto de entrada master
├── worker.py                # Punto de entrada worker
├── tareas.py                # Funciones de renderizado
└── requirements.txt
```

## 🧪 Tests

```bash
# Ejecutar todos los tests
pytest tests/ -v

# Con cobertura
pytest tests/ --cov=. --cov-report=html
```

## 🚀 Optimizaciones Implementadas

### Rendimiento
- **NumPy vectorizado**: 10-20x más rápido que Python puro
- **Numba JIT**: 50-100x más rápido con compilación a código máquina
- **Caché de frames**: Evita re-renderizar frames idénticos
- **Compresión**: Reduce tráfico de red en 30-50%

### Arquitectura
- **Configuración centralizada**: YAML para todos los parámetros
- **Logging estructurado**: Niveles configurables, salida a archivo
- **Type hints**: Mejor detección de errores y autocompletado
- **Excepciones personalizadas**: Manejo de errores robusto

### UX
- **Estimación de tiempo**: Basada en historial de renderizados
- **Dashboard Dask**: Monitoreo en tiempo real (puerto 8787)
- **Logs persistentes**: Guardados en `logs/`

## 📊 Ejemplo de Rendimiento

| Configuración | Python Puro | NumPy | Numba JIT |
|--------------|-------------|-------|-----------|
| 720p, 50 frames | ~15 min | ~2 min | ~30 seg |
| 1080p, 100 frames | ~60 min | ~8 min | ~2 min |

*Tiempos aproximados con 4 workers*

## 🔧 Troubleshooting

### Error: "Numba no disponible"
```bash
pip install numba
```

### Error: "Error creando video"
Instala FFmpeg:
- **Windows**: `choco install ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

### Workers no se conectan
- Verifica que el firewall permita el puerto 8786
- Asegúrate de usar la IP correcta del master
- Revisa los logs en `logs/worker.log`

## 📝 Licencia

Este proyecto fue desarrollado para el curso de Programación Paralela.  
Universidad Nacional de Loja - 7mo Semestre

## 👥 Autor

Emilio Bravo

## 🙏 Agradecimientos

- Dask Team por el excelente framework de computación distribuida
- NumPy y Numba por las optimizaciones de rendimiento
