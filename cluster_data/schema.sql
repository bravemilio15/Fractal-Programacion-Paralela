-- Schema SQLite para Sistema de Renders Multi-Fractal
-- Versión 1.0
-- Fecha: 2026-01-06

-- ============================================
-- 1. TABLA DE TIPOS DE FRACTALES
-- ============================================
CREATE TABLE IF NOT EXISTS fractal_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    renderer_class TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insertar Mandelbrot por defecto
INSERT OR IGNORE INTO fractal_types (name, description, renderer_class)
VALUES ('mandelbrot', 'Conjunto de Mandelbrot', 'MandelbrotOptimizedRenderer');

-- ============================================
-- 2. TABLA DE RENDERS (Sesiones)
-- ============================================
CREATE TABLE IF NOT EXISTS renders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fractal_type_id INTEGER NOT NULL,
    preset TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Configuración de renderizado
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    total_frames INTEGER NOT NULL,
    max_iter INTEGER NOT NULL,
    
    -- Configuración específica del fractal (JSON)
    fractal_config TEXT,
    
    -- Estado del render
    status TEXT NOT NULL DEFAULT 'pending',
    started_at DATETIME,
    completed_at DATETIME,
    total_time REAL,
    
    -- Archivos generados
    output_dir TEXT,
    video_path TEXT,
    
    -- Estadísticas
    frames_completed INTEGER DEFAULT 0,
    frames_failed INTEGER DEFAULT 0,
    total_retries INTEGER DEFAULT 0,
    
    FOREIGN KEY (fractal_type_id) REFERENCES fractal_types(id),
    CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled'))
);

-- ============================================
-- 3. TABLA DE FRAMES
-- ============================================
CREATE TABLE IF NOT EXISTS frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    render_id INTEGER NOT NULL,
    frame_num INTEGER NOT NULL,
    worker_name TEXT,
    
    -- Tiempos
    queued_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    render_time REAL,
    
    -- Estado
    status TEXT NOT NULL DEFAULT 'pending',
    retries INTEGER DEFAULT 0,
    error_message TEXT,
    
    -- Metadata
    file_path TEXT,
    file_size INTEGER,
    compressed BOOLEAN DEFAULT 0,
    
    FOREIGN KEY (render_id) REFERENCES renders(id) ON DELETE CASCADE,
    UNIQUE(render_id, frame_num),
    CHECK (status IN ('pending', 'assigned', 'rendering', 'completed', 'failed'))
);

-- ============================================
-- 4. TABLA DE WORKERS
-- ============================================
CREATE TABLE IF NOT EXISTS workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    render_id INTEGER NOT NULL,
    worker_name TEXT NOT NULL,
    ip_address TEXT,
    
    -- Conexión
    connected_at DATETIME NOT NULL,
    disconnected_at DATETIME,
    connection_duration REAL,
    
    -- Estadísticas
    frames_completed INTEGER DEFAULT 0,
    frames_failed INTEGER DEFAULT 0,
    total_render_time REAL DEFAULT 0,
    avg_frame_time REAL,
    
    -- Status
    status TEXT DEFAULT 'connected',
    
    FOREIGN KEY (render_id) REFERENCES renders(id) ON DELETE CASCADE,
    CHECK (status IN ('connected', 'disconnected', 'error'))
);

-- ============================================
-- 5. ÍNDICES PARA PERFORMANCE
-- ============================================
CREATE INDEX IF NOT EXISTS idx_frames_render_id ON frames(render_id);
CREATE INDEX IF NOT EXISTS idx_frames_status ON frames(status);
CREATE INDEX IF NOT EXISTS idx_frames_render_status ON frames(render_id, status);
CREATE INDEX IF NOT EXISTS idx_workers_render_id ON workers(render_id);
CREATE INDEX IF NOT EXISTS idx_renders_status ON renders(status);
CREATE INDEX IF NOT EXISTS idx_renders_timestamp ON renders(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_renders_fractal_type ON renders(fractal_type_id);

-- ============================================
-- 6. VISTAS ÚTILES
-- ============================================

-- Vista de renders con información completa
CREATE VIEW IF NOT EXISTS v_renders_full AS
SELECT 
    r.id,
    r.timestamp,
    ft.name as fractal_type,
    r.preset,
    r.width,
    r.height,
    r.total_frames,
    r.max_iter,
    r.status,
    r.total_time,
    r.frames_completed,
    r.frames_failed,
    r.output_dir,
    r.video_path,
    COUNT(DISTINCT w.id) as total_workers
FROM renders r
LEFT JOIN fractal_types ft ON r.fractal_type_id = ft.id
LEFT JOIN workers w ON r.id = w.render_id
GROUP BY r.id;

-- Vista de estadísticas por worker
CREATE VIEW IF NOT EXISTS v_worker_stats AS
SELECT 
    w.id,
    w.render_id,
    w.worker_name,
    w.ip_address,
    w.connected_at,
    w.disconnected_at,
    w.frames_completed,
    w.frames_failed,
    w.total_render_time,
    w.avg_frame_time,
    w.status,
    ROUND(w.frames_completed * 100.0 / NULLIF(w.frames_completed + w.frames_failed, 0), 2) as success_rate
FROM workers w;

-- ============================================
-- 7. TRIGGERS PARA ACTUALIZACIÓN AUTOMÁTICA
-- ============================================

-- Trigger: Actualizar contador de frames completados
CREATE TRIGGER IF NOT EXISTS update_render_completed_frames
AFTER UPDATE OF status ON frames
WHEN NEW.status = 'completed'
BEGIN
    UPDATE renders 
    SET frames_completed = frames_completed + 1
    WHERE id = NEW.render_id;
END;

-- Trigger: Actualizar contador de frames fallidos
CREATE TRIGGER IF NOT EXISTS update_render_failed_frames
AFTER UPDATE OF status ON frames
WHEN NEW.status = 'failed'
BEGIN
    UPDATE renders 
    SET frames_failed = frames_failed + 1
    WHERE id = NEW.render_id;
END;

-- Trigger: Actualizar estadísticas de worker
CREATE TRIGGER IF NOT EXISTS update_worker_stats
AFTER UPDATE OF status ON frames
WHEN NEW.status = 'completed'
BEGIN
    UPDATE workers
    SET 
        frames_completed = frames_completed + 1,
        total_render_time = total_render_time + NEW.render_time,
        avg_frame_time = (total_render_time + NEW.render_time) / (frames_completed + 1)
    WHERE render_id = NEW.render_id AND worker_name = NEW.worker_name;
END;

-- Trigger: Calcular duración de conexión al desconectar worker
CREATE TRIGGER IF NOT EXISTS calculate_connection_duration
AFTER UPDATE OF disconnected_at ON workers
WHEN NEW.disconnected_at IS NOT NULL
BEGIN
    UPDATE workers
    SET connection_duration = (julianday(NEW.disconnected_at) - julianday(connected_at)) * 86400
    WHERE id = NEW.id;
END;
