@echo off
REM Compila el build de produccion (mas liviano y rapido de cargar que el
REM modo dev, sobre todo para el chunk pesado de face-api.js del kiosco) y
REM lo sirve con "vite preview" -- HTTPS + proxy a /api ya configurados en
REM vite.config.js (mismo certificado autofirmado del kiosco).
REM
REM Para que arranque solo con Windows: Programador de tareas -> Crear
REM tarea basica -> Desencadenador "Al iniciar sesion" -> Accion "Iniciar
REM un programa" -> apuntar a este archivo .bat.
REM
REM Nota: cambios de codigo no se ven hasta volver a correr este script
REM (a diferencia de "npm run dev", que recarga solo). Para desarrollo
REM activo sigue usando "npm run dev".

cd /d "%~dp0"
call npm run build

:loop
echo [%date% %time%] Iniciando frontend (vite preview)...
call npm run preview
echo [%date% %time%] El frontend se detuvo (codigo %errorlevel%). Reintentando en 5s...
timeout /t 5 /nobreak >nul
goto loop
