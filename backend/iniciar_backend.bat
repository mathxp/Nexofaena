@echo off
REM Sirve el backend con Waitress (ver servir_produccion.py) en vez de
REM "manage.py runserver", que no esta pensado para dejarlo prendido sin
REM supervision. Se reinicia solo si se cae.
REM
REM Antes de la primera vez: python manage.py collectstatic --noinput
REM (whitenoise necesita el manifiesto de archivos estaticos).
REM
REM Para que arranque solo con Windows: Programador de tareas -> Crear
REM tarea basica -> Desencadenador "Al iniciar sesion" -> Accion "Iniciar
REM un programa" -> apuntar a este archivo .bat.

cd /d "%~dp0"
call ..\.venv\Scripts\activate.bat

:loop
echo [%date% %time%] Iniciando backend (Waitress)...
python servir_produccion.py
echo [%date% %time%] El backend se detuvo (codigo %errorlevel%). Reintentando en 5s...
timeout /t 5 /nobreak >nul
goto loop
