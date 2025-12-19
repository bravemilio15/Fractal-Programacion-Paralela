# Fractal-Programacion-Paralela

## Descripción General

Este proyecto es un sistema de renderizado distribuido de fractales de Mandelbrot que utiliza computación paralela para generar animaciones de zoom profundo en el conjunto de Mandelbrot. El sistema está diseñado para aprovechar múltiples computadoras conectadas en red, distribuyendo la carga de trabajo de renderizado entre varios nodos worker coordinados por un nodo master.

## ¿Qué es el Conjunto de Mandelbrot?

El conjunto de Mandelbrot es una estructura fractal matemática que exhibe una complejidad infinita. Al hacer zoom en diferentes regiones del fractal, se revelan patrones autosimilares que se repiten a diferentes escalas. Este proyecto genera animaciones cinematográficas que muestran este fascinante viaje visual a través de las profundidades del fractal.

## Arquitectura del Sistema

### Modelo Distribuido Master-Worker

El proyecto implementa una arquitectura cliente-servidor distribuida basada en el paradigma master-worker:

- **Nodo Master**: Coordina todo el proceso de renderizado, distribuye tareas a los workers, recopila los frames completados y ensambla el video final.
- **Nodos Worker**: Ejecutan el cálculo intensivo de renderizado de frames individuales y envían los resultados de vuelta al master.

Esta arquitectura permite escalar horizontalmente el poder de cómputo simplemente agregando más computadoras a la red.

## Tecnologías Utilizadas

### Framework de Computación Distribuida

**Dask Distributed**: El núcleo del sistema utiliza Dask, un framework de computación paralela en Python que proporciona:
- Planificación dinámica de tareas
- Balanceo de carga automático entre workers
- Tolerancia a fallos
- Dashboard web en tiempo real para monitoreo del cluster
- Comunicación eficiente entre nodos mediante protocolos optimizados

### Interfaz Gráfica de Usuario

**PyQt5**: Framework multiplataforma para crear interfaces gráficas nativas que ofrece:
- Ventanas con múltiples pestañas para organizar funcionalidades
- Widgets interactivos (sliders, botones, tablas)
- Sistema de señales y slots para programación reactiva
- Renderizado de imágenes en tiempo real
- Temas personalizables (modo oscuro implementado)

### Procesamiento de Imágenes

**Pillow (PIL)**: Biblioteca de manipulación de imágenes utilizada para:
- Crear imágenes RGB en memoria
- Manipular píxeles individuales para el renderizado del fractal
- Convertir imágenes a formato PNG
- Serializar imágenes a bytes para transmisión por red

### Generación de Video

**ImageIO con FFmpeg**: Herramientas para ensamblar frames en video:
- Lectura y escritura de múltiples formatos de imagen
- Codificación de video H.264 de alta calidad
- Control de framerate y calidad de compresión
- Generación de archivos MP4 compatibles universalmente

### Comunicación en Red

**Socket y Fabric**: Utilidades de red para:
- Detección automática de direcciones IP locales
- Comunicación TCP/IP entre nodos
- Ejecución remota de comandos SSH (opcional)
- Configuración de timeouts y manejo de conexiones

### Procesamiento Numérico

**NumPy**: Biblioteca fundamental para cálculos científicos que proporciona:
- Operaciones matemáticas optimizadas
- Manejo eficiente de arrays multidimensionales
- Funciones para interpolación y transformaciones

**Pandas**: Utilizado para análisis y estructuración de datos de rendimiento del cluster.

## Características Principales

### Modos de Operación

El sistema ofrece dos modos de ejecución:

1. **Modo GUI (Interfaz Gráfica)**: Modo por defecto que proporciona una experiencia visual completa con controles interactivos y retroalimentación en tiempo real.

2. **Modo CLI (Línea de Comandos)**: Modo tradicional sin interfaz gráfica, ideal para servidores o entornos sin display.

### Interfaz del Master

La aplicación master presenta tres pestañas principales:

#### Pestaña de Configuración
- **Presets predefinidos**: Configuraciones optimizadas para diferentes calidades (480p, 720p, 1080p)
- **Controles personalizados**: Sliders para ajustar resolución, número de frames, iteraciones y nivel de zoom
- **Coordenadas del punto focal**: Permite explorar diferentes regiones del fractal
- **Validación de workers**: Verifica que haya al menos un worker conectado antes de iniciar

#### Pestaña de Dashboard
- **Tabla de workers en vivo**: Muestra todos los nodos conectados con sus estadísticas
- **Barra de progreso global**: Visualización del porcentaje de completitud del renderizado
- **Log de eventos**: Registro cronológico de todas las actividades del sistema
- **Actualización automática**: Refresco periódico de la información sin intervención del usuario

#### Pestaña de Galería
- **Miniaturas de frames**: Vista previa de todos los frames completados
- **Organización automática**: Los frames se ordenan secuencialmente
- **Generación de video**: Botón para ensamblar todos los frames en un archivo MP4
- **Indicadores visuales**: Muestra cuántos frames se han completado

### Interfaz del Worker

Cada worker muestra una ventana compacta con:

- **Indicador LED de conexión**: Verde cuando está conectado al master, rojo en caso contrario
- **Canvas de preview en tiempo real**: Muestra el frame que se está renderizando mientras se calcula
- **Barra de progreso vertical**: Indica el porcentaje de completitud del frame actual
- **Estadísticas de rendimiento**: Frames completados, datos transmitidos, tiempo de procesamiento
- **Historial de frames**: Últimos 5 frames procesados con sus tiempos respectivos

### Sistema de Presets

El proyecto incluye configuraciones predefinidas optimizadas:

- **480p Rápido**: 854×480 píxeles, 30 frames, 80 iteraciones (1-2 minutos)
- **720p HD**: 1280×720 píxeles, 50 frames, 100 iteraciones (3-5 minutos)
- **1080p Full HD**: 1920×1080 píxeles, 100 frames, 150 iteraciones (10-15 minutos)
- **Custom**: Configuración completamente personalizable

### Algoritmo de Renderizado

El sistema implementa el algoritmo de escape del conjunto de Mandelbrot:

1. **Cálculo iterativo**: Para cada píxel, se calcula la función iterativa z = z² + c
2. **Detección de escape**: Se determina cuántas iteraciones toma para que el valor escape al infinito
3. **Colorización psicodélica**: Se aplica un esquema de colores basado en el número de iteraciones
4. **Interpolación de zoom**: Se calcula exponencialmente para crear una transición suave

### Distribución Inteligente de Tareas

Dask implementa un sistema sofisticado de distribución:

- **Balanceo de carga dinámico**: Las tareas se asignan automáticamente a workers disponibles
- **Priorización de tareas**: Los frames se procesan en orden óptimo
- **Recuperación de fallos**: Si un worker falla, sus tareas se reasignan automáticamente
- **Optimización de red**: Los datos se transmiten de forma eficiente minimizando overhead

### Monitoreo en Tiempo Real

El dashboard web de Dask (puerto 8787) proporciona:

- **Gráficos de utilización**: CPU, memoria y red de cada worker
- **Visualización de tareas**: Estado de cada tarea en el pipeline
- **Métricas de rendimiento**: Throughput, latencia y eficiencia del cluster
- **Diagnóstico de problemas**: Identificación de cuellos de botella

## Casos de Uso

### Uso Educativo

- **Aprendizaje de computación paralela**: Demuestra conceptos de programación distribuida
- **Visualización matemática**: Explora propiedades del conjunto de Mandelbrot
- **Optimización de algoritmos**: Experimenta con diferentes estrategias de paralelización

### Uso Profesional

- **Renderizado de alta calidad**: Genera videos de fractales para presentaciones o arte digital
- **Benchmarking de clusters**: Evalúa el rendimiento de infraestructura distribuida
- **Prototipado de sistemas distribuidos**: Sirve como base para otros proyectos de computación paralela

### Configuración de Red

El sistema soporta múltiples topologías:

- **Cluster local**: Múltiples workers en la misma máquina (para pruebas)
- **Red local (LAN)**: Computadoras conectadas a la misma red WiFi o Ethernet
- **Configuración híbrida**: Combinación de workers locales y remotos

## Flujo de Trabajo Típico

1. **Inicialización del Master**: Se inicia el scheduler de Dask y se espera conexión de workers
2. **Conexión de Workers**: Cada worker se registra automáticamente con el master
3. **Configuración de Parámetros**: El usuario selecciona preset o configura manualmente
4. **Distribución de Tareas**: El master calcula parámetros para cada frame y los distribuye
5. **Renderizado Paralelo**: Los workers procesan frames simultáneamente
6. **Recopilación de Resultados**: Los frames completados se envían de vuelta al master
7. **Ensamblaje de Video**: Una vez completados todos los frames, se genera el archivo MP4

## Optimizaciones Implementadas

### Eficiencia de Memoria

- Los frames se generan completamente en memoria sin escribir a disco en los workers
- Las imágenes se serializan a bytes para transmisión eficiente
- El master guarda frames a disco de forma asíncrona sin bloquear el renderizado

### Eficiencia de Red

- Configuración de timeouts optimizados para redes lentas
- Compresión PNG de imágenes antes de transmisión
- Reducción de overhead de comunicación mediante batching

### Experiencia de Usuario

- Actualización de preview cada 50 filas para no saturar la GUI
- Tema oscuro para reducir fatiga visual
- Mensajes informativos en español para mejor comprensión
- Protección contra cierre accidental durante renderizado

## Compatibilidad

El sistema es multiplataforma y funciona en:

- **Windows**: Totalmente compatible (versión principal de desarrollo)
- **macOS**: Compatible con todas las funcionalidades
- **Linux**: Compatible, ideal para servidores sin GUI usando modo CLI

## Requisitos del Sistema

### Hardware Mínimo

- **Procesador**: CPU de 2 núcleos o superior
- **Memoria RAM**: 2 GB mínimo (4 GB recomendado)
- **Almacenamiento**: 500 MB para frames temporales
- **Red**: Conexión WiFi o Ethernet para modo distribuido

### Software

- **Python**: Versión 3.7 o superior
- **Dependencias**: Todas listadas en requirements.txt
- **Sistema Operativo**: Windows 10+, macOS 10.14+, o Linux moderno

## Extensibilidad

El proyecto está diseñado para ser extensible:

- **Otros fractales**: La arquitectura permite implementar Julia sets, Burning Ship, etc.
- **Algoritmos de color**: Fácil modificación del esquema de colorización
- **Formatos de salida**: Soporte para diferentes formatos de video o imagen
- **Métricas personalizadas**: Integración de sistemas de monitoreo adicionales

## Documentación Adicional

El proyecto incluye documentación complementaria:

- **GUI_README.md**: Guía detallada de uso de la interfaz gráfica
- **QUICKSTART.md**: Guía de inicio rápido para comenzar inmediatamente
- **CLUSTER_SETUP.txt**: Instrucciones para configurar un cluster en red
- **WORKER_GUI_FIX.md**: Soluciones a problemas comunes de la GUI del worker

## Salida del Proyecto

El resultado final es un archivo de video MP4 de alta calidad que muestra:

- Una animación suave de zoom en el conjunto de Mandelbrot
- Transiciones exponenciales que revelan detalles fractales
- Colores vibrantes que resaltan la estructura matemática
- Framerate configurable (por defecto 15 FPS)
- Resolución personalizable hasta 1080p o superior

Este video puede ser utilizado para presentaciones académicas, contenido educativo, arte digital o simplemente para apreciar la belleza matemática de los fractales.

---

**Proyecto desarrollado para el curso de Programación Paralela**  
**Universidad Nacional de Loja - 7mo Semestre**
